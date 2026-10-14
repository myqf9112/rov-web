#!/usr/bin/env python3
"""
OU host-protocol v0.4 bench/client tool.

Speaks the sealed OU v0.4 link (SM4-CBC + HMAC-SM3 shell, see
libraries/OU_Protocol/crypto/) over a serial port, and prints flight-controller
telemetry as JSON lines.  It is also the executable reference for the RK3588
side: message layouts here are cross-checked against
libraries/OU_Protocol/generated/ou_protocol.h and the golden frames in
libraries/OU_Protocol/tests/golden/golden.h.

Examples
--------
    # Validate codecs against the repo's golden vectors (no hardware needed)
    python3 Tools/ou_serial_test.py --self-test

    # Dump telemetry as JSON lines at 115200 on /dev/ttyUSB0
    python3 Tools/ou_serial_test.py --port /dev/ttyUSB0 --baud 115200 --listen

    # Same thing against SITL (--serial5=tcp:8000 on the SITL command line)
    python3 Tools/ou_serial_test.py --port tcp:127.0.0.1:8000 --listen --json

    # Arm, then spin up the GPS/RC/servo echoes
    python3 Tools/ou_serial_test.py --port /dev/ttyUSB0 --arm
    python3 Tools/ou_serial_test.py --port /dev/ttyUSB0 --set-stream 0x18,0x1a,0x1b

    # Production key (32 hex chars or 16 ASCII chars); defaults to the repo's
    # development placeholder K_serial = "OU_SERIAL_KEY_01"
    python3 Tools/ou_serial_test.py --port /dev/ttyUSB0 --key 00112233... --listen

Wire format
-----------
Plaintext frame:  AA 55 | ver(1)=0x04 | len(1) | type(1) | payload(len)
On the link it is replaced by the sealed shell:

    AA 55 | ver | len=payload_len+1 | seq(u32 BE) | IV(16) | E(type|payload) | tag(16)

See Tools/ou_crypto.py for the full shell description.

AP_FLAKE8_CLEAN
"""

from __future__ import print_function

import argparse
import json
import os
import re
import socket
import struct
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))

from ou_crypto import (  # noqa: E402
    K_SERIAL_DEV_PLACEHOLDER,
    KEY_SIZE,
    SerialShell,
    STX0,
    STX1,
    PROTOCOL_VERSION,
    self_test as crypto_self_test,
)

# ---------------------------------------------------------------------------
# Protocol constants (libraries/OU_Protocol/generated/ou_protocol.h)
# ---------------------------------------------------------------------------

TYPE_HEARTBEAT = 0x50
TYPE_SYSSTATUS = 0x10
TYPE_COMMANDACK = 0x51
TYPE_POSENED = 0x13
TYPE_EKFSTATUSREPORT = 0x14
TYPE_VFRHUD = 0x15
TYPE_GLOBALPOSITIONINT = 0x16
TYPE_GPSRAWINT = 0x18
TYPE_WATERDEPTH = 0x19
TYPE_DISTANCESENSOR = 0x52
TYPE_MANUALCONTROL = 0x30
TYPE_COMMAND = 0x32
TYPE_RCCHANNELS = 0x1A
TYPE_SERVOOUTPUTRAW = 0x1B
TYPE_PARAMSET = 0x33
TYPE_PARAMVALUE = 0x1D

MODE_MANUAL = 0
MODE_AUTO = 1
MODE_RETURN = 2
MODE_HOLD = 3

SYSTEMSTATE_UNINIT = 0
SYSTEMSTATE_BOOT = 1
SYSTEMSTATE_CALIBRATING = 2
SYSTEMSTATE_STANDBY = 3
SYSTEMSTATE_ARMED = 4
SYSTEMSTATE_ACTIVE = 5
SYSTEMSTATE_CRITICAL = 6
SYSTEMSTATE_EMERGENCY = 7

CMD_SET_MODE = 1
CMD_ARM = 2
CMD_GO_HOME = 4
CMD_SET_STREAM = 5
CMD_SET_PWM = 6

ACK_ACCEPTED = 0
ACK_TEMPORARILY_REJECTED = 1
ACK_DENIED = 2
ACK_UNSUPPORTED = 3
ACK_FAILED = 4
ACK_IN_PROGRESS = 5

