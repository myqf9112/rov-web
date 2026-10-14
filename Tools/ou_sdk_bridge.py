"""SDK-backed OU v0.4 shell -- drop-in replacement for ou_crypto.SerialShell.

The cryptography here is not reimplemented: every seal/open goes through
ou_sdk 0.4.1's own ``ou::crypto::ShellCrypto`` (SM4-CBC + HMAC-SM3), reached via
the flat C ABI in ``Tools/ou_sdk_wrapper`` (libou_link_wrap.so). That makes this
the *second* independent path onto the same wire format:

    ou_crypto.SerialShell  -- pure-Python reference implementation
    SdkShell               -- the shipping ou_sdk 0.4.1 artifact

``ou_dashboard.py --decoder sdk`` uses this class instead of the Python one, so
the browser UI (which never touches crypto) is unchanged while the bytes on the
wire are produced and accepted by the vendor SDK.

Usage
-----
    export OU_SDK_ROOT=/path/to/ou-sdk-0.4.1        # include/ + lib/
    cmake -S Tools/ou_sdk_wrapper -B Tools/ou_sdk_wrapper/build -DOU_SDK_ROOT=$OU_SDK_ROOT
    cmake --build Tools/ou_sdk_wrapper/build
    python3 Tools/ou_sdk_bridge.py --self-test

The wrapper library is found via ``OU_SDK_WRAPPER_LIB`` (explicit path) or the
default ``Tools/ou_sdk_wrapper/build/`` location.
"""

import ctypes
import os
import struct
import sys
import time
from collections.abc import Mapping

MAX_PLAIN = 512
MAX_SHELL = 296

SIDE_BOARD = 0
SIDE_FC = 1

_HERE = os.path.dirname(os.path.realpath(__file__))
_WRAPPER_DIR = os.path.join(_HERE, "ou_sdk_wrapper")

_LIB_NAMES = ("libou_link_wrap.so", "libou_link_wrap.dylib", "ou_link_wrap.dll")


class SdkError(RuntimeError):
    """The ou_sdk wrapper could not be loaded or used."""


# ---------------------------------------------------------------------------
# Library discovery
# ---------------------------------------------------------------------------

def _library_candidates():
    explicit = os.environ.get("OU_SDK_WRAPPER_LIB")
    if explicit:
        yield explicit
    for sub in ("build", "build/lib", "build/Release", ""):
        for name in _LIB_NAMES:
            yield os.path.join(_WRAPPER_DIR, sub, name) if sub else \
                os.path.join(_WRAPPER_DIR, name)


def _sdk_lib_candidates():
    """Directories that may hold libou_crypto.so, to preload before the wrapper."""
    for var in ("OU_SDK_LIB_DIR",):
        if os.environ.get(var):
            yield os.environ[var]
    if os.environ.get("OU_SDK_ROOT"):
        yield os.path.join(os.environ["OU_SDK_ROOT"], "lib")


class _Stats(ctypes.Structure):
    _fields_ = [
        ("frames_ok", ctypes.c_uint64),
        ("auth_fail", ctypes.c_uint64),
        ("replay", ctypes.c_uint64),
        ("unpad_fail", ctypes.c_uint64),
        ("resync_bytes", ctypes.c_uint64),
    ]


_LIB = None


def _load_library():
    """Load libou_link_wrap.so once, with prototypes declared."""
    global _LIB
    if _LIB is not None:
        return _LIB

    # Load the SDK's crypto core first when we know where it lives: the wrapper
    # has an rpath, but a relocated artifact would otherwise fail to resolve.
    for directory in _sdk_lib_candidates():
        for name in ("libou_crypto.so.0.4.1", "libou_crypto.so.0", "libou_crypto.so"):
            path = os.path.join(directory, name)
            if os.path.exists(path):
                try:
                    ctypes.CDLL(path, mode=ctypes.RTLD_GLOBAL)
                except OSError:
                    pass
                break
        break

    errors = []
    for path in _library_candidates():
        if not os.path.exists(path):
            continue
        try:
            lib = ctypes.CDLL(path)
        except OSError as exc:                                  # noqa: PERF203
            errors.append("%s: %s" % (path, exc))
            continue
        _declare(lib)
        _LIB = lib
        return _LIB

    detail = "; ".join(errors) if errors else "no candidate path exists"
    raise SdkError(
        "cannot load the OU SDK wrapper library (%s).\n"
        "Build it first:\n"
        "  cmake -S Tools/ou_sdk_wrapper -B Tools/ou_sdk_wrapper/build "
        "-DOU_SDK_ROOT=<ou-sdk-0.4.1>\n"
        "  cmake --build Tools/ou_sdk_wrapper/build\n"
        "or point OU_SDK_WRAPPER_LIB at libou_link_wrap.so." % detail)


