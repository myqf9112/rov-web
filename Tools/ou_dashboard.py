#!/usr/bin/env python3
"""
OU v0.4 bench dashboard -- decrypted telemetry in a web browser.

Purpose
-------
A read-only-by-default front end for a bench link (Pixhawk <-> USB-TTL <-> PC),
so the sealed OU v0.4 traffic is visible as plain values instead of hex dumps.
It reuses the byte-exact codec in Tools/ou_crypto.py, so nothing about the
protocol changes here: this file only decodes, counts and paints.

What it shows
-------------
  * One card per message type with the decrypted fields (units applied), the
    raw decoded dict, and the message rate.
  * Link health: good/bad frames, MAC failures, anti-replay drops, resync
    bytes -- i.e. the reasons a frame silently disappears.
  * A rolling log of the last sealed/plaintext frames in hex (RX and TX).
  * Safe downlink: SET_STREAM and heartbeat are always allowed; ARM / SET_MODE
    / SET_PWM / GO_HOME / ManualControl need --allow-control.

Examples
--------
    # Bench PC, Pixhawk TELEM1 at 115200 on COM5 (Windows) or /dev/ttyUSB0
    python3 Tools/ou_dashboard.py --port /dev/ttyUSB0 --baud 115200

    # Same against SITL, no hardware at all
    python3 Tools/ou_dashboard.py --port tcp:127.0.0.1:8001

    # Unlock the control buttons (ARM/PWM); read the safety notes first
    python3 Tools/ou_dashboard.py --port COM5 --baud 115200 --allow-control

Then open http://127.0.0.1:8770/ .
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import webbrowser
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))

import ou_serial_test as ou                                              # noqa: E402
from ou_crypto import sm3_hmac                                          # noqa: E402

DASH = "\u2014"          # em dash: "no data"
HEXLOG_LEN = 14
LOG_LEN = 400
RATE_WINDOW = 3.0

STATE_NAMES = {
    ou.SYSTEMSTATE_UNINIT: "UNINIT 未初始化",
    ou.SYSTEMSTATE_BOOT: "BOOT 启动中",
    ou.SYSTEMSTATE_CALIBRATING: "CALIBRATING 校准中",
    ou.SYSTEMSTATE_STANDBY: "STANDBY 待命",
    ou.SYSTEMSTATE_ARMED: "ARMED 已解锁",
    ou.SYSTEMSTATE_ACTIVE: "ACTIVE 运行中",
    ou.SYSTEMSTATE_CRITICAL: "CRITICAL 临界",
    ou.SYSTEMSTATE_EMERGENCY: "EMERGENCY 紧急",
}

MODE_NAMES = {
    ou.MODE_MANUAL: "MANUAL",
    ou.MODE_AUTO: "AUTO",
    ou.MODE_RETURN: "RETURN",
    ou.MODE_HOLD: "HOLD",
}

CMD_NAMES = {
    ou.CMD_SET_MODE: "SET_MODE",
    ou.CMD_ARM: "ARM",
    ou.CMD_GO_HOME: "GO_HOME",
    ou.CMD_SET_STREAM: "SET_STREAM",
    ou.CMD_SET_PWM: "SET_PWM",
}

FIX_NAMES = {
    0: "NO_GPS", 1: "NO_FIX", 2: "2D_FIX", 3: "3D_FIX",
    4: "DGPS", 5: "RTK_FLOAT", 6: "RTK_FIXED", 7: "STATIC", 8: "PPP",
}

STREAM_NAMES = {
    ou.TYPE_GPSRAWINT: "GpsRawInt",
    ou.TYPE_RCCHANNELS: "RcChannels",
    ou.TYPE_SERVOOUTPUTRAW: "ServoOutputRaw",
}


# ---------------------------------------------------------------------------
# Field formatters
# ---------------------------------------------------------------------------

def _auto(value):
    """Render a decoded value with no explicit formatter."""
    if isinstance(value, (list, tuple)):
        return "[" + ", ".join(_auto(item) for item in value) + "]"
    if isinstance(value, bytes):
        return value.rstrip(b"\x00").decode("ascii", "replace")
    if isinstance(value, float):
        return "%.4f" % value
    return str(value)


def _enum(names):
    def fmt(value, _decoded):
        if value is None:
            return DASH
        return "%s (%s)" % (names.get(value, "?"), value)
    return fmt


def _num(scale=1.0, decimals=0, unit="", unknown=()):
    def fmt(value, _decoded):
        if value is None or value in unknown:
            return DASH
        text = "%.*f" % (decimals, value * scale)
        return text + (" " + unit if unit else "")
    return fmt


def _hex(prefix=True):
    def fmt(value, _decoded):
        if value is None:
            return DASH
        return ("0x%X" if prefix else "%X") % value
    return fmt


def _bits(mask_names):
    def fmt(value, _decoded):
        if value is None:
            return DASH
        set_names = [name for bit, name in sorted(mask_names.items()) if value & bit]
        return "%s [%s]" % (_hex()(value, _decoded), ", ".join(set_names) or "none")
    return fmt


def _deg(decimals=2):
    return _num(57.29577951308232, decimals, "°")


def _latlon():
    def fmt(value, _decoded):
        if value is None:
            return DASH
        return "%.7f" % (value * 1e-7)
    return fmt


def _text():
    def fmt(value, _decoded):
        if isinstance(value, bytes):
            value = value.rstrip(b"\x00").decode("ascii", "replace")
        return str(value) if value is not None else DASH
    return fmt


def _command_names():
    def fmt(value, _decoded):
        if value is None:
            return DASH
        return "%s (%s)" % (CMD_NAMES.get(value, "?"), value)
    return fmt


def _cmd_param(decoded):
    command = decoded.get("command")
    param = decoded.get("param")
    if param is None:
        return None
    if command == ou.CMD_SET_STREAM:
        target = (param >> 16) & 0xFF
        on = "on" if param & 1 else "off"
        return "type=0x%02X (%s) %s" % (target, STREAM_NAMES.get(target, "?"), on)
    if command == ou.CMD_SET_PWM:
        return "channel=%u pwm=%u µs" % ((param >> 16) & 0xFFFF, param & 0xFFFF)
    if command == ou.CMD_SET_MODE:
        return "mode=%s" % MODE_NAMES.get(param & 0xFFFF, param & 0xFFFF)
    return "0x%X" % param


def _cmd_param_field():
    def fmt(value, decoded):
        text = _cmd_param(decoded)
        return text if text is not None else _auto(value)
    return fmt


def _ack_result(value, _decoded):
    if value is None:
        return DASH
    return "%s (%s)" % (ou.ACK_NAMES.get(value, "?"), value)


# ---------------------------------------------------------------------------
# What each card shows: (title, [(field, label, formatter)], bars)
# bars = (field, label, low, high) drawn as horizontal bars.
# ---------------------------------------------------------------------------

VIEW = {
    ou.TYPE_HEARTBEAT: ("Heartbeat 心跳", [
        ("system_state", "系统状态", _enum(STATE_NAMES)),
        ("mode", "模式", _enum(MODE_NAMES)),
        ("fw_version", "固件版本", _num()),
        ("system_type", "系统类型 (bit0 role)", _num()),
    ], None),

    ou.TYPE_SYSSTATUS: ("SysStatus 电源", [
        ("voltage_total", "总电压", _num(0.001, 2, "V", unknown=(0xFFFF,))),
        ("voltage_cell_max", "最高电芯", _num(0.001, 2, "V", unknown=(0xFFFF,))),
        ("voltage_cell_min", "最低电芯", _num(0.001, 2, "V", unknown=(0xFFFF,))),
        ("current_battery", "电流", _num(0.01, 2, "A", unknown=(-1,))),
        ("battery_remaining", "剩余电量", _num(1, 0, "%", unknown=(-1,))),
        ("current_consumed", "已消耗", _num(unit="mAh", unknown=(-1,))),
        ("battery_temperature", "电池温度", _num(0.01, 1, "°C")),
        ("load", "CPU 负载", _num(0.1, 1, "%")),
        ("sensors_present", "sensors_present", _hex()),
        ("sensors_enabled", "sensors_enabled", _hex()),
        ("sensors_health", "sensors_health", _hex()),
        ("drop_rate_comm", "drop_rate_comm", _num(0.01, 2, "%")),
        ("errors_comm", "errors_comm", _num()),
        ("battery_fault_bitmask", "电池故障位", _hex()),
        ("stream_mask", "stream_mask", _bits({1: "GPS", 2: "RC", 4: "SERVO"})),
    ], None),

    ou.TYPE_POSENED: ("PoseNed 姿态/位置 (NED)", [
        ("roll", "roll", _deg()),
        ("pitch", "pitch", _deg()),
        ("yaw", "yaw", _deg()),
        ("rollspeed", "roll 角速度", _deg(2)),
        ("pitchspeed", "pitch 角速度", _deg(2)),
        ("yawspeed", "yaw 角速度", _deg(2)),
        ("x", "x 北", _num(1, 3, "m")),
        ("y", "y 东", _num(1, 3, "m")),
        ("z", "z 下", _num(1, 3, "m")),
        ("vx", "vx", _num(1, 3, "m/s")),
        ("vy", "vy", _num(1, 3, "m/s")),
        ("vz", "vz", _num(1, 3, "m/s")),
        ("time_boot_ms", "开机时间", _num(0.001, 2, "s")),
    ], None),

    ou.TYPE_VFRHUD: ("VfrHud 速度/高度", [
        ("airspeed", "空速", _num(1, 2, "m/s")),
        ("groundspeed", "地速", _num(1, 2, "m/s")),
        ("heading", "航向", _num(1, 0, "°", unknown=(0xFFFF,))),
        ("throttle", "油门", _num(1, 0, "%")),
        ("alt", "高度", _num(1, 2, "m")),
        ("climb", "爬升率", _num(1, 2, "m/s")),
    ], None),

    ou.TYPE_GLOBALPOSITIONINT: ("GlobalPositionInt 全局定位", [
        ("lat", "纬度", _latlon()),
        ("lon", "经度", _latlon()),
        ("alt", "海拔", _num(0.001, 2, "m")),
        ("relative_alt", "相对高度", _num(0.001, 2, "m")),
        ("vx", "vx", _num(0.01, 2, "m/s", unknown=(0xFFFF,))),
        ("vy", "vy", _num(0.01, 2, "m/s", unknown=(0xFFFF,))),
        ("vz", "vz", _num(0.01, 2, "m/s", unknown=(0xFFFF,))),
        ("hdg", "航向", _num(0.01, 2, "°", unknown=(0xFFFF,))),
        ("time_boot_ms", "开机时间", _num(0.001, 2, "s")),
    ], None),

    ou.TYPE_GPSRAWINT: ("GpsRawInt GNSS 原始", [
        ("fix_type", "定位类型", _enum(FIX_NAMES)),
        ("satellites_visible", "可见卫星", _num()),
        ("lat", "纬度", _latlon()),
        ("lon", "经度", _latlon()),
        ("alt", "海拔", _num(0.001, 2, "m")),
        ("eph", "水平精度", _num(0.01, 2, "m", unknown=(0xFFFF,))),
        ("epv", "垂直精度", _num(0.01, 2, "m", unknown=(0xFFFF,))),
        ("vel", "地速", _num(0.01, 2, "m/s", unknown=(0xFFFF,))),
        ("cog", "航迹向", _num(0.01, 2, "°", unknown=(0xFFFF,))),
        ("h_acc", "水平精度估计", _num(0.001, 3, "m")),
        ("v_acc", "垂直精度估计", _num(0.001, 3, "m")),
        ("vel_acc", "速度精度估计", _num(0.001, 3, "m/s")),
        ("hdg_acc", "航向精度估计", _num(0.001, 3, "°")),
        ("time_usec", "GNSS 时间", _num(0.001, 0, "ms")),
    ], None),

    ou.TYPE_WATERDEPTH: ("WaterDepth 水深", [
        ("id", "传感器 id", _num()),
        ("healthy", "healthy", _enum({0: "UNHEALTHY", 1: "OK"})),
        ("altitude", "altitude", _num(1, 3, "m")),
        ("bottom_distance", "bottom_distance", _num(1, 3, "m")),
        ("terrain_height", "terrain_height", _num(1, 3, "m")),
        ("temperature", "水温", _num(1, 2, "°C")),
        ("lat", "纬度", _latlon()),
        ("lng", "经度", _latlon()),
        ("time_boot_ms", "开机时间", _num(0.001, 2, "s")),
    ], None),

    ou.TYPE_DISTANCESENSOR: ("DistanceSensor 测距", [
        ("id", "id", _num()),
        ("type", "类型", _num()),
        ("orientation", "安装方向", _num()),
        ("current_distance", "当前距离", _num(unit="cm")),
        ("min_distance", "最小", _num(unit="cm")),
        ("max_distance", "最大", _num(unit="cm")),
        ("signal_quality", "信号质量", _num()),
        ("covariance", "covariance", _num()),
        ("horizontal_fov", "水平 FOV", _num(1, 2, "°")),
        ("vertical_fov", "垂直 FOV", _num(1, 2, "°")),
        ("time_boot_ms", "开机时间", _num(0.001, 2, "s")),
    ], None),

    ou.TYPE_EKFSTATUSREPORT: ("EkfStatusReport 滤波状态", [
        ("flags", "flags", _hex()),
        ("velocity_variance", "速度方差", _num(0.01, 2)),
        ("pos_horiz_variance", "水平位置方差", _num(0.01, 2)),
        ("pos_vert_variance", "垂直位置方差", _num(0.01, 2)),
        ("compass_variance", "磁罗盘方差", _num(0.01, 2)),
        ("terrain_alt_variance", "地形高度方差", _num(0.01, 2)),
    ], None),

    ou.TYPE_RCCHANNELS: ("RcChannels 遥控输入", [
        ("chancount", "通道数", _num()),
        ("rssi", "RSSI", _num()),
        ("time_boot_ms", "开机时间", _num(0.001, 2, "s")),
    ], ("chan_raw", "通道 1-18 (µs)", 800, 2200)),

    ou.TYPE_SERVOOUTPUTRAW: ("ServoOutputRaw 舵机输出", [
        ("port", "port", _num()),
        ("time_boot_ms", "开机时间", _num(0.001, 2, "s")),
    ], ("servo_raw", "输出 1-16 (µs)", 800, 2200)),

    ou.TYPE_MANUALCONTROL: ("ManualControl 手动控制", [
        ("sequence", "sequence", _num()),
        ("x", "x 前后", _num()),
        ("y", "y 左右", _num()),
        ("z", "z 升降", _num()),
        ("p", "p", _num()),
        ("r", "r", _num()),
        ("yaw", "yaw", _num()),
    ], None),

    ou.TYPE_COMMAND: ("Command 下行命令", [
        ("command", "命令", _command_names()),
        ("param", "参数", _cmd_param_field()),
    ], None),

    ou.TYPE_COMMANDACK: ("CommandAck 命令应答", [
        ("command", "对应命令", _command_names()),
        ("result", "结果", _ack_result),
        ("progress", "progress", _num()),
        ("result_param2", "result_param2", _num()),
    ], None),

    ou.TYPE_PARAMSET: ("ParamSet 参数写入", [
        ("param_id", "参数名", _text()),
        ("param_value", "值", _num(1, 6)),
        ("param_type", "类型", _num()),
    ], None),

    ou.TYPE_PARAMVALUE: ("ParamValue 参数回读", [
        ("param_id", "参数名", _text()),
        ("param_value", "值", _num(1, 6)),
        ("param_index", "序号", _num()),
        ("param_count", "总数", _num()),
        ("param_type", "类型", _num()),
    ], None),
}

PANEL_ORDER = [
    ou.TYPE_HEARTBEAT,
    ou.TYPE_SYSSTATUS,
    ou.TYPE_POSENED,
    ou.TYPE_VFRHUD,
    ou.TYPE_GLOBALPOSITIONINT,
    ou.TYPE_GPSRAWINT,
    ou.TYPE_WATERDEPTH,
    ou.TYPE_DISTANCESENSOR,
    ou.TYPE_EKFSTATUSREPORT,
    ou.TYPE_RCCHANNELS,
    ou.TYPE_SERVOOUTPUTRAW,
    ou.TYPE_COMMANDACK,
    ou.TYPE_PARAMVALUE,
]

# Fields whose value is a bit-level enum rather than a plain number.


# ---------------------------------------------------------------------------
# The bench link: transport + state + reader thread
# ---------------------------------------------------------------------------

class Bench(object):
    HEARTBEAT_PERIOD = 1.0
    SILENT_WARN_AFTER = 5.0

    def __init__(self, args):
        self.args = args
        self.decoder = getattr(args, "decoder", "python")
        self.key = ou.parse_key(args.key)
        self.fingerprint = sm3_hmac(self.key, b"ou-dashboard").hex()[:12]
        self.sdk_version = None
        if self.decoder == "sdk":
            # Fail loudly instead of silently falling back to the Python core:
            # the whole point of --decoder sdk is that the vendor SDK is the one
            # authenticating and decrypting the frames.
            import ou_sdk_bridge
            self.sdk_version = ou_sdk_bridge.version()
            sdk_fingerprint = ou_sdk_bridge.sdk_sm3_hmac16(
                self.key, b"ou-dashboard").hex()[:12]
            if sdk_fingerprint != self.fingerprint:
                raise RuntimeError(
                    "ou_sdk key fingerprint %s != reference %s: the two backends "
                    "disagree about the key or about SM3"
                    % (sdk_fingerprint, self.fingerprint))
        self.link = ou.OULink(args.port, args.baud, self.key,
                              verbose=False, start_seq=args.start_seq,
                              decoder=self.decoder)
        self.shell = self.link.shell
        self.diag = self.shell.enable_diag()
        self.allow_control = bool(args.allow_control)

        self.lock = threading.Lock()
        self.tx_lock = threading.Lock()
        self.stop = threading.Event()
        # All durations/rates use the monotonic clock: the realtime clock can be
        # stepped (NTP) under the tool's feet, which would truncate capture
        # windows and corrupt the Hz readout.
        self.start = time.monotonic()

        self.latest = {}                       # type -> decoded dict
        self.latest_ts = {}                    # type -> monotonic time
        self.history = {}                      # type -> deque of monotonic times
        self.counts = {}                       # type -> total frames received
        self.bad_frames = 0
        self.tx_counts = {}
        self.rx_bytes = 0
        self.frames = 0
        self.last_rx = None
        self.last_ack = None
        self.warned_no_ack = False
        self.heartbeat_on = not args.no_heartbeat
        self.last_heartbeat = 0.0
        self.warned_silent = False
        self.hexlog = deque(maxlen=HEXLOG_LEN)
        self.log = deque(maxlen=LOG_LEN)
        self.errors = {}                       # exception -> last text
        self.format_errors = set()             # (type, field) already reported

    # -- logging ------------------------------------------------------------
    def _stamp(self):
        """Wall-clock stamp for human-readable log lines (never for durations)."""
        when = time.time()
        return time.strftime("%H:%M:%S", time.localtime(when)) + ".%03u" % int(
            (when % 1) * 1000)

    def _log(self, level, text):
        line = "%s %-5s %s" % (self._stamp(), level, text)
        with self.lock:
            self.log.append(line)
        if level in ("ERROR", "WARN"):
            print(line)
            sys.stdout.flush()

    # -- transmit -----------------------------------------------------------
    def _send(self, frame_type, **fields):
        """Mirror of OULink.send(), but also records the sealed bytes."""
        frame = ou.encode_frame(frame_type, **fields)
        with self.tx_lock:
            sealed = self.shell.seal(frame)
            if not sealed:
                raise ValueError("seal failed for %s" % ou.TYPE_NAMES[frame_type])
            self.link.serial.write(sealed)
            self.link.serial.flush()
            self.tx_counts[frame_type] = self.tx_counts.get(frame_type, 0) + 1
        with self.lock:
            self.hexlog.append({
                "t": self._stamp(), "dir": "TX",
                "name": ou.TYPE_NAMES.get(frame_type, "0x%02X" % frame_type),
                "sealed": sealed.hex(), "plain": frame.hex(),
            })
        return frame

    def send_command(self, command, param):
        self._send(ou.TYPE_COMMAND, command=command, param=param & 0xFFFFFFFF)
        self._log("CMD", "TX %s param=%s" % (CMD_NAMES.get(command, command),
                                             _cmd_param({"command": command, "param": param})))
        result = self._wait_ack(command, self.args.ack_timeout)
        if result[0] is None and not self.warned_no_ack:
            self.warned_no_ack = True
            # Three different failures look identical from here, so name them.
            self._log("WARN", "%s 无 ack。按可能性排序：① 对端防重放窗口已越过本端 seq"
                              "（飞控没重启而工具重启过 → 用 --start-seq 抬高）；"
                              "② 对端根本没收/没回（密钥、方向）；"
                              "③ 固件 TX 缓冲满时静默丢帧（§8.1.3，控制命令需重发）。"
                              "界面上的『重同步丢弃字节/验签失败』都是 0 时，多为 ①。"
                              % CMD_NAMES.get(command, command))
        return result

    def _wait_ack(self, command, timeout):
        start = time.monotonic()
        deadline = start + timeout
        while time.monotonic() < deadline:
            time.sleep(0.02)
            ack = self.last_ack
            if ack and ack["command"] == command and ack["ts"] >= start:
                return ack["result"], ack["decoded"]
        return None, None

    # -- receive ------------------------------------------------------------
    def _pump(self):
        while not self.stop.is_set():
            self._maybe_heartbeat()
            self._check_silence()
            try:
                data = self.link.serial.read(4096)
            except Exception as exc:                                  # noqa: BLE001
                if self.errors.get("read") != str(exc):
                    self.errors["read"] = str(exc)
                    self._log("ERROR", "读取失败: %s" % exc)
                time.sleep(0.2)
                continue
            if data:
                self.rx_bytes += len(data)
                self.shell.push(data)
            drained = 0
            while True:
                sealed, frame = self.shell.next_pair()
                if frame is None:
                    break
                self._on_frame(frame, sealed)
                drained += 1
                if drained >= 256:
                    break
        self._log("INFO", "读取线程退出")

    def _on_frame(self, frame, sealed):
        frame_type, decoded = ou.decode_frame(frame)
        now = time.monotonic()
        if frame_type is None:
            self.bad_frames += 1
            self._log("WARN", "丢弃明文帧: %s | %s" % (decoded, frame.hex()))
            return
        self.frames += 1
        self.last_rx = now
        self.warned_silent = False
        if frame_type not in self.latest:
            self._log("INFO", "首次收到 %s (0x%02X)" % (ou.TYPE_NAMES[frame_type], frame_type))
        with self.lock:
            self.latest[frame_type] = decoded
            self.latest_ts[frame_type] = now
            self.counts[frame_type] = self.counts.get(frame_type, 0) + 1
            self.history.setdefault(frame_type, deque(maxlen=400)).append(now)
            self.hexlog.append({
                "t": self._stamp(), "dir": "RX",
                "name": ou.TYPE_NAMES[frame_type],
                "sealed": sealed.hex(), "plain": frame.hex(),
            })
        if frame_type == ou.TYPE_COMMANDACK:
            self.last_ack = {"command": decoded.get("command"), "result": decoded.get("result"),
                             "ts": now, "decoded": decoded}
            self._log("ACK", "CommandAck command=%s result=%s%s" % (
                CMD_NAMES.get(decoded.get("command"), decoded.get("command")),
                ou.ACK_NAMES.get(decoded.get("result"), decoded.get("result")),
                " progress=%u" % decoded.get("progress") if decoded.get("progress") else ""))
        elif frame_type == ou.TYPE_COMMAND:
            self._log("CMD", "RX Command %s param=%s" % (
                CMD_NAMES.get(decoded.get("command"), decoded.get("command")),
                _cmd_param(decoded)))

    def _maybe_heartbeat(self):
        if not self.heartbeat_on:
            return
        now = time.monotonic()
        if now - self.last_heartbeat < self.HEARTBEAT_PERIOD:
            return
        self.last_heartbeat = now
        try:
            self._send(ou.TYPE_HEARTBEAT, mode=ou.MODE_MANUAL, system_type=0x01,
                       fw_version=4, system_state=ou.SYSTEMSTATE_STANDBY)
        except Exception as exc:                                      # noqa: BLE001
            self._log("ERROR", "心跳发送失败: %s" % exc)

    def _check_silence(self):
        """The classic silent failure: TX is fine, nothing authentic comes back."""
        if self.warned_silent or self.last_rx is not None:
            return
        if time.monotonic() - self.start < self.SILENT_WARN_AFTER:
            return
        if not self.tx_counts.get(ou.TYPE_HEARTBEAT):
            return
        self.warned_silent = True
        self._log("WARN", "已发出心跳，但未收到任何合法帧。按顺序排查："
                          "① 波特率/线序；② SERIALx_PROTOCOL=49 且已重启；"
                          "③ 两端密钥一致；④ 若飞控未重启而本工具重启过，"
                          "用 --start-seq 抬高本端 seq（防重放窗口只接受严格递增）")

    # -- view model ---------------------------------------------------------
    def _panel(self, frame_type, now):
        decoded = self.latest.get(frame_type)
        spec = VIEW.get(frame_type)
        title = spec[0] if spec else ou.TYPE_NAMES.get(frame_type, "0x%02X" % frame_type)
        fields = spec[1] if spec else None
        bars_spec = spec[2] if spec else None
        rows = []
        if decoded is None:
            fields = fields or []
            for name, label, _fmt in fields:
                rows.append([label, DASH])
        else:
            if fields is None:
                fields = [(name, name, None) for name, _fmt, _count in ou.MESSAGES[frame_type][1]]
            for name, label, fmt in fields:
                value = decoded.get(name)
                try:
                    text = fmt(value, decoded) if fmt else _auto(value)
                except Exception as exc:                              # noqa: BLE001
                    # Never let a broken formatter blank a card in silence;
                    # --self-test is the place that is supposed to catch these.
                    key = (frame_type, name)
                    if key not in self.format_errors:
                        self.format_errors.add(key)
                        self._log("ERROR", "格式化失败 %s.%s: %s" % (
                            ou.TYPE_NAMES.get(frame_type, frame_type), name, exc))
                    text = _auto(value)
                rows.append([label, text])
            known = set(f[0] for f in fields)
            for name in decoded:
                if name not in known:
                    rows.append([name, _auto(decoded[name])])
        bars = None
        if bars_spec and decoded is not None:
            field, label, low, high = bars_spec
            values = list(decoded.get(field) or [])
            if values:
                bars = {"label": label, "low": low, "high": high,
                        "values": [[i + 1, int(v)] for i, v in enumerate(values)]}
        ts = self.latest_ts.get(frame_type)
        age = None if ts is None else now - ts
        hist = self.history.get(frame_type)
        rate = 0.0
        if hist:
            cutoff = now - RATE_WINDOW
            recent = [t for t in hist if t >= cutoff]
            rate = len(recent) / RATE_WINDOW
        return {
            "id": frame_type,
            "name": ou.TYPE_NAMES.get(frame_type, "0x%02X" % frame_type),
            "title": title,
            "age": age,
            "rate": round(rate, 2),
            "count": self.counts.get(frame_type, 0),
            "rows": rows,
            "bars": bars,
            "raw": json.dumps(decoded, default=_auto, sort_keys=False) if decoded is not None else None,
        }

    def state(self):
        now = time.monotonic()
        with self.lock:
            latest_ts = dict(self.latest_ts)
            hist = dict((t, list(d)) for t, d in self.history.items())
            hexlog = list(self.hexlog)
            log = list(self.log)
            bad_frames = self.bad_frames
            frames = self.frames
            rx_bytes = self.rx_bytes
            tx_counts = dict(self.tx_counts)
            diag = dict(self.diag)
            total_counts = dict(self.counts)
        panels = [self._panel(t, now) for t in PANEL_ORDER]
        for extra in sorted(t for t in latest_ts if t not in PANEL_ORDER):
            panels.append(self._panel(extra, now))

        last_rx = self.last_rx
        age = None if last_rx is None else round(now - last_rx, 1)
        notes = []
        if age is None:
            notes.append("尚未收到任何合法帧（见日志中的排查提示）")
        elif age > 3.0:
            notes.append("已 %.1f 秒没有收到帧：链路中断，或对端已停止发送" % age)
        if diag.get("auth_fail"):
            notes.append("验签失败 %u 次：两端密钥不一致，或流量不是本协议的 OU 帧"
                         % diag["auth_fail"])
        if diag.get("replay"):
            notes.append("防重放丢弃 %u 次：seq 未严格递增。对端重启后本工具需用 --start-seq 抬高"
                         % diag["replay"])
        if bad_frames:
            notes.append("明文帧解码失败 %u 次：外壳通过但载荷/长度不符（协议版本或类型不匹配）"
                         % bad_frames)

        counts = []
        for frame_type in sorted(set(list(hist) + list(tx_counts))):
            hist_list = hist.get(frame_type, [])
            cutoff = now - RATE_WINDOW
            recent = [t for t in hist_list if t >= cutoff]
            counts.append([
                ou.TYPE_NAMES.get(frame_type, "0x%02X" % frame_type),
                total_counts.get(frame_type, 0), round(len(recent) / RATE_WINDOW, 2),
                tx_counts.get(frame_type, 0),
            ])

        stats = [
            ["端口", self.args.port],
            ["运行时长", "%.0f s" % (now - self.start)],
            ["最近一帧", DASH if age is None else "%.1f s 前" % age],
            ["收到字节", str(rx_bytes)],
            ["合法帧", str(frames)],
            ["明文解码失败", str(bad_frames)],
            ["验签失败 (auth_fail)", str(diag.get("auth_fail", 0))],
            ["防重放丢弃 (replay)", str(diag.get("replay", 0))],
            ["解包失败 (unpad_fail)", str(diag.get("unpad_fail", 0))],
            ["重同步丢弃字节", str(diag.get("resync_bytes", 0))],
            ["密钥指纹 (SM3)", self.fingerprint],
            ["解密后端", "ou_sdk 0.4.1" if self.sdk_version else "Python 参考实现"],
            ["心跳下行", "开" if self.heartbeat_on else "关"],
            ["控制权限", "已解锁 (--allow-control)" if self.allow_control else "只读"],
        ]
        return {
            "link": {"port": self.args.port, "baud": self.args.baud,
                     "control": self.allow_control, "heartbeat": self.heartbeat_on,
                     "decoder": self.decoder, "sdk": self.sdk_version},
            "stats": stats,
            "panels": panels,
            "counts": counts,
            "hex": hexlog,
            "log": log,
            "notes": notes,
        }

    # -- snapshot mode -------------------------------------------------------
    def snapshot_html(self):
        """Self-contained HTML page with the current state baked in."""
        state = self.state()
        return PAGE.replace("const SNAPSHOT = null;",
                            "const SNAPSHOT = %s;" % json.dumps(state))

    def enable_startup_streams(self, spec):
        """Send CMD_SET_STREAM for each type in a comma-separated spec."""
        for token in spec.split(","):
            token = token.strip()
            if not token:
                continue
            try:
                target = int(token, 0)
            except ValueError:
                self._log("ERROR", "--stream: 无法解析 %r" % token)
                continue
            if target not in ou.STREAM_MASK:
                self._log("ERROR", "--stream: 0x%02X 不是可开流类型" % target)
                continue
            result, _decoded = self.send_command(ou.CMD_SET_STREAM, (target << 16) | 1)
            self._log("CMD", "%s %s" % (STREAM_NAMES.get(target, hex(target)),
                                        "ACCEPTED" if result == ou.ACK_ACCEPTED else
                                        ou.ACK_NAMES.get(result, "no ack")))

    # -- command API (called from HTTP handler threads) ----------------------
    CONTROL_ACTIONS = ("arm", "disarm", "go_home", "set_mode", "set_pwm", "manual_control")

    def api_command(self, request):
        action = request.get("action")
        if action in self.CONTROL_ACTIONS and not self.allow_control:
            return {"ok": False, "detail": "控制类命令需要在启动时加 --allow-control"}
        if action == "heartbeat":
            self.heartbeat_on = bool(request.get("on"))
            self._log("CMD", "心跳下行 %s" % ("开" if self.heartbeat_on else "关"))
            return {"ok": True, "detail": "heartbeat %s" % self.heartbeat_on}
        try:
            if action == "set_stream":
                target = int(request.get("type", 0))
                if target not in ou.STREAM_MASK:
                    return {"ok": False, "detail": "0x%02X 不是可开流类型" % target}
                on = bool(request.get("on"))
                result, _decoded = self.send_command(
                    ou.CMD_SET_STREAM, (target << 16) | (1 if on else 0))
                return {"ok": result == ou.ACK_ACCEPTED,
                        "detail": "%s %s" % (STREAM_NAMES.get(target, target),
                                             "on" if on else "off"),
                        "ack": None if result is None else ou.ACK_NAMES.get(result, result)}
            if action == "clear_stream":
                for target in ou.STREAM_MASK:
                    self.send_command(ou.CMD_SET_STREAM, target << 16)
                return {"ok": True, "detail": "所有可选流已关闭"}
            if action == "set_mode":
                result, _decoded = self.send_command(ou.CMD_SET_MODE, int(request.get("mode", 0)))
                return {"ok": result == ou.ACK_ACCEPTED, "detail": "SET_MODE",
                        "ack": None if result is None else ou.ACK_NAMES.get(result, result)}
            if action == "arm":
                result, _decoded = self.send_command(ou.CMD_ARM, 1)
                return {"ok": result == ou.ACK_ACCEPTED, "detail": "ARM",
                        "ack": None if result is None else ou.ACK_NAMES.get(result, result)}
            if action == "disarm":
                result, _decoded = self.send_command(ou.CMD_ARM, 0)
                return {"ok": result == ou.ACK_ACCEPTED, "detail": "DISARM",
                        "ack": None if result is None else ou.ACK_NAMES.get(result, result)}
            if action == "go_home":
                result, _decoded = self.send_command(ou.CMD_GO_HOME, 0)
                return {"ok": result == ou.ACK_ACCEPTED, "detail": "GO_HOME",
                        "ack": None if result is None else ou.ACK_NAMES.get(result, result)}
            if action == "set_pwm":
                channel = int(request.get("channel", 0)) & 0xFFFF
                pwm = int(request.get("pwm", 1500)) & 0xFFFF
                result, _decoded = self.send_command(ou.CMD_SET_PWM, (channel << 16) | pwm)
                return {"ok": result == ou.ACK_ACCEPTED,
                        "detail": "ch%u pwm%u" % (channel, pwm),
                        "ack": None if result is None else ou.ACK_NAMES.get(result, result)}
            if action == "manual_control":
                fields = dict((key, int(request.get(key, 0)))
                              for key in ("x", "y", "z", "p", "r", "yaw"))
                self._send(ou.TYPE_MANUALCONTROL, sequence=0, **fields)
                return {"ok": True, "detail": "ManualControl %s" % fields}
        except Exception as exc:                                      # noqa: BLE001
            self._log("ERROR", "命令失败 %s: %s" % (action, exc))
            return {"ok": False, "detail": str(exc)}
        return {"ok": False, "detail": "unknown action %r" % action}


# ---------------------------------------------------------------------------
# HTTP
# ---------------------------------------------------------------------------

class Handler(BaseHTTPRequestHandler):
    bench = None                        # set by main()
    server_version = "OUDashboard/1"

    def _reply(self, code, body, ctype):
        payload = body if isinstance(body, bytes) else body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self):                                             # noqa: N802
        path = self.path.split("?")[0]
        if path in ("/", "/index.html"):
            self._reply(200, PAGE, "text/html; charset=utf-8")
        elif path == "/api/state":
            self._reply(200, json.dumps(self.bench.state()), "application/json")
        else:
            self._reply(404, "not found", "text/plain; charset=utf-8")

    def do_POST(self):                                            # noqa: N802
        path = self.path.split("?")[0]
        if path != "/api/command":
            self._reply(404, "not found", "text/plain; charset=utf-8")
            return
        try:
            length = int(self.headers.get("Content-Length") or 0)
            request = json.loads(self.rfile.read(length) or b"{}")
            result = self.bench.api_command(request)
            self._reply(200 if result.get("ok") else 400, json.dumps(result),
                        "application/json")
        except Exception as exc:                                  # noqa: BLE001
            self._reply(500, json.dumps({"ok": False, "detail": str(exc)}), "application/json")

    def log_message(self, fmt, *args):
        pass


PAGE = r"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>OU v0.4 Dashboard</title>
<style>
:root { --bg:#0f1115; --fg:#e6e6e6; --dim:#8b93a1; --card:#171a21; --line:#252a34;
        --ok:#3ddc84; --warn:#ffb300; --bad:#ff5252; --acc:#4da3ff; }
* { box-sizing:border-box; }
body { margin:0; background:var(--bg); color:var(--fg); font:13px/1.45 ui-monospace,
       Menlo,Consolas,"DejaVu Sans Mono",monospace; }
header { display:flex; gap:10px; align-items:center; padding:9px 14px;
         border-bottom:1px solid var(--line); position:sticky; top:0; background:var(--bg);
         flex-wrap:wrap; z-index:2; }
h1 { font-size:15px; margin:0 8px 0 0; }
h2 { font-size:13px; margin:0 0 8px; color:var(--dim); }
.pill { padding:2px 9px; border-radius:10px; background:var(--card);
        border:1px solid var(--line); }
.pill.ok { color:var(--ok); } .pill.warn { color:var(--warn); } .pill.bad { color:var(--bad); }
.dim { color:var(--dim); }
main { padding:12px 14px 40px; display:grid; gap:12px; }
.grid2 { display:grid; gap:12px; grid-template-columns:minmax(320px,1fr) minmax(320px,1.4fr); }
@media (max-width:900px) { .grid2 { grid-template-columns:1fr; } }
.cards { display:grid; gap:10px; grid-template-columns:repeat(auto-fill,minmax(310px,1fr)); }
.card { background:var(--card); border:1px solid var(--line); border-radius:8px;
        padding:9px 11px; }
.card.stale { opacity:.4; }
.card h3 { margin:0 0 6px; font-size:12px; color:var(--acc); display:flex;
           justify-content:space-between; gap:8px; }
.card h3 span { color:var(--dim); font-weight:400; }
table { border-collapse:collapse; width:100%; }
td { padding:1px 0; vertical-align:top; }
td.k { color:var(--dim); padding-right:8px; }
td.v { text-align:right; white-space:nowrap; }
.bars { display:grid; gap:2px; margin-top:6px; }
.barrow { display:grid; grid-template-columns:44px 1fr 56px; gap:6px; align-items:center;
          font-size:11px; }
.bar { height:9px; background:#0b0d11; border:1px solid var(--line); position:relative; }
.bar i { position:absolute; left:0; top:0; bottom:0; background:var(--acc); }
pre { background:var(--card); border:1px solid var(--line); border-radius:8px; padding:8px;
      overflow:auto; max-height:300px; margin:0; font-size:12px; }
details { margin-top:6px; } summary { color:var(--dim); cursor:pointer; font-size:11px; }
button { background:#222936; color:var(--fg); border:1px solid var(--line);
         border-radius:6px; padding:4px 10px; cursor:pointer; font:inherit; }
button:hover { border-color:var(--acc); } button:disabled { opacity:.4; cursor:not-allowed; }
button.danger { border-color:#7a3030; }
label { display:inline-flex; gap:5px; align-items:center; margin:0 10px 6px 0; }
input { background:#0b0d11; color:var(--fg); border:1px solid var(--line);
        border-radius:6px; padding:3px 6px; width:74px; font:inherit; }
.row { display:flex; gap:10px; flex-wrap:wrap; align-items:center; }
.note { border-left:3px solid var(--warn); background:#1d1a12; padding:6px 10px;
        border-radius:4px; margin-bottom:6px; }
.note.err { border-color:var(--bad); background:#1f1416; }
#ack { color:var(--dim); }
</style>
</head>
<body>
<header>
  <h1>OU v0.4</h1>
  <span id="conn" class="pill">connecting…</span>
  <span id="link" class="dim"></span>
  <span id="age" class="dim"></span>
  <span id="notes"></span>
</header>
<main>
  <div class="grid2">
    <div><h2>链路健康</h2><div id="stats"></div>
         <h2 style="margin-top:12px">消息速率 / 计数</h2><div id="counts"></div></div>
    <div><h2>最近帧（sealed / plaintext hex）</h2><pre id="hex"></pre>
         <h2 style="margin-top:12px">事件日志</h2><pre id="log"></pre></div>
  </div>
  <div><h2>下发（安全区）</h2><div id="control"></div><div id="ack"></div></div>
  <h2>解密后的遥测</h2>
  <div id="cards" class="cards"></div>
</main>
<script>
"use strict";
const SNAPSHOT = null;
const $ = (id) => document.getElementById(id);
const esc = (s) => String(s).replace(/[&<>"]/g, (c) =>
  ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
let controlBuilt = false;
function table(pairs) {
  return "<table>" + pairs.map((p) =>
    "<tr>" + p.map((cell, i) =>
      "<td class='" + (i === 0 ? "k" : "v") + "'>" + esc(cell) + "</td>").join("") +
    "</tr>").join("") + "</table>";
}

function barsHtml(bars) {
  const span = bars.high - bars.low;
  return "<div class='bars'>" + bars.values.map((v) => {
    const pct = Math.max(0, Math.min(100, ((v[1] - bars.low) / span) * 100));
    return "<div class='barrow'><span class='dim'>ch" + v[0] + "</span>" +
      "<span class='bar'><i style='width:" + pct.toFixed(1) + "%'></i></span>" +
      "<span class='v'>" + v[1] + "</span></div>";
  }).join("") + "</div>";
}

function renderCards(panels) {
  $("cards").innerHTML = panels.map((p) => {
    const stale = (p.age === null || p.age > 3) ? " stale" : "";
    const meta = p.age === null ? "未收到" : p.rate.toFixed(1) + " Hz";
    const extra = p.raw === null ? "" :
      "<details><summary>raw JSON</summary><pre>" + esc(p.raw) + "</pre></details>";
    return "<div class='card" + stale + "'><h3>" + esc(p.title) +
      " <span>" + esc(meta) + "</span></h3>" + table(p.rows) +
      (p.bars ? barsHtml(p.bars) : "") + extra + "</div>";
  }).join("");
}

function renderScroll(el, text) {
  const atBottom = el.scrollTop + el.clientHeight >= el.scrollHeight - 12;
  el.textContent = text;
  if (atBottom) { el.scrollTop = el.scrollHeight; }
}

function render(s) {
  $("link").textContent = s.link.port + (s.link.baud ? " @" + s.link.baud : "") +
    (s.link.control ? "  [控制已解锁]" : "  [只读]");
  $("age").textContent = s.stats[2] ? "最近一帧 " + s.stats[2][1] : "";
  $("notes").innerHTML = s.notes.map((n) =>
    "<div class='note" + (n.indexOf("中断") >= 0 || n.indexOf("不一致") >= 0 ? " err" : "") +
    "'>" + esc(n) + "</div>").join("");
  $("stats").innerHTML = table(s.panels ? s.stats : []);
  $("counts").innerHTML = table([["消息", "RX", "Hz", "TX"]].concat(s.counts));
  renderCards(s.panels);
  renderScroll($("hex"), s.hex.map((h) =>
    h.t + " " + h.dir + " " + h.name + "\n  sealed: " + (h.sealed || "-") +
    "\n  plain : " + h.plain).join("\n\n"));
  renderScroll($("log"), s.log.join("\n"));
  if (!controlBuilt && !SNAPSHOT) { buildControl(s); controlBuilt = true; }
  if (SNAPSHOT) { $("control").innerHTML = "<span class='dim'>静态快照：下发按钮不可用</span>"; }
}

async function api(action, extra) {
  const body = Object.assign({ action: action }, extra || {});
  $("ack").textContent = "…";
  try {
    const r = await fetch("/api/command", { method: "POST", body: JSON.stringify(body) });
    const j = await r.json();
    let msg = (j.ok ? "OK" : "未确认") + ": " + (j.detail || "") ;
    if (j.ack) { msg += "  ack=" + j.ack; }
    else if (j.detail && j.detail.indexOf("需要") < 0) {
      msg += "  （超时没等到 CommandAck：先看事件日志，多为防重放 seq 未抬高 → 用 --start-seq）";
    }
    $("ack").textContent = msg;
  } catch (e) {
    $("ack").textContent = "请求失败: " + e;
  }
}

function buildControl(s) {
  const box = $("control");
  const streams = [[0x18, "GpsRawInt"], [0x1A, "RcChannels"], [0x1B, "ServoOutputRaw"]];
  let html = "<div class='row'>";
  streams.forEach(([t, name]) => {
    html += "<label><input type='checkbox' onchange=\"api('set_stream',{type:" + t +
      ",on:this.checked})\">" + name + "</label>";
  });
  html += "<label><input type='checkbox' id='hb' " +
    (s.link.heartbeat ? "checked" : "") +
    " onchange=\"api('heartbeat',{on:this.checked})\">心跳下行 1 Hz</label>";
  html += "</div>";
  if (s.link.control) {
    html += "<div class='row dim' style='margin:6px 0 2px'>控制类命令需要不接实体 RC 接收机，" +
      "否则固件恒返回 TEMPORARILY_REJECTED(1)。</div>";
    html += "<div class='row'>" +
      "<button class='danger' onclick=\"if(confirm('确认 ARM？'))api('arm')\">ARM</button>" +
      "<button onclick=\"api('disarm')\">DISARM</button>" +
      "<button onclick=\"api('go_home')\">GO_HOME</button>";
  }
  html += "</div>";
  if (s.link.control) {
    html += "<div class='row' style='margin-top:6px'>" +
      "<label>模式 <input id='mode' value='0'></label>" +
      "<button onclick=\"api('set_mode',{mode:+document.getElementById('mode').value})\">" +
      "SET_MODE</button>" +
      "<label>ch <input id='pwmch' value='3'></label>" +
      "<label>pwm <input id='pwm' value='1600'></label>" +
      "<button onclick=\"api('set_pwm',{channel:+document.getElementById('pwmch').value," +
      "pwm:+document.getElementById('pwm').value})\">SET_PWM</button></div>";
  }
  box.innerHTML = html;
}

async function tick() {
  try {
    const r = await fetch("/api/state");
    render(await r.json());
    $("conn").textContent = "web ok";
    $("conn").className = "pill ok";
  } catch (e) {
    $("conn").textContent = "HTTP 断开";
    $("conn").className = "pill bad";
  }
}
if (SNAPSHOT) {
  render(SNAPSHOT);
  $("conn").textContent = "静态快照（离线）";
  $("conn").className = "pill warn";
  document.title = "OU v0.4 Dashboard (snapshot)";
} else {
  tick();
  setInterval(tick, 400);
}
</script>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# Self-check: keep VIEW honest against the repo's message definitions
# ---------------------------------------------------------------------------

def self_check(verbose=True):
    """Validate every VIEW entry against ou_serial_test.MESSAGES.

    Catches the class of bug where a card silently falls back to a raw value:
    unknown field name, formatter with the wrong signature, or a message type
    that has no view at all.
    """
    checks = [0]

    def check(label, got, want):
        checks[0] += 1
        if got != want:
            raise AssertionError("%s:\n  got  %s\n  want %s" % (label, got, want))
        if verbose:
            print("  ok  %s" % label)

    check("PANEL_ORDER entries all have a view",
          [t for t in PANEL_ORDER if t not in VIEW], [])
    check("VIEW entries are real message types",
          [t for t in VIEW if t not in ou.MESSAGES], [])
    check("VIEW covers every message the firmware can send",
          sorted(t for t in ou.MESSAGES if t not in VIEW), [])

    for frame_type, (title, fields, bars) in sorted(VIEW.items()):
        name = ou.TYPE_NAMES.get(frame_type, hex(frame_type))
        declared = [field for field, _fmt, _count in ou.MESSAGES[frame_type][1]]
        check("%s: title set" % name, bool(title), True)
        for field, label, fmt in fields:
            check("%s.%s exists in MESSAGES" % (name, field), field in declared, True)
            check("%s.%s has a label" % (name, field), bool(label), True)
            if fmt is not None:
                # A formatter with the wrong arity used to degrade to a raw
                # number with no error; exercise it here instead.
                sample = _sample_value(frame_type, field)
                try:
                    text = fmt(sample, {field: sample})
                except Exception as exc:                              # noqa: BLE001
                    raise AssertionError("%s.%s formatter raised: %s" % (name, field, exc))
                check("%s.%s formats without falling back" % (name, field),
                      isinstance(text, str), True)
        if bars is not None:
            field = bars[0]
            check("%s bars field %s exists" % (name, field), field in declared, True)
            check("%s bars field %s is an array" % (name, field),
                  ou.MESSAGES[frame_type][1][declared.index(field)][2] > 1, True)
        # The generic fallback path must also work for every declared field.
        for field in declared:
            check("%s.%s auto-formats" % (name, field),
                  isinstance(_auto(_sample_value(frame_type, field)), str), True)

    # The page is HTML+JS living in a Python literal.  It can die silently in
    # two ways, both of which leave the browser stuck on the initial
    # "connecting…" pill with no data at all: the template stops being raw (so
    # Python eats the JS "\n" and the script becomes a syntax error), or a
    # </script> sneaks into the JS.  Neither is visible over HTTP -- the bytes
    # arrive fine, only the browser rejects them -- so check them here.
    check("page has exactly one script block", PAGE.count("<script>"), 1)
    check("page closes its script block exactly once", PAGE.count("</script>"), 1)
    check("page keeps JS escapes literal (PAGE must stay a raw string)",
          '"\\n  sealed: "' in PAGE, True)
    match = re.search(r"<script>(.*?)</script>", PAGE, re.S)
    js = match.group(1) if match else ""
    check("script block extracted", len(js) > 1000, True)
    node = shutil.which("node")
    if node:
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "page.js")
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(js)
            proc = subprocess.run([node, "--check", path], stdout=subprocess.PIPE,
                                  stderr=subprocess.STDOUT)
            if proc.returncode and verbose:
                print(proc.stdout.decode("utf-8", "replace"))
            check("page JS parses (node --check)", proc.returncode, 0)
    elif verbose:
        print("  --  node 不在，跳过真实 JS 语法校验")

    # The startup CMD_SET_STREAMs wait for a CommandAck (--ack-timeout each), so
    # sending them inline used to hold the HTTP server -- and therefore the page
    # that is supposed to explain the missing ack -- back by seconds per stream.
    sent = []

    class _BenchStub(object):
        def __init__(self):
            self.logs = []

        def enable_startup_streams(self, spec):
            sent.append(spec)

        def _log(self, level, text):
            self.logs.append((level, text))

    before = {t.name for t in threading.enumerate()}
    _enable_streams_async(_BenchStub(), None)
    check("no --stream starts no thread",
          {t.name for t in threading.enumerate()} == before, True)
    _enable_streams_async(_BenchStub(), "0x18")
    deadline = time.monotonic() + 3.0
    while time.monotonic() < deadline and not sent:
        time.sleep(0.05)
    check("--stream is sent off the main thread", sent, ["0x18"])
    check("the stream thread is a daemon (never holds the process open)",
          all(t.daemon for t in threading.enumerate() if t.name == "ou-streams"), True)

    class _DeadLink(object):
        def __init__(self):
            self.logs = []

        def enable_startup_streams(self, spec):
            raise BrokenPipeError(32, "Broken pipe")

        def _log(self, level, text):
            self.logs.append((level, text))

    dead = _DeadLink()
    _enable_streams_async(dead, "0x18")           # must not raise out of the thread
    deadline = time.monotonic() + 3.0
    while time.monotonic() < deadline and not dead.logs:
        time.sleep(0.05)
    check("a dead link while opening streams is logged, not raised",
          [level for level, _ in dead.logs], ["ERROR"])
    return checks[0]


def _sample_value(frame_type, field):
    """A plausible value for a field, used to exercise formatters."""
    for name, _fmt, count in ou.MESSAGES[frame_type][1]:
        if name != field:
            continue
        if count > 1:
            return [1500] * count
        if _fmt.endswith("s"):
            return b"TEST_PARAM"
        if _fmt == "f":
            return 1.25
        if _fmt == "h":
            return -1
        return 1
    return 0


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def _enable_streams_async(bench, spec):
    """Send the startup CMD_SET_STREAMs without blocking the caller.

    Each one waits up to --ack-timeout (3 s by default) for a CommandAck.  On a
    bench where nothing is acked -- wrong key, stale seq: the very cases this
    dashboard exists to diagnose -- that delay would keep the HTTP server (or
    the snapshot window) from starting, so the page carrying the "no ack"
    warning could not be opened.  The reader thread is already running, so any
    acks still land in the page log.
    """
    if not spec:
        return

    def worker():
        time.sleep(0.3)                 # let the link settle, as before
        try:
            bench.enable_startup_streams(spec)
        except Exception as exc:                                  # noqa: BLE001
            # Same as the heartbeat path: a link that dies mid-send is normal on
            # shutdown, and a raw traceback here would only be noise.
            bench._log("ERROR", "开流失败: %s" % exc)
    threading.Thread(target=worker, name="ou-streams", daemon=True).start()


def _run_snapshot(bench, args):
    """Capture for --snapshot-seconds, write the offline page, print a summary."""
    print("capturing %s for %.0f s ..." % (args.port, args.snapshot_seconds))
    _enable_streams_async(bench, args.stream)
    deadline = time.monotonic() + args.snapshot_seconds
    while time.monotonic() < deadline:
        time.sleep(0.2)
    html = bench.snapshot_html()
    with open(args.snapshot, "w", encoding="utf-8") as handle:
        handle.write(html)
    state = bench.state()
    print("")
    print("%-22s %8s %6s %6s  %s" % ("消息", "RX", "Hz", "TX", "首个字段"))
    for panel in state["panels"]:
        first = next((r for r in panel["rows"] if r[1] != DASH), None)
        print("%-22s %8d %6.2f %6d  %s" % (
            panel["name"], panel["count"], panel["rate"],
            bench.tx_counts.get(panel["id"], 0),
            ("%s = %s" % (first[0], first[1])) if first else "(未收到)"))
    print("")
    for label, value in state["stats"]:
        print("  %-24s %s" % (label, value))
    print("")
    print("snapshot: %s  (%.1f KB, 浏览器直接打开)" % (
        os.path.abspath(args.snapshot), len(html) / 1024.0))
    bench.stop.set()
    time.sleep(0.2)
    bench.link.close()
    return 0


def main():
    parser = argparse.ArgumentParser(
        description="OU v0.4 decrypted-telemetry dashboard (browser UI).")
    parser.add_argument("--port", default=None,
                        help="/dev/ttyUSB0, COM5, or tcp:HOST:PORT")
    parser.add_argument("--baud", type=int, default=115200,
                        help="serial baud; must match SERIALx_BAUD (kBaud x 1000)")
    parser.add_argument("--key", default=None,
                        help="16 ASCII chars or 32 hex digits (default: dev placeholder)")
    parser.add_argument("--start-seq", type=int, default=0,
                        help="first outbound seq (bump it when the FC did not reboot)")
    parser.add_argument("--decoder", choices=["python", "sdk"], default="sdk",
                        help="which implementation authenticates/decrypts the link: "
                             "'sdk' (ou_sdk 0.4.1 through Tools/ou_sdk_wrapper, "
                             "default; needs Linux/WSL) or 'python' (the "
                             "zero-dependency reference in Tools/ou_crypto.py). The "
                             "browser UI is identical either way.")
    parser.add_argument("--http-port", type=int, default=8770)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--allow-control", action="store_true",
                        help="unlock ARM / SET_MODE / SET_PWM / GO_HOME / ManualControl")
    parser.add_argument("--no-heartbeat", action="store_true",
                        help="do not send the 1 Hz heartbeat")
    parser.add_argument("--ack-timeout", type=float, default=3.0,
                        help="how long to wait for a CommandAck before reporting none")
    parser.add_argument("--stream", default=None,
                        help="comma-separated optional streams to enable at start, "
                             "e.g. 0x18,0x1a,0x1b")
    parser.add_argument("--snapshot", default=None, metavar="OUT.html",
                        help="capture for --snapshot-seconds then write a self-contained "
                             "offline HTML page (interface + real data) and exit")
    parser.add_argument("--snapshot-seconds", type=float, default=8.0)
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument("--self-test", action="store_true",
                        help="validate the view table against the repo's message "
                             "definitions and exit (no hardware needed)")
    args = parser.parse_args()

    if args.self_test:
        count = self_check(verbose=True)
        print("ou_dashboard self-test: %u checks passed" % count)
        return 0

    if not args.port:
        parser.error("--port is required (or use --self-test)")
    if args.host not in ("127.0.0.1", "localhost", "::1"):
        print("refusing to bind %s: OU frames are unauthenticated broadcast targets; "
              "use an SSH tunnel instead" % args.host)
        return 2
    if args.allow_control:
        print("*** --allow-control: ARM / SET_PWM are live. Unplug the RC receiver for "
              "control tests, and keep the props off. ***")

    try:
        bench = Bench(args)
    except ImportError as exc:
        print("需要 pyserial 才能打开真串口（pip install pyserial）：%s" % exc)
        return 2
    except OSError as exc:
        print("无法打开 %s：%s" % (args.port, exc))
        print("（tcp:HOST:PORT 需要 SITL 的 --serialN=tcp:PORT 已经在监听）")
        return 2
    except RuntimeError as exc:
        print("--decoder sdk 不可用：%s" % exc)
        print("先构建封装层：cmake -S Tools/ou_sdk_wrapper -B Tools/ou_sdk_wrapper/build "
              "-DOU_SDK_ROOT=<ou-sdk-0.4.1> && cmake --build Tools/ou_sdk_wrapper/build")
        return 2
    print("key fingerprint (SM3): %s" % bench.fingerprint)
    if bench.sdk_version:
        print("decoder: ou_sdk 0.4.1 — 验签/解密由厂商 SDK 完成 (%s)" % bench.sdk_version)
    else:
        print("decoder: python reference (Tools/ou_crypto.py)")
    thread = threading.Thread(target=bench._pump, name="ou-reader", daemon=True)
    thread.start()

    if args.snapshot:
        return _run_snapshot(bench, args)

    _enable_streams_async(bench, args.stream)
    time.sleep(0.2)

    Handler.bench = bench
    server = ThreadingHTTPServer((args.host, args.http_port), Handler)
    server.daemon_threads = True
    url = "http://%s:%u/" % (args.host, args.http_port)
    print("dashboard: %s  (Ctrl-C to stop)" % url)
    if not args.no_browser:
        threading.Thread(target=webbrowser.open, args=(url,), daemon=True).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("")
    finally:
        bench.stop.set()
        time.sleep(0.3)
        bench.link.close()
        print("frames: %s" % ", ".join(
            "%s=%u" % (ou.TYPE_NAMES.get(t, hex(t)), len(h))
            for t, h in sorted(bench.history.items())))
        print("valid=%u bad=%u diag=%s" % (bench.frames, bench.bad_frames, bench.diag))
    return 0


if __name__ == "__main__":
    sys.exit(main())