ACK_NAMES = {
    ACK_ACCEPTED: "ACCEPTED",
    ACK_TEMPORARILY_REJECTED: "TEMPORARILY_REJECTED",
    ACK_DENIED: "DENIED",
    ACK_UNSUPPORTED: "UNSUPPORTED",
    ACK_FAILED: "FAILED",
    ACK_IN_PROGRESS: "IN_PROGRESS",
}

STREAM_MASK = {
    TYPE_GPSRAWINT: 1 << 0,
    TYPE_RCCHANNELS: 1 << 1,
    TYPE_SERVOOUTPUTRAW: 1 << 2,
}

# type -> (message name, [(field name, struct format, array count)])
# Fields are packed in declaration order, so offsets are cumulative.
MESSAGES = {
    TYPE_HEARTBEAT: ("Heartbeat", [
        ("mode", "B", 1),
        ("system_type", "B", 1),
        ("fw_version", "B", 1),
        ("system_state", "B", 1),
    ]),
    TYPE_SYSSTATUS: ("SysStatus", [
        ("sensors_present", "I", 1),
        ("sensors_enabled", "I", 1),
        ("sensors_health", "I", 1),
        ("load", "H", 1),
        ("voltage_total", "H", 1),
        ("voltage_cell_max", "H", 1),
        ("voltage_cell_min", "H", 1),
        ("current_battery", "h", 1),
        ("battery_remaining", "b", 1),
        ("current_consumed", "i", 1),
        ("battery_temperature", "h", 1),
        ("battery_fault_bitmask", "I", 1),
        ("drop_rate_comm", "H", 1),
        ("errors_comm", "H", 1),
        ("errors_count", "H", 4),
        ("stream_mask", "I", 1),
    ]),
    TYPE_COMMANDACK: ("CommandAck", [
        ("command", "H", 1),
        ("result", "B", 1),
        ("progress", "B", 1),
        ("result_param2", "i", 1),
    ]),
    TYPE_POSENED: ("PoseNed", [
        ("time_boot_ms", "I", 1),
        ("roll", "f", 1),
        ("pitch", "f", 1),
        ("yaw", "f", 1),
        ("rollspeed", "f", 1),
        ("pitchspeed", "f", 1),
        ("yawspeed", "f", 1),
        ("x", "f", 1),
        ("y", "f", 1),
        ("z", "f", 1),
        ("vx", "f", 1),
        ("vy", "f", 1),
        ("vz", "f", 1),
    ]),
    TYPE_EKFSTATUSREPORT: ("EkfStatusReport", [
        ("flags", "H", 1),
        ("velocity_variance", "B", 1),
        ("pos_horiz_variance", "B", 1),
        ("pos_vert_variance", "B", 1),
        ("compass_variance", "B", 1),
        ("terrain_alt_variance", "B", 1),
    ]),
    TYPE_VFRHUD: ("VfrHud", [
        ("airspeed", "f", 1),
        ("groundspeed", "f", 1),
        ("heading", "h", 1),
        ("throttle", "H", 1),
        ("alt", "f", 1),
        ("climb", "f", 1),
    ]),
    TYPE_GLOBALPOSITIONINT: ("GlobalPositionInt", [
        ("time_boot_ms", "I", 1),
        ("lat", "i", 1),
        ("lon", "i", 1),
        ("alt", "i", 1),
        ("relative_alt", "i", 1),
        ("vx", "h", 1),
        ("vy", "h", 1),
        ("vz", "h", 1),
        ("hdg", "H", 1),
    ]),
    TYPE_GPSRAWINT: ("GpsRawInt", [
        ("time_usec", "Q", 1),
        ("fix_type", "B", 1),
        ("lat", "i", 1),
        ("lon", "i", 1),
        ("alt", "i", 1),
        ("eph", "H", 1),
        ("epv", "H", 1),
        ("vel", "H", 1),
        ("cog", "H", 1),
        ("satellites_visible", "B", 1),
        ("h_acc", "I", 1),
        ("v_acc", "I", 1),
        ("vel_acc", "I", 1),
        ("hdg_acc", "I", 1),
    ]),
    TYPE_WATERDEPTH: ("WaterDepth", [
        ("time_boot_ms", "I", 1),
        ("id", "B", 1),
        ("healthy", "B", 1),
        ("lat", "i", 1),
        ("lng", "i", 1),
        ("altitude", "f", 1),
        ("bottom_distance", "f", 1),
        ("terrain_height", "f", 1),
        ("temperature", "f", 1),
    ]),
    TYPE_DISTANCESENSOR: ("DistanceSensor", [
        ("time_boot_ms", "I", 1),
        ("min_distance", "H", 1),
        ("max_distance", "H", 1),
        ("current_distance", "H", 1),
        ("type", "B", 1),
        ("id", "B", 1),
        ("orientation", "B", 1),
        ("covariance", "B", 1),
        ("horizontal_fov", "f", 1),
        ("vertical_fov", "f", 1),
        ("signal_quality", "B", 1),
    ]),
    TYPE_MANUALCONTROL: ("ManualControl", [
        ("sequence", "H", 1),
        ("x", "h", 1),
        ("y", "h", 1),
        ("z", "h", 1),
        ("p", "h", 1),
        ("r", "h", 1),
        ("yaw", "h", 1),
    ]),
    TYPE_COMMAND: ("Command", [
        ("command", "H", 1),
        ("param", "I", 1),
    ]),
    TYPE_RCCHANNELS: ("RcChannels", [
        ("time_boot_ms", "I", 1),
        ("chancount", "B", 1),
        ("chan_raw", "H", 18),
        ("rssi", "B", 1),
    ]),
    TYPE_SERVOOUTPUTRAW: ("ServoOutputRaw", [
        ("time_boot_ms", "I", 1),
        ("port", "B", 1),
        ("servo_raw", "H", 16),
    ]),
    TYPE_PARAMSET: ("ParamSet", [
        ("param_id", "16s", 1),
        ("param_value", "f", 1),
        ("param_type", "B", 1),
    ]),
    TYPE_PARAMVALUE: ("ParamValue", [
        ("param_id", "16s", 1),
        ("param_value", "f", 1),
        ("param_type", "B", 1),
        ("param_count", "H", 1),
        ("param_index", "H", 1),
    ]),
}