def _declare(lib):
    u8p = ctypes.POINTER(ctypes.c_uint8)
    size_p = ctypes.POINTER(ctypes.c_size_t)

    lib.ou_link_create.argtypes = [u8p, ctypes.c_int]
    lib.ou_link_create.restype = ctypes.c_void_p

    lib.ou_link_destroy.argtypes = [ctypes.c_void_p]
    lib.ou_link_destroy.restype = None

    lib.ou_link_set_start_seq.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
    lib.ou_link_set_start_seq.restype = None

    lib.ou_link_tx_sequence.argtypes = [ctypes.c_void_p]
    lib.ou_link_tx_sequence.restype = ctypes.c_uint32

    lib.ou_link_reset_receiver.argtypes = [ctypes.c_void_p]
    lib.ou_link_reset_receiver.restype = None

    lib.ou_link_seal.argtypes = [ctypes.c_void_p, u8p, ctypes.c_size_t, u8p, ctypes.c_size_t]
    lib.ou_link_seal.restype = ctypes.c_size_t

    lib.ou_link_push.argtypes = [ctypes.c_void_p, u8p, ctypes.c_size_t]
    lib.ou_link_push.restype = None

    lib.ou_link_next.argtypes = [ctypes.c_void_p, u8p, ctypes.c_size_t, size_p,
                                 u8p, ctypes.c_size_t, size_p]
    lib.ou_link_next.restype = ctypes.c_int

    lib.ou_link_get_stats.argtypes = [ctypes.c_void_p, ctypes.POINTER(_Stats)]
    lib.ou_link_get_stats.restype = None

    lib.ou_link_sm3_hmac16.argtypes = [u8p, u8p, ctypes.c_size_t, u8p]
    lib.ou_link_sm3_hmac16.restype = None

    lib.ou_link_sm3.argtypes = [u8p, ctypes.c_size_t, u8p]
    lib.ou_link_sm3.restype = None

    lib.ou_link_version.argtypes = []
    lib.ou_link_version.restype = ctypes.c_char_p


def available():
    """True when the wrapper library can be loaded."""
    try:
        _load_library()
        return True
    except SdkError:
        return False


def version():
    return _load_library().ou_link_version().decode("ascii")


def _u8buf(data):
    data = bytes(data)
    buf = (ctypes.c_uint8 * max(1, len(data)))()
    if data:
        ctypes.memmove(buf, data, len(data))
    return buf


def sdk_sm3_hmac16(key, msg):
    """HMAC-SM3(key, msg) truncated to 16 bytes, computed by ou_sdk itself."""
    lib = _load_library()
    out = (ctypes.c_uint8 * 16)()
    lib.ou_link_sm3_hmac16(_u8buf(key), _u8buf(msg), len(msg), out)
    return bytes(bytearray(out))


def sdk_sm3(msg):
    """SM3(msg), 32 bytes, computed by ou_sdk itself."""
    lib = _load_library()
    out = (ctypes.c_uint8 * 32)()
    lib.ou_link_sm3(_u8buf(msg), len(msg), out)
    return bytes(bytearray(out))


# ---------------------------------------------------------------------------
# Live diagnostics view
# ---------------------------------------------------------------------------

class _DiagView(Mapping):
    """Mapping that reads the C stat counters on every access.

    The dashboard snapshots diagnostics with ``dict(self.diag)``; a plain dict
    would freeze at the first read, so this stays live and behaves like the
    dict that ou_crypto.SerialShell.enable_diag() returns.
    """

    def __init__(self, shell):
        self._shell = shell

    def _raw(self):
        return self._shell.stats()

    def __getitem__(self, key):
        return self._raw()[key]

    def __iter__(self):
        return iter(self._raw())

    def __len__(self):
        return len(self._raw())

    def __repr__(self):
        return "diag(%r)" % (self._raw(),)


