"""
OU serial-link crypto shell -- dependency-free Python reference implementation.

This mirrors, byte-for-byte, the vendored core used by the flight controller:

    libraries/OU_Protocol/crypto/ou/crypto.hpp   (ou::crypto::ShellCrypto)
    libraries/OU_Protocol/crypto/crypto.cpp      (SM4 / SM3 / HMAC-SM3)
    libraries/OU_Protocol/crypto/ou_serial_shell.{h,cpp}  (stream assembler)

It exists so the SITL test suite and Tools/ou_serial_test.py can talk to a
v0.4 ArduSub firmware -- and so the RK3588 side has a readable, executable
statement of the wire format.

Wire format of one shell frame (replaces the plaintext frame on the link):

    AA55 | ver(1) | len(1) | seq(u32 BE) | IV(16) | E(body) | tag(16)

    len        = length of the plaintext body = inner_len + 1
                 where inner_len is the plaintext frame's own len byte
    body       = type(1) | payload(inner_len)
    E(body)    = SM4-CBC-PKCS#7(body), ciphertext_len(len) = 16*(len//16 + 1)
    tag        = HMAC-SM3(K_serial, MAC_INPUT)[:16]
    MAC_INPUT  = flow_id(1) | ver(1) | len(1) | seq(4 BE) | IV(16) | E(body)

Flow ids are NOT transmitted; both ends agree on them out of band.  For the
FC <-> board link: 0x03 = BoardToFc (frames the FC receives), 0x04 = FcToBoard
(frames the FC sends).  Because flow_id is part of MAC_INPUT, a frame captured
in one direction cannot be reflected back in the other direction.

No third-party packages are required; SM4 and SM3 are implemented here (GM/T
0002 / GM/T 0004).

Self-check against the C++ core's fixed-IV vectors:

    python3 Tools/ou_crypto.py
"""

from __future__ import print_function

import os
import struct
from enum import IntEnum

STX0 = 0xAA
STX1 = 0x55

PROTOCOL_VERSION = 0x04

BLOCK_SIZE = 16
IV_SIZE = 16
KEY_SIZE = 16
TAG_SIZE = 16

# AA55(2) + ver(1) + len(1) + seq(4) + IV(16)
SHELL_HEADER_SIZE = 2 + 1 + 1 + 4 + IV_SIZE

# Largest shell frame the FC can emit: 24 + ciphertext_len(53) + tag = 104.
MAX_SEALED_FRAME_SIZE = 24 + 64 + 16
# Receive accumulator bound: a shell frame may declare len=255 -> 296 bytes.
MAX_RECEIVE_FRAME_SIZE = 24 + 256 + 16

# Development placeholder for K_serial (libraries/OU_Protocol/OU_SerialKey.h).
# A production build defines OU_K_SERIAL_BURNED and burns a real key instead.
K_SERIAL_DEV_PLACEHOLDER = b"OU_SERIAL_KEY_01"

_MASK32 = 0xFFFFFFFF


class FlowId(IntEnum):
    """Implicit one-byte direction tag (never transmitted)."""

    HOST_TO_BOARD = 0x01
    BOARD_TO_HOST = 0x02
    BOARD_TO_FC = 0x03
    FC_TO_BOARD = 0x04