TYPE_NAMES = dict((t, info[0]) for t, info in MESSAGES.items())


def payload_size(frame_type):
    """Declared payload size of a message type."""
    total = 0
    for _name, fmt, count in MESSAGES[frame_type][1]:
        total += struct.calcsize("<" + fmt) * count
    return total


def _field_offsets(frame_type):
    offsets = []
    offset = 0
    for name, fmt, count in MESSAGES[frame_type][1]:
        offsets.append((name, offset, fmt, count))
        offset += struct.calcsize("<" + fmt) * count
    return offsets


def encode_frame(frame_type, **fields):
    """Build a plaintext OU frame (AA55|ver|len|type|payload)."""
    if frame_type not in MESSAGES:
        raise ValueError("unknown OU frame type 0x%02X" % frame_type)
    payload = bytearray()
    for name, _offset, fmt, count in _field_offsets(frame_type):
        if count > 1:
            values = fields.get(name, [0] * count)
            if len(values) != count:
                raise ValueError("%s needs %u values" % (name, count))
            for value in values:
                payload += struct.pack("<" + fmt, value)
        else:
            value = fields.get(name, 0)
            if fmt.endswith("s"):
                value = value.encode("ascii") if isinstance(value, str) else bytes(value)
                payload += value.ljust(struct.calcsize("<" + fmt), b"\x00")
            else:
                payload += struct.pack("<" + fmt, value)
    return (bytes(bytearray([STX0, STX1, PROTOCOL_VERSION, len(payload), frame_type])) +
            bytes(payload))


def decode_frame(frame):
    """Decode a plaintext OU frame; returns (type, dict) or (None, reason)."""
    frame = bytes(frame)
    if len(frame) < 5:
        return None, "short frame"
    if frame[0] != STX0 or frame[1] != STX1:
        return None, "bad STX"
    if frame[2] != PROTOCOL_VERSION:
        return None, "unsupported version 0x%02X" % frame[2]
    frame_type = frame[4]
    if frame_type not in MESSAGES:
        return None, "unknown type 0x%02X" % frame_type
    want = payload_size(frame_type)
    if frame[3] != want or len(frame) != want + 5:
        return None, "length mismatch (len byte %u, payload %u, got %u)" % (
            frame[3], want, len(frame))
    payload = frame[5:]
    out = {}
    for name, offset, fmt, count in _field_offsets(frame_type):
        if count > 1:
            out[name] = [struct.unpack_from("<" + fmt, payload, offset + i * struct.calcsize("<" + fmt))[0]
                         for i in range(count)]
        else:
            value = struct.unpack_from("<" + fmt, payload, offset)[0]
            if fmt.endswith("s"):
                value = value.rstrip(b"\x00")
            out[name] = value
    return frame_type, out