class _TxView(object):
    """Mirrors the ``shell.tx`` handle the host tools use for --start-seq."""

    def __init__(self, shell):
        self._shell = shell

    @property
    def tx_seq(self):
        return _load_library().ou_link_tx_sequence(self._shell.handle)

    @tx_seq.setter
    def tx_seq(self, value):
        _load_library().ou_link_set_start_seq(self._shell.handle, int(value) & 0xFFFFFFFF)


# ---------------------------------------------------------------------------
# The shell
# ---------------------------------------------------------------------------

class SdkShell(object):
    """ou_sdk 0.4.1 backed shell, API-compatible with ou_crypto.SerialShell."""

    def __init__(self, key=None, side="board"):
        self.side = SIDE_FC if side == "fc" else SIDE_BOARD
        self.handle = None
        self.tx = _TxView(self)
        self.diag = None
        if key is not None:
            self.init(key)

    # -- lifecycle ----------------------------------------------------------
    def init(self, key):
        key = bytes(key)
        if len(key) != 16:
            raise SdkError("key must be 16 bytes, got %u" % len(key))
        lib = _load_library()
        if self.handle:
            lib.ou_link_destroy(self.handle)
        self.handle = lib.ou_link_create(_u8buf(key), self.side)
        if not self.handle:
            raise SdkError("ou_link_create failed")

    def close(self):
        if self.handle:
            _load_library().ou_link_destroy(self.handle)
            self.handle = None

    def __del__(self):
        try:
            self.close()
        except Exception:                                       # noqa: BLE001
            pass

    # -- crypto -------------------------------------------------------------
    def seal(self, plaintext_frame):
        """Wrap an outbound plaintext frame; b"" on failure."""
        lib = _load_library()
        frame = bytes(plaintext_frame)
        out = (ctypes.c_uint8 * MAX_SHELL)()
        written = lib.ou_link_seal(self.handle, _u8buf(frame), len(frame), out, MAX_SHELL)
        if not written:
            return b""
        return bytes(bytearray(out[:written]))

    def push(self, data):
        """Append raw bytes read from the link."""
        data = bytes(data)
        if data and self.handle:
            _load_library().ou_link_push(self.handle, _u8buf(data), len(data))

    def next(self):
        return self.next_pair()[1]

    def next_pair(self):
        """(sealed_wire_bytes, plaintext) for the next authentic frame."""
        if not self.handle:
            return b"", None
        lib = _load_library()
        plain = (ctypes.c_uint8 * MAX_PLAIN)()
        wire = (ctypes.c_uint8 * MAX_SHELL)()
        plain_len = ctypes.c_size_t(0)
        wire_len = ctypes.c_size_t(0)
        got = lib.ou_link_next(self.handle, plain, MAX_PLAIN, ctypes.byref(plain_len),
                               wire, MAX_SHELL, ctypes.byref(wire_len))
        if not got:
            return b"", None
        return (bytes(bytearray(wire[:wire_len.value])),
                bytes(bytearray(plain[:plain_len.value])))

    def reset_receiver(self):
        if self.handle:
            _load_library().ou_link_reset_receiver(self.handle)

    # -- diagnostics --------------------------------------------------------
    def enable_diag(self):
        """Live view of the SDK's frame counters (ok / auth_fail / replay / ...).

        ou_sdk's ``open()`` returns an opaque failure, so ``auth_fail`` is
        re-derived with the SDK's own ``sm3_hmac``; ``replay`` vs ``unpad_fail``
        splits the remainder using a mirror of the accepted-seq window.
        """
        self.diag = _DiagView(self)
        return self.diag

    def stats(self):
        if not self.handle:
            return {}
        raw = _Stats()
        _load_library().ou_link_get_stats(self.handle, ctypes.byref(raw))
        return {
            "ok": raw.frames_ok,
            "auth_fail": raw.auth_fail,
            "replay": raw.replay,
            "unpad_fail": raw.unpad_fail,
            "resync_bytes": raw.resync_bytes,
        }


# ---------------------------------------------------------------------------
# Self-check: does the SDK agree with the pure-Python reference implementation?
# ---------------------------------------------------------------------------