def ciphertext_len(len_byte):
    """Ciphertext bytes for a shell frame whose len byte is len_byte."""
    return BLOCK_SIZE * (len_byte // BLOCK_SIZE + 1)


def shell_frame_size(len_byte):
    """Total on-wire size of a shell frame declaring len=len_byte."""
    return SHELL_HEADER_SIZE + ciphertext_len(len_byte) + TAG_SIZE


# ---------------------------------------------------------------------------
# SM4 (GM/T 0002) -- 128-bit block cipher, big-endian words
# ---------------------------------------------------------------------------

_SM4_SBOX = (
    0xD6, 0x90, 0xE9, 0xFE, 0xCC, 0xE1, 0x3D, 0xB7, 0x16, 0xB6, 0x14, 0xC2, 0x28, 0xFB, 0x2C, 0x05,
    0x2B, 0x67, 0x9A, 0x76, 0x2A, 0xBE, 0x04, 0xC3, 0xAA, 0x44, 0x13, 0x26, 0x49, 0x86, 0x06, 0x99,
    0x9C, 0x42, 0x50, 0xF4, 0x91, 0xEF, 0x98, 0x7A, 0x33, 0x54, 0x0B, 0x43, 0xED, 0xCF, 0xAC, 0x62,
    0xE4, 0xB3, 0x1C, 0xA9, 0xC9, 0x08, 0xE8, 0x95, 0x80, 0xDF, 0x94, 0xFA, 0x75, 0x8F, 0x3F, 0xA6,
    0x47, 0x07, 0xA7, 0xFC, 0xF3, 0x73, 0x17, 0xBA, 0x83, 0x59, 0x3C, 0x19, 0xE6, 0x85, 0x4F, 0xA8,
    0x68, 0x6B, 0x81, 0xB2, 0x71, 0x64, 0xDA, 0x8B, 0xF8, 0xEB, 0x0F, 0x4B, 0x70, 0x56, 0x9D, 0x35,
    0x1E, 0x24, 0x0E, 0x5E, 0x63, 0x58, 0xD1, 0xA2, 0x25, 0x22, 0x7C, 0x3B, 0x01, 0x21, 0x78, 0x87,
    0xD4, 0x00, 0x46, 0x57, 0x9F, 0xD3, 0x27, 0x52, 0x4C, 0x36, 0x02, 0xE7, 0xA0, 0xC4, 0xC8, 0x9E,
    0xEA, 0xBF, 0x8A, 0xD2, 0x40, 0xC7, 0x38, 0xB5, 0xA3, 0xF7, 0xF2, 0xCE, 0xF9, 0x61, 0x15, 0xA1,
    0xE0, 0xAE, 0x5D, 0xA4, 0x9B, 0x34, 0x1A, 0x55, 0xAD, 0x93, 0x32, 0x30, 0xF5, 0x8C, 0xB1, 0xE3,
    0x1D, 0xF6, 0xE2, 0x2E, 0x82, 0x66, 0xCA, 0x60, 0xC0, 0x29, 0x23, 0xAB, 0x0D, 0x53, 0x4E, 0x6F,
    0xD5, 0xDB, 0x37, 0x45, 0xDE, 0xFD, 0x8E, 0x2F, 0x03, 0xFF, 0x6A, 0x72, 0x6D, 0x6C, 0x5B, 0x51,
    0x8D, 0x1B, 0xAF, 0x92, 0xBB, 0xDD, 0xBC, 0x7F, 0x11, 0xD9, 0x5C, 0x41, 0x1F, 0x10, 0x5A, 0xD8,
    0x0A, 0xC1, 0x31, 0x88, 0xA5, 0xCD, 0x7B, 0xBD, 0x2D, 0x74, 0xD0, 0x12, 0xB8, 0xE5, 0xB4, 0xB0,
    0x89, 0x69, 0x97, 0x4A, 0x0C, 0x96, 0x77, 0x7E, 0x65, 0xB9, 0xF1, 0x09, 0xC5, 0x6E, 0xC6, 0x84,
    0x18, 0xF0, 0x7D, 0xEC, 0x3A, 0xDC, 0x4D, 0x20, 0x79, 0xEE, 0x5F, 0x3E, 0xD7, 0xCB, 0x39, 0x48,
)

# System parameter FK (GM/T 0002).
_SM4_FK = (0xA3B1BAC6, 0x56AA3350, 0x677D9197, 0xB27022DC)

# Fixed parameter CK (GM/T 0002).
_SM4_CK = (
    0x00070E15, 0x1C232A31, 0x383F464D, 0x545B6269, 0x70777E85, 0x8C939AA1, 0xA8AFB6BD, 0xC4CBD2D9,
    0xE0E7EEF5, 0xFC030A11, 0x181F262D, 0x343B4249, 0x50575E65, 0x6C737A81, 0x888F969D, 0xA4ABB2B9,
    0xC0C7CED5, 0xDCE3EAF1, 0xF8FF060D, 0x141B2229, 0x30373E45, 0x4C535A61, 0x686F767D, 0x848B9299,
    0xA0A7AEB5, 0xBCC3CAD1, 0xD8DFE6ED, 0xF4FB0209, 0x10171E25, 0x2C333A41, 0x484F565D, 0x646B7279,
)


def _rotl32(x, n):
    n &= 31
    return ((x << n) | (x >> (32 - n))) & _MASK32


def _as_bytes(value, size, what):
    try:
        out = bytes(value)
    except TypeError:
        raise TypeError("%s must be bytes-like" % what)
    if len(out) != size:
        raise ValueError("%s must be %u bytes" % (what, size))
    return out


def _sm4_tau(x):
    return ((_SM4_SBOX[(x >> 24) & 0xFF] << 24) |
            (_SM4_SBOX[(x >> 16) & 0xFF] << 16) |
            (_SM4_SBOX[(x >> 8) & 0xFF] << 8) |
            _SM4_SBOX[x & 0xFF])


def _sm4_t(x):
    """Round transform L: x ^ (x<<<2) ^ (x<<<10) ^ (x<<<18) ^ (x<<<24)."""
    y = _sm4_tau(x)
    return y ^ _rotl32(y, 2) ^ _rotl32(y, 10) ^ _rotl32(y, 18) ^ _rotl32(y, 24)


def _sm4_t_prime(x):
    """Key-schedule transform L': x ^ (x<<<13) ^ (x<<<23)."""
    y = _sm4_tau(x)
    return y ^ _rotl32(y, 13) ^ _rotl32(y, 23)


def _sm4_round_keys(key):
    mk = list(struct.unpack(">4I", key))
    k = [mk[i] ^ _SM4_FK[i] for i in range(4)]
    rk = []
    for i in range(32):
        nxt = (k[i] ^ _sm4_t_prime(k[i + 1] ^ k[i + 2] ^ k[i + 3] ^ _SM4_CK[i])) & _MASK32
        k.append(nxt)
        rk.append(nxt)
    return rk


def _sm4_crypt(round_keys, block):
    x = list(struct.unpack(">4I", block))
    for i in range(32):
        x.append((x[i] ^ _sm4_t(x[i + 1] ^ x[i + 2] ^ x[i + 3] ^ round_keys[i])) & _MASK32)
    return struct.pack(">4I", x[35], x[34], x[33], x[32])


def sm4_encrypt_block(key, block):
    """Single-block SM4 encryption (key and block are 16 bytes)."""
    return _sm4_crypt(_sm4_round_keys(_as_bytes(key, KEY_SIZE, "key")),
                      _as_bytes(block, BLOCK_SIZE, "block"))


def sm4_decrypt_block(key, block):
    """Single-block SM4 decryption (key and block are 16 bytes)."""
    rk = _sm4_round_keys(_as_bytes(key, KEY_SIZE, "key"))
    rk.reverse()
    return _sm4_crypt(rk, _as_bytes(block, BLOCK_SIZE, "block"))


# ---------------------------------------------------------------------------
# SM3 (GM/T 0004) -- 256-bit hash
# ---------------------------------------------------------------------------

_SM3_IV = (0x7380166F, 0x4914B2B9, 0x172442D7, 0xDA8A0600,
           0xA96F30BC, 0x163138AA, 0xE38DEE4D, 0xB0FB0E4E)


def _sm3_p0(x):
    return x ^ _rotl32(x, 9) ^ _rotl32(x, 17)


def _sm3_p1(x):
    return x ^ _rotl32(x, 15) ^ _rotl32(x, 23)


def _sm3_compress(v, block):
    w = list(struct.unpack(">16I", block)) + [0] * 52
    for j in range(16, 68):
        w[j] = (_sm3_p1(w[j - 16] ^ w[j - 9] ^ _rotl32(w[j - 3], 15)) ^
                _rotl32(w[j - 13], 7) ^ w[j - 6]) & _MASK32
    w_prime = [w[j] ^ w[j + 4] for j in range(64)]

    a, b, c, d, e, f, g, h = v
    for j in range(64):
        if j < 16:
            ff = a ^ b ^ c
            gg = e ^ f ^ g
            tj = 0x79CC4519
        else:
            ff = (a & b) | (a & c) | (b & c)
            gg = (e & f) | ((~e & _MASK32) & g)
            tj = 0x7A879D8A
        ss1 = _rotl32((_rotl32(a, 12) + e + _rotl32(tj, j)) & _MASK32, 7)
        ss2 = ss1 ^ _rotl32(a, 12)
        tt1 = (ff + d + ss2 + w_prime[j]) & _MASK32
        tt2 = (gg + h + ss1 + w[j]) & _MASK32
        d = c
        c = _rotl32(b, 9)
        b = a
        a = tt1
        h = g
        g = _rotl32(f, 19)
        f = e
        e = _sm3_p0(tt2)

    return [a ^ v[0], b ^ v[1], c ^ v[2], d ^ v[3],
            e ^ v[4], f ^ v[5], g ^ v[6], h ^ v[7]]


def sm3(msg):
    """SM3 digest (32 bytes) of msg."""
    data = bytes(msg)
    bitlen = len(data) * 8
    padded = data + b"\x80"
    padded += b"\x00" * ((56 - len(padded) % 64) % 64)
    padded += struct.pack(">Q", bitlen)

    v = list(_SM3_IV)
    for off in range(0, len(padded), 64):
        v = _sm3_compress(v, padded[off:off + 64])
    return struct.pack(">8I", *v)


def sm3_hmac(key, msg):
    """HMAC-SM3 (RFC 2104), truncated to the 16-byte OU shell tag."""
    k = _as_bytes(key, KEY_SIZE, "key")
    if len(k) > 64:
        k = sm3(k)
    k = k + b"\x00" * (64 - len(k))
    ipad = bytes(byte ^ 0x36 for byte in k)
    opad = bytes(byte ^ 0x5C for byte in k)
    inner = sm3(ipad + bytes(msg))
    return sm3(opad + inner)[:TAG_SIZE]


# ---------------------------------------------------------------------------
# PKCS#7 + CBC
# ---------------------------------------------------------------------------

def pkcs7_pad(body):
    """PKCS#7 pad; always adds at least one byte (matches the C++ core)."""
    body = bytes(body)
    pad = BLOCK_SIZE - (len(body) % BLOCK_SIZE)
    return body + bytes(bytearray([pad])) * pad


def pkcs7_unpad(buf, expected_len):
    """Strip PKCS#7 padding and assert the stripped length; None on failure."""
    buf = bytes(buf)
    if not buf:
        return None
    pad = buf[-1]
    if pad == 0 or pad > BLOCK_SIZE or pad > len(buf):
        return None
    diff = 0
    for i in range(pad):
        diff |= buf[len(buf) - 1 - i] ^ pad
    if diff != 0:
        return None
    stripped = buf[:len(buf) - pad]
    if len(stripped) != expected_len:
        return None
    return stripped


def cbc_encrypt(key, iv, plaintext):
    """SM4-CBC encryption; plaintext length must be a multiple of 16."""
    if len(plaintext) % BLOCK_SIZE != 0:
        raise ValueError("plaintext must be a multiple of %u bytes" % BLOCK_SIZE)
    out = bytearray()
    prev = _as_bytes(iv, IV_SIZE, "iv")
    for off in range(0, len(plaintext), BLOCK_SIZE):
        blk = bytes(a ^ b for a, b in zip(plaintext[off:off + BLOCK_SIZE], prev))
        prev = sm4_encrypt_block(key, blk)
        out += prev
    return bytes(out)


def cbc_decrypt(key, iv, ciphertext):
    """SM4-CBC decryption; ciphertext length must be a multiple of 16."""
    if len(ciphertext) % BLOCK_SIZE != 0:
        raise ValueError("ciphertext must be a multiple of %u bytes" % BLOCK_SIZE)
    out = bytearray()
    prev = _as_bytes(iv, IV_SIZE, "iv")
    for off in range(0, len(ciphertext), BLOCK_SIZE):
        blk = ciphertext[off:off + BLOCK_SIZE]
        dec = sm4_decrypt_block(key, blk)
        out += bytes(a ^ b for a, b in zip(dec, prev))
        prev = blk
    return bytes(out)


def _constant_time_equal(a, b):
    a = bytes(a)
    b = bytes(b)
    if len(a) != len(b):
        return False
    diff = 0
    for x, y in zip(a, b):
        diff |= x ^ y
    return diff == 0


def _mac_input(flow, ver, length, seq, iv, ciphertext):
    """MAC_INPUT = flow_id | ver | len | seq(4 BE) | IV | ciphertext."""
    return (bytes(bytearray([int(flow) & 0xFF, ver & 0xFF, length & 0xFF])) +
            struct.pack(">I", seq & _MASK32) + bytes(iv) + bytes(ciphertext))


# ---------------------------------------------------------------------------
# Anti-replay
# ---------------------------------------------------------------------------

class ReplayWindow(object):
    """Per-flow monotonic sequence check (mirrors ou::crypto::ReplayWindow)."""

    def __init__(self):
        self.last_seq = 0
        self.ready = False

    def reset(self):
        self.last_seq = 0
        self.ready = False

    def accept(self, seq):
        if not self.ready:
            self.ready = True
            self.last_seq = seq
            return True
        if seq == self.last_seq:
            return False
        if seq > self.last_seq:
            self.last_seq = seq
            return True
        # A backward step is only a wrap/resync if it exceeds half the u32 space.
        delta = (self.last_seq - seq) & _MASK32
        if delta > 0x80000000:
            self.last_seq = seq
            return True
        return False


def default_iv_source():
    """Host CSPRNG IV source (the firmware injects a HAL RNG instead)."""
    return os.urandom(IV_SIZE)


# ---------------------------------------------------------------------------
# Shell codec, one direction
# ---------------------------------------------------------------------------

class ShellCrypto(object):
    """Seals/opens shell frames for a single flow direction.

    iv_source is a zero-argument callable returning 16 IV bytes; None selects
    the host CSPRNG.  For reproducible tests, pass a callable returning a fixed
    IV (see _fixed_iv in self_test()).
    """

    def __init__(self, key, flow, iv_source=None):
        self.key = _as_bytes(key, KEY_SIZE, "key")
        self.flow = FlowId(int(flow))
        self._iv_source = iv_source
        self.tx_seq = 0
        self.rx = ReplayWindow()
        # Optional outcome counters (None = off).  Purely additive bookkeeping
        # for the bench dashboard: enabling it changes no bytes on the wire and
        # no accept/reject decision.  See SerialShell.enable_diag().
        self.diag = None

    def _note(self, reason):
        if self.diag is not None:
            self.diag[reason] = self.diag.get(reason, 0) + 1

    def reset_receiver(self):
        self.rx.reset()

    def _next_iv(self):
        iv = default_iv_source() if self._iv_source is None else self._iv_source()
        return _as_bytes(iv, IV_SIZE, "iv")

    def seal(self, plaintext_frame):
        """Seal a plaintext frame (AA55|ver|len|type|payload); b'' on error."""
        frame = bytes(plaintext_frame)
        if len(frame) < 5 or frame[0] != STX0 or frame[1] != STX1:
            return b""
        ver = frame[2]
        inner_len = frame[3]
        if len(frame) != 5 + inner_len:
            return b""
        length = inner_len + 1
        if length > 0xFF:
            return b""

        body = frame[4:4 + length]
        seq = self.tx_seq
        self.tx_seq = (self.tx_seq + 1) & _MASK32
        iv = self._next_iv()

        ct = cbc_encrypt(self.key, iv, pkcs7_pad(body))
        tag = sm3_hmac(self.key, _mac_input(self.flow, ver, length, seq, iv, ct))

        return (bytes(bytearray([STX0, STX1, ver, length])) +
                struct.pack(">I", seq) + iv + ct + tag)

    def open(self, shell):
        """Authenticate/decrypt a shell frame; returns the plaintext frame or None."""
        shell = bytes(shell)
        if len(shell) < shell_frame_size(1):
            return None
        if shell[0] != STX0 or shell[1] != STX1:
            return None
        ver = shell[2]
        length = shell[3]
        if length == 0:
            return None
        seq = struct.unpack_from(">I", shell, 4)[0]
        iv = shell[8:8 + IV_SIZE]

        ct_len = ciphertext_len(length)
        if len(shell) != SHELL_HEADER_SIZE + ct_len + TAG_SIZE:
            return None
        ct = shell[SHELL_HEADER_SIZE:SHELL_HEADER_SIZE + ct_len]
        got_tag = shell[SHELL_HEADER_SIZE + ct_len:SHELL_HEADER_SIZE + ct_len + TAG_SIZE]

        # 1) MAC first (constant time); anything that fails is dropped silently.
        expect = sm3_hmac(self.key, _mac_input(self.flow, ver, length, seq, iv, ct))
        if not _constant_time_equal(got_tag, expect):
            self._note("auth_fail")
            return None

        # 2) Anti-replay only after the MAC checks out (no forged-frame DoS).
        if not self.rx.accept(seq):
            self._note("replay")
            return None

        # 3) Decrypt + unpad, asserting the stripped length equals len.
        body = pkcs7_unpad(cbc_decrypt(self.key, iv, ct), length)
        if body is None:
            self._note("unpad_fail")
            return None

        self._note("ok")
        # 4) Rebuild AA55 | ver | (len - 1) | type | payload
        return bytes(bytearray([STX0, STX1, ver, length - 1])) + body


# ---------------------------------------------------------------------------
# Stream assembler (byte-stream endpoint, either side of the FC link)
# ---------------------------------------------------------------------------

# Which end of the FC <-> board link this endpoint plays.
SIDE_BOARD = "board"  # we are the RK3588/host: tx=BoardToFc, rx=FcToBoard
SIDE_FC = "fc"        # we are the flight controller: tx=FcToBoard, rx=BoardToFc


# Client-side accumulator bound.  The firmware uses kMaxReceiveFrameSize (296 B)
# because it is an MCU that drains its accumulator on every update() call and
# only ever pushes small reads.  A host reading a socket can legitimately be
# handed a much larger chunk than that, so this mirror keeps a generous sanity
# bound and only falls back to drop-oldest resync beyond it -- otherwise a large
# recv() would discard every frame in it except the last one.
MAX_PENDING_BYTES = 64 * 1024


class SerialShell(object):
    """Byte-stream shell endpoint.

    side=SIDE_BOARD (default) is the client view: outbound frames carry
    FlowId.BOARD_TO_FC (what the FC's rx expects) and inbound frames are opened
    with FlowId.FC_TO_BOARD (what the FC's tx emits).  So a board-side
    SerialShell can drive an unmodified firmware.

    side=SIDE_FC mirrors OU::SerialShell's own direction assignment exactly.
    """

    def __init__(self, key=None, iv_source=None, side=SIDE_BOARD):
        self.side = side
        self.rx = None
        self.tx = None
        self.buf = bytearray()
        self.diag = None
        if key is not None:
            self.init(key, iv_source)

    def init(self, key, iv_source=None):
        if self.side == SIDE_FC:
            rx_flow, tx_flow = FlowId.BOARD_TO_FC, FlowId.FC_TO_BOARD
        else:
            rx_flow, tx_flow = FlowId.FC_TO_BOARD, FlowId.BOARD_TO_FC
        self.rx = ShellCrypto(key, rx_flow, iv_source)
        self.tx = ShellCrypto(key, tx_flow, iv_source)
        self.buf = bytearray()
        if self.diag is not None:
            self.rx.diag = self.diag
            self.tx.diag = self.diag

    def enable_diag(self):
        """Start recording decode outcomes; returns the counters dict.

        Keys: ok, auth_fail, replay, unpad_fail, resync_bytes.  Additive
        bookkeeping only -- no wire bytes and no accept/reject decision change.
        """
        self.diag = {}
        for crypto in (self.rx, self.tx):
            if crypto is not None:
                crypto.diag = self.diag
        return self.diag

    def _note(self, reason, count=1):
        if self.diag is not None:
            self.diag[reason] = self.diag.get(reason, 0) + count

    def seal(self, plaintext_frame):
        """Wrap an outbound plaintext frame for the peer."""
        return self.tx.seal(plaintext_frame)

    def push(self, data):
        """Append raw bytes read from the link.

        Bounded by MAX_PENDING_BYTES with a drop-oldest resync guard, so a
        pathological backlog degrades to resync instead of growing forever.
        """
        data = bytes(data)
        if not data:
            return
        if len(data) >= MAX_PENDING_BYTES:
            self.buf = bytearray(data[len(data) - MAX_PENDING_BYTES:])
            return
        if len(self.buf) + len(data) > MAX_PENDING_BYTES:
            drop = len(self.buf) + len(data) - MAX_PENDING_BYTES
            del self.buf[:drop]
        self.buf += data

    def next(self):
        """Extract the next authentic plaintext frame, or None."""
        return self.next_pair()[1]

    def next_pair(self):
        """Extract the next authentic frame as (sealed_wire_bytes, plaintext).

        Returns (b"", None) while no complete authentic frame is buffered.  The
        sealed bytes are exactly what arrived on the wire, which lets a bench
        tool show the byte-exact frame next to the decoded values.
        """
        if self.rx is None:
            return b"", None
        buf = self.buf
        while len(buf) >= 2:
            # Resync to the next AA55.
            start = 0
            while start + 1 < len(buf) and not (buf[start] == STX0 and buf[start + 1] == STX1):
                start += 1
            if start > 0:
                del buf[:start]
                self._note("resync_bytes", start)
            if len(buf) < SHELL_HEADER_SIZE:
                return b"", None

            length = buf[3]
            if length == 0:
                del buf[:1]
                self._note("resync_bytes")
                continue
            total = SHELL_HEADER_SIZE + ciphertext_len(length) + TAG_SIZE
            if len(buf) < total:
                return b"", None

            candidate = bytes(buf[:total])
            opened = self.rx.open(candidate)
            if opened is None:
                # Authentication/format failure: resync one byte and keep scanning.
                del buf[:1]
                self._note("resync_bytes")
                continue
            del buf[:total]
            return candidate, opened
        return b"", None

    def reset_receiver(self):
        if self.rx is not None:
            self.rx.reset_receiver()


# ---------------------------------------------------------------------------
# Self-check: GB/T vectors plus fixed-IV vectors dumped from the C++ core
# ---------------------------------------------------------------------------

_SM4_STD_KEY = bytes.fromhex("0123456789abcdeffedcba9876543210")
_SM4_STD_PT = bytes.fromhex("0123456789abcdeffedcba9876543210")
_SM4_STD_CT = bytes.fromhex("681edf34d206965e86b3e94f536e4246")

_FIXED_IV = bytes(bytearray(range(16)))


def _fixed_iv():
    return _FIXED_IV


# Fixed-IV shell vectors produced by a host build of
# libraries/OU_Protocol/crypto/crypto.cpp (see the header comment), so a
# regression in this file is caught here instead of on the wire.
_FIXED_IV_VECTORS = (
    # (label, flow, sequence, plaintext_frame_hex, shell_hex)
    ("BoardToFc seq=0 Command",
     FlowId.BOARD_TO_FC, 0, "AA55040632010003000000",
     "AA55040700000000000102030405060708090A0B0C0D0E0F262F16103529FB20C5A0C1E04C1CBA38"
     "6D5AA45945F0F20FA250CC64B651526E"),
    ("BoardToFc seq=1 Command",
     FlowId.BOARD_TO_FC, 1, "AA55040632010003000000",
     "AA55040700000001000102030405060708090A0B0C0D0E0F262F16103529FB20C5A0C1E04C1CBA38"
     "FB61DC1FBA5BC10C9D51A1CC94217E51"),
    ("BoardToFc seq=0 Heartbeat",
     FlowId.BOARD_TO_FC, 0, "AA5504045000000303",
     "AA55040500000000000102030405060708090A0B0C0D0E0FFB41352995D1D55448428E10D0170F55"
     "EC8BBCB03BBA6224915D033534CDD934"),
    ("BoardToFc seq=0 PoseNed(52)",
     FlowId.BOARD_TO_FC, 0, None,  # built programmatically below
     "AA55043500000000000102030405060708090A0B0C0D0E0FA9F392DB438788AF287172C293A38DF0"
     "6205BA70BD3DE0C63A4DDF62E37AF10B46BFECDE793F2BF7EFE880183155DFCCD565F0C8B96816CC4"
     "AC8AA84905B5296F6AFE8FEB3FBDA331BFF57B3413158A3"),
    ("FcToBoard seq=0 Heartbeat",
     FlowId.FC_TO_BOARD, 0, "AA5504045000000303",
     "AA55040500000000000102030405060708090A0B0C0D0E0FFB41352995D1D55448428E10D0170F55"
     "CFACDA8A69A11E0BA548BEFAFC101C29"),
    ("FcToBoard seq=1 Heartbeat",
     FlowId.FC_TO_BOARD, 1, "AA5504045000000303",
     "AA55040500000001000102030405060708090A0B0C0D0E0FFB41352995D1D55448428E10D0170F55"
     "1719858EB52B1719B797345D35289318"),
    ("BoardToFc seq=258 Heartbeat (seq BE beyond one byte)",
     FlowId.BOARD_TO_FC, 258, "AA5504045000000303",
     "AA55040500000102000102030405060708090A0B0C0D0E0FFB41352995D1D55448428E10D0170F55"
     "3EC8C8589806CD1AFB148EBE7EFA171F"),
)


def _posened_plaintext():
    """AA55|04|34|13|payload where payload[i] = (i*7 + 1) & 0xFF."""
    payload = bytes(bytearray(((i * 7 + 1) & 0xFF) for i in range(52)))
    return bytes(bytearray([STX0, STX1, 0x04, 0x34, 0x13])) + payload


def self_test(verbose=False):
    """Validate this port against GB/T vectors and the C++ core's vectors.

    Returns the number of checks performed; raises AssertionError on the first
    mismatch.
    """
    checks = [0]

    def check(label, got, want):
        checks[0] += 1
        if got != want:
            raise AssertionError("%s:\n  got  %s\n  want %s" % (label, got, want))
        if verbose:
            print("  ok  %s" % label)

    # --- SM4 (GB/T 32907) ---
    check("SM4 encrypt block (GB/T 32907)",
          sm4_encrypt_block(_SM4_STD_KEY, _SM4_STD_PT).hex().upper(),
          _SM4_STD_CT.hex().upper())
    check("SM4 decrypt block (GB/T 32907)",
          sm4_decrypt_block(_SM4_STD_KEY, _SM4_STD_CT).hex().upper(),
          _SM4_STD_PT.hex().upper())

    # --- SM3 (GB/T 32905) ---
    check('SM3("abc")',
          sm3(b"abc").hex().upper(),
          "66C7F0F462EEEDD9D1F2D46BDC10E4E24167C4875CF2F7A2297DA02B8F4BA8E0")
    check('SM3("")',
          sm3(b"").hex().upper(),
          "1AB21D8355CFA17F8E61194831E81A8F22BEC8C728FEFB747ED035EB5082AA2B")
    check('SM3("abcd"*16)',
          sm3(b"abcd" * 16).hex().upper(),
          "DEBE9FF92275B8A138604889C18E5A4D6FDB70E5387E5765293DCBA39C0C5732")

    # --- HMAC-SM3 (RFC 2104), fixed K_serial ---
    check("HMAC-SM3(K_serial, \"abc\")",
          sm3_hmac(K_SERIAL_DEV_PLACEHOLDER, b"abc").hex().upper(),
          "FBAC5D67A09D51AAD5BA838C9D7D6C90")
    check("HMAC-SM3(K_serial, \"\")",
          sm3_hmac(K_SERIAL_DEV_PLACEHOLDER, b"").hex().upper(),
          "5E1B8443F79FF03A58FE0F2C27B56AE2")

    # --- fixed-IV shell frames (byte-identical to the C++ core) ---
    for label, flow, seq, pt_hex, want_hex in _FIXED_IV_VECTORS:
        plaintext = _posened_plaintext() if pt_hex is None else bytes.fromhex(pt_hex)
        sealer = ShellCrypto(K_SERIAL_DEV_PLACEHOLDER, flow, _fixed_iv)
        got = b""
        for _ in range(seq + 1):
            got = sealer.seal(plaintext)
        check("seal %s" % label, got.hex().upper(), want_hex)

    # --- len semantics: shell len byte == payload_len + 1 ---
    check("shell len byte = payload_len + 1 (Command)",
          ShellCrypto(K_SERIAL_DEV_PLACEHOLDER, FlowId.BOARD_TO_FC,
                      _fixed_iv).seal(bytes.fromhex("AA55040632010003000000"))[3],
          7)
    check("shell size for len=255 (receive bound)",
          shell_frame_size(255), 296)
    check("max sealed frame size", MAX_SEALED_FRAME_SIZE, 104)

    # --- seal/open round-trip, both flows ---
    for flow in (FlowId.BOARD_TO_FC, FlowId.FC_TO_BOARD):
        tx = ShellCrypto(K_SERIAL_DEV_PLACEHOLDER, flow, _fixed_iv)
        rx = ShellCrypto(K_SERIAL_DEV_PLACEHOLDER, flow, _fixed_iv)
        plaintext = _posened_plaintext()
        opened = rx.open(tx.seal(plaintext))
        check("round-trip flow=0x%02X" % int(flow), opened, plaintext)

    # --- rejections ---
    tx = ShellCrypto(K_SERIAL_DEV_PLACEHOLDER, FlowId.BOARD_TO_FC, _fixed_iv)
    rx = ShellCrypto(K_SERIAL_DEV_PLACEHOLDER, FlowId.BOARD_TO_FC, _fixed_iv)
    frame = bytes.fromhex("AA5504045000000303")

    shell = bytearray(tx.seal(frame))
    shell[-1] ^= 0x01
    check("tampered tag rejected", rx.open(bytes(shell)), None)

    shell = bytearray(tx.seal(frame))
    shell[SHELL_HEADER_SIZE] ^= 0x80
    check("tampered ciphertext rejected", rx.open(bytes(shell)), None)

    shell = tx.seal(frame)
    check("truncated shell rejected", rx.open(shell[:-1]), None)

    # Wrong key must not authenticate.
    rx_wrong = ShellCrypto(b"OU_SERIAL_KEY_02", FlowId.BOARD_TO_FC, _fixed_iv)
    check("wrong key rejected", rx_wrong.open(shell), None)

    # Reflection: a frame sealed for the other direction must not open.
    tx_other = ShellCrypto(K_SERIAL_DEV_PLACEHOLDER, FlowId.FC_TO_BOARD, _fixed_iv)
    check("cross-direction reflection rejected",
          rx.open(tx_other.seal(frame)), None)

    # Anti-replay: the same seq twice must not open; a lower seq must not.
    rx2 = ShellCrypto(K_SERIAL_DEV_PLACEHOLDER, FlowId.BOARD_TO_FC, _fixed_iv)
    tx2 = ShellCrypto(K_SERIAL_DEV_PLACEHOLDER, FlowId.BOARD_TO_FC, _fixed_iv)
    first = tx2.seal(frame)
    second = tx2.seal(frame)
    check("replay: first accepted", rx2.open(first), frame)
    check("replay: duplicate seq rejected", rx2.open(first), None)
    check("replay: newer seq accepted", rx2.open(second), frame)

    # A backward step is only a resync when it exceeds half the u32 space.
    window = ReplayWindow()
    check("replay window accepts first", window.accept(100), True)
    check("replay window rejects backward step", window.accept(90), False)
    check("replay window rejects duplicate", window.accept(100), False)
    check("replay window accepts forward", window.accept(0xFFFFFFF0), True)
    check("replay window accepts u32 wrap/resync", window.accept(5), True)
    window.reset()
    check("replay window accepts after reset", window.accept(3), True)

    # --- SerialShell stream assembler (board side receiving FC telemetry) ---
    stream = SerialShell(K_SERIAL_DEV_PLACEHOLDER, _fixed_iv)
    fc = ShellCrypto(K_SERIAL_DEV_PLACEHOLDER, FlowId.FC_TO_BOARD, _fixed_iv)
    plaintext = _posened_plaintext()
    wire = b"\x00\xAA\x55garbage" + fc.seal(frame) + fc.seal(plaintext)
    for i in range(len(wire)):
        stream.push(wire[i:i + 1])
    check("stream: first frame", stream.next(), frame)
    check("stream: second frame", stream.next(), plaintext)
    check("stream: no more frames", stream.next(), None)

    # ... and a board-side sender must satisfy an FC-side receiver.
    fc_link = SerialShell(K_SERIAL_DEV_PLACEHOLDER, _fixed_iv, side=SIDE_FC)
    fc_link.push(stream.seal(frame))
    check("stream: board->fc direction", fc_link.next(), frame)

    # A socket read hands over many frames at once; that must not discard all
    # but the last kMaxReceiveFrameSize bytes (the firmware can push small
    # chunks, a host cannot control recv() granularity).
    burst = SerialShell(K_SERIAL_DEV_PLACEHOLDER, _fixed_iv)
    burst_tx = ShellCrypto(K_SERIAL_DEV_PLACEHOLDER, FlowId.FC_TO_BOARD, _fixed_iv)
    burst_len = 200
    burst.push(b"".join(burst_tx.seal(plaintext) for _ in range(burst_len)))
    recovered = 0
    while burst.next() is not None:
        recovered += 1
    check("stream: large push keeps every frame", recovered, burst_len)

    # next_pair() is next() plus the wire bytes, for bench tooling.
    pair = SerialShell(K_SERIAL_DEV_PLACEHOLDER, _fixed_iv)
    pair_tx = ShellCrypto(K_SERIAL_DEV_PLACEHOLDER, FlowId.FC_TO_BOARD, _fixed_iv)
    wire_frame = pair_tx.seal(frame)
    pair.push(b"\x00\xAA" + wire_frame)
    check("stream: next_pair returns wire bytes", pair.next_pair(), (wire_frame, frame))
    check("stream: next_pair drains the buffer", pair.next_pair(), (b"", None))

    # --- optional diagnostics counters (used by Tools/ou_dashboard.py) ---
    # Enabling them must not change any decision: the same frames are accepted
    # and rejected, only the reasons get counted.
    diag_link = SerialShell(K_SERIAL_DEV_PLACEHOLDER, _fixed_iv)
    counters = diag_link.enable_diag()
    diag_fc = ShellCrypto(K_SERIAL_DEV_PLACEHOLDER, FlowId.FC_TO_BOARD, _fixed_iv)
    good = diag_fc.seal(frame)

    diag_link.push(good)
    check("diag: good frame still opens", diag_link.next(), frame)
    check("diag: ok counted", counters.get("ok"), 1)

    diag_link.push(good)
    check("diag: duplicate still dropped", diag_link.next(), None)
    check("diag: replay counted", counters.get("replay"), 1)
    check("diag: replay resync bytes counted", counters.get("resync_bytes", 0) > 0, True)

    before = counters.get("resync_bytes", 0)
    tampered = bytearray(diag_fc.seal(frame))
    tampered[-1] ^= 0x01
    diag_link.push(bytes(tampered))
    check("diag: tampered frame still dropped", diag_link.next(), None)
    check("diag: auth_fail counted", counters.get("auth_fail", 0) >= 1, True)
    check("diag: auth_fail resync bytes counted",
          counters.get("resync_bytes", 0) > before, True)

    return checks[0]


if __name__ == "__main__":
    count = self_test(verbose=True)
    print("ou_crypto self-test: %u checks passed" % count)