# ---------------------------------------------------------------------------
# Golden/header cross-checks
# ---------------------------------------------------------------------------

def _repo_path(*parts):
    root = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
    return os.path.join(root, *parts)


GENERATED_HEADER = _repo_path("libraries", "OU_Protocol", "generated", "ou_protocol.h")
GOLDEN_HEADER = _repo_path("libraries", "OU_Protocol", "tests", "golden", "golden.h")


def verify_generated_header():
    """Check every payload size in MESSAGES against the generated header."""
    checks = 0
    with open(GENERATED_HEADER) as handle:
        header = handle.read()
    sizes = {}
    for name, size in re.findall(r"#define OU_(\w+)_PAYLOAD_SIZE (\d+)", header):
        sizes[name] = int(size)
    type_to_name = {}
    for name, value in re.findall(r"#define OU_TYPE_(\w+) (0x[0-9A-Fa-f]+)", header):
        type_to_name[int(value, 16)] = name
    for frame_type, (name, _fields) in MESSAGES.items():
        assert frame_type in type_to_name, "type 0x%02X missing from generated header" % frame_type
        header_name = type_to_name[frame_type].upper()
        assert name.upper() == header_name, \
            "name mismatch for 0x%02X: %s vs %s" % (frame_type, name.upper(), header_name)
        declared = sizes.get(header_name)
        assert declared is not None, "no payload size for %s" % header_name
        assert payload_size(frame_type) == declared, \
            "%s payload size %u != generated %u" % (name, payload_size(frame_type), declared)
        checks += 1
    return checks


def verify_offsets():
    """Check derived field offsets against OU_<NAME>_<FIELD>_OFFSET macros."""
    checks = 0
    with open(GENERATED_HEADER) as handle:
        header = handle.read()
    offsets = {}
    for name, value in re.findall(r"#define OU_(\w+)_OFFSET (\d+)", header):
        offsets[name] = int(value)
    for frame_type, (msg, _fields) in MESSAGES.items():
        for name, offset, _fmt, count in _field_offsets(frame_type):
            if count > 1:
                continue  # only scalar fields have a single offset macro
            key = (msg + "_" + name).upper()
            if key in offsets:
                assert offsets[key] == offset, \
                    "%s.%s offset %u != generated %u" % (msg, name, offset, offsets[key])
                checks += 1
    return checks


def verify_golden_frames():
    """Decode and re-encode every golden frame; byte equality is the test."""
    checks = 0
    with open(GOLDEN_HEADER) as handle:
        golden = handle.read()
    pattern = re.compile(
        r"static const uint8_t OU_GOLDEN_(\w+)_FRAME\[[^\]]*\] = \{([^}]*)\};")
    found = pattern.findall(golden)
    assert len(found) == len(MESSAGES), \
        "golden header has %u frames, codec knows %u messages" % (len(found), len(MESSAGES))
    for name, body in found:
        raw = bytes(bytearray(int(byte, 16) for byte in re.findall(r"0x([0-9A-Fa-f]{2})", body)))
        frame_type, decoded = decode_frame(raw)
        assert frame_type is not None, "%s: %s" % (name, decoded)
        assert TYPE_NAMES[frame_type].upper() == name, \
            "%s decoded as %s" % (name, TYPE_NAMES[frame_type])
        reencoded = encode_frame(frame_type, **decoded)
        assert reencoded == raw, \
            "%s re-encode differs:\n  got  %s\n  want %s" % (
                name, reencoded.hex().upper(), raw.hex().upper())
        checks += 1
    return checks