def self_test(verbose=False):
    sys.path.insert(0, _HERE)
    import ou_crypto as ou

    checks = 0
    key = ou.K_SERIAL_DEV_PLACEHOLDER

    def check(cond, what):
        nonlocal checks
        checks += 1
        if verbose:
            print("  %-52s %s" % (what, "ok" if cond else "FAIL"))
        assert cond, what

    check(version().startswith("ou_sdk_wrapper"), "wrapper version reports itself")
    check(len(sdk_sm3(b"abc")) == 32, "sm3 returns 32 bytes")
    check(sdk_sm3(b"abc") == ou.sm3(b"abc"), "sm3(b'abc') matches the Python core")

    # The dashboard key fingerprint must survive the trip through the SDK.
    check(sdk_sm3_hmac16(key, b"ou-dashboard") == ou.sm3_hmac(key, b"ou-dashboard"),
          "HMAC-SM3 fingerprint matches the Python core")

    # Cross-implementation round trips: SDK seals -> Python opens, and back.
    golden = [
        bytes.fromhex("aa5504045001000304"),
        bytes.fromhex("aa5504341340e201000000003f000080be000040400000003e000000be"
                      "0000003f00002041000020c1000048410000003f000000bf0000803e"),
    ]
    sdk = SdkShell(key)
    py_board = ou.ShellCrypto(key, ou.FlowId.BOARD_TO_FC)     # what the FC's rx expects
    py_fc = ou.ShellCrypto(key, ou.FlowId.FC_TO_BOARD)        # what the FC's tx emits
    for frame in golden:
        sealed = sdk.seal(frame)
        check(len(sealed) == ou.shell_frame_size(frame[3] + 1), "seal sizes the shell frame")
        check(py_board.open(sealed) == frame, "Python opens an SDK-sealed frame")
        py_sealed = py_fc.seal(frame)
        sdk.push(py_sealed)
        check(sdk.next() == frame, "SDK opens a Python-sealed frame")

    # Direction and tamper handling.
    wrong_dir = SdkShell(key)
    wrong_dir.push(ou.ShellCrypto(key, ou.FlowId.BOARD_TO_FC).seal(golden[0]))
    check(wrong_dir.next() is None, "a frame from the wrong direction is rejected")

    bad = bytearray(ou.ShellCrypto(key, ou.FlowId.FC_TO_BOARD).seal(golden[0]))
    bad[-1] ^= 0x01
    tampered = SdkShell(key)
    tampered.push(bytes(bad))
    check(tampered.next() is None, "a tampered tag is rejected")
    check(tampered.stats()["auth_fail"] == 1, "the tamper is classified as auth_fail")

    # Junk before a good frame must resync instead of stalling.
    resyncing = SdkShell(key)
    resyncing.push(b"\x00\xaa\x11\x55\x42")
    resyncing.push(ou.ShellCrypto(key, ou.FlowId.FC_TO_BOARD).seal(golden[0]))
    check(resyncing.next() == golden[0], "resync skips junk and finds the frame")
    check(resyncing.stats()["resync_bytes"] > 0, "resync bytes are accounted")

    # --start-seq must accept the wall-clock sized seqs this repo's bench seeds
    # (Tools/ou_bench.py:initial_start_seq adds a day per session on top of a
    # timestamp) -- instantly, not one SM4+HMAC pass per skipped seq. This is
    # the case that a re-sealing implementation cannot do at all.
    resumed = SdkShell(key)
    wanted = 1792378051
    started = time.monotonic()
    resumed.tx.tx_seq = wanted
    elapsed = time.monotonic() - started
    check(resumed.tx.tx_seq == wanted, "bench-sized --start-seq is accepted")
    check(elapsed < 0.5, "it is not O(seq) (took %.4f s)" % elapsed)
    check(resumed.seal(golden[0])[4:8] == struct.pack(">I", wanted),
          "the next frame carries that seq")
    check(ou.ShellCrypto(key, ou.FlowId.BOARD_TO_FC).open(
        resumed.seal(golden[0])) == golden[0],
        "the reference implementation opens a bench-sized-seq frame")

    # Diagnostics view behaves like the dict the dashboard snapshots.
    diag = SdkShell(key).enable_diag()
    check(dict(diag).get("auth_fail") == 0, "diag snapshots as a dict")
    check("resync_bytes" in dict(diag), "diag exposes the dashboard's keys")

    return checks


def main(argv):
    if "--self-test" in argv:
        print("ou_sdk 0.4.1 bridge: %s" % version())
        count = self_test(verbose=True)
        print("ou_sdk_bridge self-test: %u checks passed" % count)
        return 0
    print(version())
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