def run_self_test(verbose=False):
    """Validate the crypto shell and the frame codec against repo references."""
    print("crypto shell vs C++ core:")
    crypto_checks = crypto_self_test(verbose)
    print("  %u crypto checks passed" % crypto_checks)

    codec_checks = 0
    for name, count in (("payload sizes vs generated header", verify_generated_header()),
                        ("field offsets vs generated header", verify_offsets()),
                        ("golden frames decode+re-encode", verify_golden_frames())):
        print("%s: %u checks passed" % (name, count))
        codec_checks += count

    # A sealed frame round-trip proves the codec and shell compose.
    shell = SerialShell(K_SERIAL_DEV_PLACEHOLDER)
    peer = SerialShell(K_SERIAL_DEV_PLACEHOLDER, side="fc")
    heartbeat = encode_frame(TYPE_HEARTBEAT, mode=MODE_MANUAL, system_type=0,
                             fw_version=4, system_state=SYSTEMSTATE_STANDBY)
    peer.push(shell.seal(heartbeat))
    assert peer.next() == heartbeat, "sealed heartbeat round-trip failed"
    peer_ack = encode_frame(TYPE_COMMANDACK, command=CMD_ARM, result=ACK_ACCEPTED,
                            progress=100, result_param2=0)
    shell.push(peer.seal(peer_ack))
    assert shell.next() == peer_ack, "sealed CommandAck round-trip failed"
    codec_checks += 2

    print("frame codec: %u checks passed" % codec_checks)
    print("TOTAL: %u checks passed" % (crypto_checks + codec_checks))
    return True


# ---------------------------------------------------------------------------
# JSON rendering
# ---------------------------------------------------------------------------

def jsonify(value):
    if isinstance(value, bytes):
        return value.rstrip(b"\x00").decode("ascii", "replace")
    if isinstance(value, dict):
        # ParamSet/ParamValue carry param_id as raw bytes; json.dumps would raise
        # on them, so recurse instead of only converting top-level values.
        return dict((key, jsonify(item)) for key, item in value.items())
    if isinstance(value, (list, tuple)):
        return [jsonify(item) for item in value]
    if isinstance(value, float):
        return round(value, 6)
    return value


def print_json(frame_type, decoded):
    record = {"msg": TYPE_NAMES[frame_type], "type": "0x%02X" % frame_type}
    record.update(dict((key, jsonify(value)) for key, value in decoded.items()))
    print(json.dumps(record, sort_keys=False))
    sys.stdout.flush()


def print_human(frame_type, decoded):
    name = TYPE_NAMES[frame_type]
    if frame_type == TYPE_HEARTBEAT:
        print("%-18s mode=%u state=%u fw=%u" % (name, decoded["mode"], decoded["system_state"],
                                                decoded["fw_version"]))
    elif frame_type == TYPE_SYSSTATUS:
        print("%-18s load=%.1f%% voltage=%umV remaining=%d%% stream_mask=0x%X" % (
            name, decoded["load"] / 10.0, decoded["voltage_total"],
            decoded["battery_remaining"], decoded["stream_mask"]))
    elif frame_type == TYPE_POSENED:
        print("%-18s roll=%.3f pitch=%.3f yaw=%.3f x=%.2f y=%.2f z=%.2f" % (
            name, decoded["roll"], decoded["pitch"], decoded["yaw"],
            decoded["x"], decoded["y"], decoded["z"]))
    elif frame_type == TYPE_WATERDEPTH:
        print("%-18s healthy=%u altitude=%.2f bottom_distance=%.2f temperature=%.2f" % (
            name, decoded["healthy"], decoded["altitude"],
            decoded["bottom_distance"], decoded["temperature"]))
    elif frame_type == TYPE_COMMANDACK:
        print("%-18s command=%u result=%s progress=%u" % (
            name, decoded["command"], ACK_NAMES.get(decoded["result"], decoded["result"]),
            decoded["progress"]))
    elif frame_type == TYPE_VFRHUD:
        print("%-18s alt=%.2f climb=%.2f groundspeed=%.2f" % (
            name, decoded["alt"], decoded["climb"], decoded["groundspeed"]))
    elif frame_type == TYPE_GLOBALPOSITIONINT:
        print("%-18s lat=%.7f lon=%.7f relative_alt=%.2f" % (
            name, decoded["lat"] * 1e-7, decoded["lon"] * 1e-7,
            decoded["relative_alt"] * 1e-3))
    elif frame_type == TYPE_PARAMVALUE:
        print("%-18s %s=%.6f" % (name, jsonify(decoded["param_id"]), decoded["param_value"]))
    else:
        print("%-18s %s" % (name, json.dumps(jsonify(decoded), sort_keys=True)))


# ---------------------------------------------------------------------------
# Link
# ---------------------------------------------------------------------------

class TcpSerial(object):
    """pyserial-shaped shim for a TCP endpoint (SITL's `--serialN=tcp:PORT`).

    SITL exposes a listening socket for the OU port; connecting to it as a
    client is exactly what an RK3588 (or any host) does over a USB-TTL pair.
    """

    def __init__(self, host, port, timeout=0.1):
        self.sock = socket.create_connection((host, port), timeout=5.0)
        self.sock.settimeout(timeout)
        # Every OU frame is small (56-104 B) and latency matters: without
        # NODELAY the Nagle/delayed-ACK pair can stall a CommandAck for tens of
        # milliseconds on a TCP bridge or on SITL's tcp: endpoints.
        try:
            self.sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        except OSError:
            pass

    def read(self, count):
        try:
            return self.sock.recv(count)
        except socket.timeout:
            return b""
        except OSError:
            return b""

    def write(self, data):
        self.sock.sendall(data)
        return len(data)

    def flush(self):
        pass

    def close(self):
        try:
            self.sock.close()
        except OSError:
            pass


def open_transport(port, baud):
    """Open a serial device path, or a `tcp:HOST:PORT` / `tcpclient:HOST:PORT`."""
    if port.startswith("tcp:") or port.startswith("tcpclient:"):
        host, _, port_str = port.split(":", 1)[1].rpartition(":")
        if not port_str.isdigit():
            raise SystemExit("--port tcp: expects tcp:HOST:PORT")
        return TcpSerial(host or "127.0.0.1", int(port_str))
    import serial  # pyserial; imported here so --self-test needs no deps
    return serial.Serial(port, baud, timeout=0.1)


def make_shell(key, decoder="python"):
    """Build the sealed shell for the requested crypto backend.

    "python" uses the zero-dependency reference implementation in
    Tools/ou_crypto.py. "sdk" routes every seal/open through ou_sdk 0.4.1 via
    Tools/ou_sdk_bridge.py, so the bytes on the wire are produced and accepted
    by the vendor SDK instead of our own implementation. The two backends are
    wire-compatible; picking one is a choice of which implementation you want to
    trust on this run.
    """
    if decoder == "sdk":
        from ou_sdk_bridge import SdkShell
        return SdkShell(key)
    if decoder != "python":
        raise ValueError("unknown decoder %r" % decoder)
    return SerialShell(key)


class OULink(object):
    """Sealed OU link over pyserial or a TCP socket."""

    HEARTBEAT_PERIOD = 1.0

    def __init__(self, port, baud, key, verbose=False, start_seq=0, decoder="python"):
        self.serial = open_transport(port, baud)
        self.shell = make_shell(key, decoder)
        # The peer only accepts strictly increasing seq per direction and never
        # resets that window except on its own reboot, so a host that restarts
        # must resume above the last seq it sent (see the reference doc).
        self.shell.tx.tx_seq = start_seq
        self.verbose = verbose
        self.last_heartbeat = 0.0
        self.counts = {}
        self.bad_frames = 0

    def close(self):
        self.serial.close()

    def send(self, frame_type, **fields):
        frame = encode_frame(frame_type, **fields)
        shell = self.shell.seal(frame)
        if not shell:
            raise ValueError("seal failed for %s" % TYPE_NAMES[frame_type])
        self.serial.write(shell)
        self.serial.flush()
        if self.verbose:
            print("tx %s %s" % (TYPE_NAMES[frame_type], json.dumps(jsonify(fields), sort_keys=True)))

    def maybe_heartbeat(self, enabled=True):
        if not enabled:
            return
        # Monotonic: a wall-clock step must not stall or burst the heartbeat.
        now = time.monotonic()
        if now - self.last_heartbeat >= self.HEARTBEAT_PERIOD:
            self.send(TYPE_HEARTBEAT, mode=MODE_MANUAL, system_type=0x01,
                      fw_version=4, system_state=SYSTEMSTATE_STANDBY)
            self.last_heartbeat = now

    def poll(self, timeout=None, heartbeat=True):
        """Yield (type, decoded) for every authentic frame that arrives."""
        deadline = None if timeout is None else time.monotonic() + timeout
        while True:
            if deadline is not None and time.monotonic() >= deadline:
                return
            self.maybe_heartbeat(heartbeat)
            data = self.serial.read(4096)
            if data:
                self.shell.push(data)
            drained = 0
            while True:
                frame = self.shell.next()
                if frame is None:
                    break
                frame_type, decoded = decode_frame(frame)
                if frame_type is None:
                    self.bad_frames += 1
                    if self.verbose:
                        print("dropped frame: %s" % decoded)
                    continue
                self.counts[frame_type] = self.counts.get(frame_type, 0) + 1
                yield frame_type, decoded
                drained += 1
                if drained >= 128:
                    break


def run_action(link, args):
    """Send the requested control frames and wait for their replies."""
    replies = []

    def wait_for(type_list, timeout=2.0):
        for frame_type, decoded in link.poll(timeout=timeout):
            if frame_type in type_list:
                return frame_type, decoded
        return None, None

    if args.set_stream:
        for token in args.set_stream.split(","):
            token = token.strip()
            if not token:
                continue
            target = int(token, 0)
            if target not in STREAM_MASK:
                raise SystemExit("--set-stream: 0x%02X is not a streamable type" % target)
            link.send(TYPE_COMMAND, command=CMD_SET_STREAM, param=(target << 16) | 1)
            kind, decoded = wait_for((TYPE_COMMANDACK,))
            replies.append((kind, decoded))

    if args.clear_stream:
        for token in args.clear_stream.split(","):
            token = token.strip()
            if not token:
                continue
            target = int(token, 0)
            link.send(TYPE_COMMAND, command=CMD_SET_STREAM, param=(target << 16))
            kind, decoded = wait_for((TYPE_COMMANDACK,))
            replies.append((kind, decoded))

    if args.mode is not None:
        link.send(TYPE_COMMAND, command=CMD_SET_MODE, param=args.mode & 0xFFFF)
        replies.append(wait_for((TYPE_COMMANDACK,)))

    if args.arm:
        link.send(TYPE_COMMAND, command=CMD_ARM, param=1)
        replies.append(wait_for((TYPE_COMMANDACK,)))

    if args.disarm:
        link.send(TYPE_COMMAND, command=CMD_ARM, param=0)
        replies.append(wait_for((TYPE_COMMANDACK,)))

    if args.go_home:
        link.send(TYPE_COMMAND, command=CMD_GO_HOME, param=0)
        replies.append(wait_for((TYPE_COMMANDACK,)))

    if args.set_pwm:
        for token in args.set_pwm.split(","):
            channel, _, pwm = token.partition(":")
            param = ((int(channel) & 0xFFFF) << 16) | (int(pwm) & 0xFFFF)
            link.send(TYPE_COMMAND, command=CMD_SET_PWM, param=param)
            replies.append(wait_for((TYPE_COMMANDACK,)))

    if args.param_set:
        for token in args.param_set.split(","):
            name, _, value = token.partition("=")
            link.send(TYPE_PARAMSET, param_id=name, param_value=float(value), param_type=0)
            replies.append(wait_for((TYPE_PARAMVALUE,)))

    failures = 0
    for kind, decoded in replies:
        if kind is None:
            print("ERROR: no reply for a control frame")
            print("       (the peer only accepts strictly increasing seq; if another "
                  "host process already opened this link, retry with --start-seq "
                  "above its last seq)")
            failures += 1
            continue
        if kind == TYPE_COMMANDACK:
            result = decoded["result"]
            if result != ACK_ACCEPTED:
                failures += 1
            print("%s command=%u result=%s%s" % (
                TYPE_NAMES[kind], decoded["command"],
                ACK_NAMES.get(result, result),
                " progress=%u" % decoded["progress"] if decoded["progress"] else ""))
        else:
            print("%s %s=%.6f" % (TYPE_NAMES[kind],
                                  jsonify(decoded["param_id"]), decoded["param_value"]))
    return failures


def listen(link, args):
    printers = print_json if args.json else print_human
    deadline = None if args.duration <= 0 else time.monotonic() + args.duration
    try:
        for frame_type, decoded in link.poll(timeout=None, heartbeat=not args.no_heartbeat):
            printers(frame_type, decoded)
            if deadline is not None and time.monotonic() >= deadline:
                break
    except KeyboardInterrupt:
        print("")
    print("frames: %s" % ", ".join(
        "%s=%u" % (TYPE_NAMES.get(t, hex(t)), c) for t, c in sorted(link.counts.items())))
    return 0


def parse_key(text):
    if text is None:
        return K_SERIAL_DEV_PLACEHOLDER
    text = text.strip()
    if re.match(r"^[0-9A-Fa-f]{32}$", text):
        return bytes(bytearray.fromhex(text))
    raw = text.encode("ascii")
    if len(raw) != KEY_SIZE:
        raise SystemExit("--key must be 16 ASCII characters or 32 hex digits")
    return raw


def main():
    parser = argparse.ArgumentParser(
        description="OU v0.4 host-protocol bench/client tool",
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--port", help="serial port (/dev/ttyUSB0) or a TCP endpoint "
                        "for SITL/bench (tcp:127.0.0.1:8000)")
    parser.add_argument("--baud", type=int, default=115200,
                        help="baud rate, ignored for tcp: ports (115200 or 230400 recommended)")
    parser.add_argument("--key", help="K_serial: 16 ASCII chars or 32 hex digits "
                                      "(default: repo development placeholder)")
    parser.add_argument("--self-test", action="store_true",
                        help="validate the codec against the repo's golden vectors and exit")
    parser.add_argument("--listen", action="store_true", help="print telemetry")
    parser.add_argument("--json", action="store_true", help="JSON lines instead of human-readable")
    parser.add_argument("--duration", type=float, default=0.0,
                        help="stop listening after N seconds (0 = forever)")
    parser.add_argument("--no-heartbeat", action="store_true",
                        help="do not send the 1 Hz Heartbeat keepalive")
    parser.add_argument("--start-seq", type=int, default=0,
                        help="first outgoing shell seq (the peer only accepts increasing "
                             "seq; a restarted host must resume above its last seq; default 0)")
    parser.add_argument("--decoder", choices=["python", "sdk"], default="sdk",
                        help="crypto backend: ou_sdk 0.4.1 via Tools/ou_sdk_wrapper "
                             "(default; needs Linux/WSL) or 'python' for the "
                             "zero-dependency reference implementation (see "
                             "Tools/ou_sdk_bridge.py)")
    parser.add_argument("--arm", action="store_true", help="send Command(CMD_ARM, 1)")
    parser.add_argument("--disarm", action="store_true", help="send Command(CMD_ARM, 0)")
    parser.add_argument("--go-home", action="store_true", help="send Command(CMD_GO_HOME)")
    parser.add_argument("--mode", type=int, choices=[MODE_MANUAL, MODE_AUTO, MODE_RETURN, MODE_HOLD],
                        help="send Command(CMD_SET_MODE): 0=MANUAL 1=AUTO 2=RETURN 3=HOLD")
    parser.add_argument("--set-stream", help="enable echoes: comma-separated types, e.g. 0x18,0x1a,0x1b")
    parser.add_argument("--clear-stream", help="disable echoes: comma-separated types")
    parser.add_argument("--set-pwm", help="set an output: comma-separated CHANNEL:PWM, e.g. 5:1500")
    parser.add_argument("--param-set", help="write a parameter: comma-separated NAME=VALUE")
    parser.add_argument("--verbose", action="store_true", help="log transmitted frames")
    args = parser.parse_args()

    if args.self_test:
        return 0 if run_self_test(args.verbose) else 1

    if not args.port:
        parser.error("--port is required (or use --self-test)")

    has_action = any([args.arm, args.disarm, args.go_home, args.mode is not None,
                      args.set_stream, args.clear_stream, args.set_pwm, args.param_set])

    key = parse_key(args.key)
    if key == K_SERIAL_DEV_PLACEHOLDER:
        print("warning: using the development placeholder K_serial; pass --key for a burned key",
              file=sys.stderr)

    link = OULink(args.port, args.baud, key, verbose=args.verbose, start_seq=args.start_seq,
                  decoder=args.decoder)
    failures = 0
    try:
        link.maybe_heartbeat(enabled=not args.no_heartbeat)
        if has_action:
            failures = run_action(link, args)
        if args.listen or not has_action:
            failures += listen(link, args)
    finally:
        link.close()
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
