#!/usr/bin/env python3
"""ou_bench.py -- one-click OU v0.4 bench launcher.

Typical use, from WSL (or any Linux box that can reach the FC's USB-TTL):

    python3 Tools/ou_bench.py

It does the whole bench dance for you:

  0. checks the ou_sdk 0.4.1 decrypt backend (the default) and builds the
     wrapper on the spot if OU_SDK_ROOT points at an extracted SDK tree,
  1. finds the USB-TTL COM port on the Windows side (skips the flight
     controller's own USB port that Mission Planner is using),
  2. probes the candidate baud rates and picks the one whose frames actually
     authenticate, so `SERIAL1_BAUD` being 57 instead of 115 does not matter,
  3. starts a Windows-side serial<->TCP bridge (PowerShell + in-box C#, nothing
     to install) and checks that this side can reach it,
  4. starts Tools/ou_dashboard.py against that bridge and waits for it to
     serve,
  5. opens http://localhost:<http-port>/ in the Windows browser and tells you
     whether the browser will actually be able to reach it,
  6. on Ctrl-C stops the dashboard and the Windows bridge (and never leaves a
     process holding the COM port).

Authentication and decryption go through the vendor SDK (ou_sdk 0.4.1) by
default; `--decoder python` switches the whole bench back to the zero-dependency
reference implementation in Tools/ou_crypto.py. The two are byte-compatible --
`python3 Tools/ou_sdk_interop.py` proves it -- so this is a choice of which
implementation you want to trust on a given run, not a different protocol.

On a plain Linux box with a local /dev/ttyUSB0 none of that is needed: pass
`--port /dev/ttyUSB0` and it just runs the dashboard.

`--stop` cleans up after a previous run: it stops the recorded dashboard and the
Windows bridge. That matters because a launcher started as a background job
inherits SIG_IGN for SIGINT -- Ctrl-C on it does nothing, its cleanup never runs,
and the bridge keeps holding the COM port.

Everything here is additive: it only drives the two existing tools.
"""

import argparse
import base64
import json
import os
import re
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import ou_crypto as oc            # noqa: E402
import ou_serial_test as ost      # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
DASHBOARD = os.path.join(HERE, "ou_dashboard.py")

PROBE_BAUDS = (57600, 115200, 230400)
STATE_PATH = os.path.join(tempfile.gettempdir(), "ou_bench_state.json")
# How far past the previous session's start seq to jump (see initial_start_seq).
SEQ_STEP = 86400

# Friendly-name hints.  A USB-TTL adapter looks like one of these; the flight
# controller's own USB port looks like the second group.
USB_SERIAL_HINTS = ("CH340", "CH341", "CP210", "FT232", "FTDI", "PROLIFIC",
                    "PL2303", "USB-SERIAL", "USB SERIAL", "SILABS", "USB-ENHANCED")
FC_HINTS = ("ARDUPILOT", "PIXHAWK", "PX4", "CUBE", "HOLYBRO", "MATEKSYS")


# ---------------------------------------------------------------------------
# Windows-side helper: a serial<->TCP bridge plus a multi-baud prober,
# compiled from this source by the in-box PowerShell C# compiler.
# ---------------------------------------------------------------------------

BRIDGE_CS = r"""
using System;
using System.IO;
using System.IO.Ports;
using System.Net;
using System.Net.Sockets;
using System.Threading;

public static class OuBench
{
    // Read `seconds` worth of bytes at `baud` into `path`; returns the length.
    private static int Capture(string port, int baud, double seconds, string path)
    {
        SerialPort s = new SerialPort(port, baud, Parity.None, 8, StopBits.One);
        s.ReadTimeout = 50;
        s.Open();
        MemoryStream ms = new MemoryStream();
        byte[] buf = new byte[4096];
        DateTime t0 = DateTime.UtcNow;
        while ((DateTime.UtcNow - t0).TotalSeconds < seconds)
        {
            try
            {
                int n = s.Read(buf, 0, buf.Length);
                if (n > 0) { ms.Write(buf, 0, n); }
            }
            catch (TimeoutException) { }
        }
        s.Close();
        byte[] all = ms.ToArray();
        File.WriteAllBytes(path, all);
        return all.Length;
    }

    // Capture every candidate baud in turn; the caller decrypts the dumps and
    // keeps the baud that actually authenticates.
    public static string Probe(string port, string baudCsv, double seconds, string outDir)
    {
        Directory.CreateDirectory(outDir);
        string summary = "";
        foreach (string raw in baudCsv.Split(','))
        {
            string t = raw.Trim();
            if (t.Length == 0) { continue; }
            int baud = int.Parse(t);
            string path = Path.Combine(outDir, "probe_" + baud + ".bin");
            string err = "";
            int got = 0;
            try { got = Capture(port, baud, seconds, path); }
            catch (Exception e) { err = e.Message.Replace("\r", " ").Replace("\n", " "); }
            summary += baud + " " + got + " " + (err.Length == 0 ? "-" : err) + "\n";
        }
        return summary;
    }

    // Full-duplex COM <-> TCP server.  Exits when no client has shown up for
    // idleSeconds, so a crashed launcher cannot leave the COM port held.
    public static void Start(string port, int baud, int tcpPort, string statusPath,
                             double idleSeconds)
    {
        try
        {
            SerialPort s = new SerialPort(port, baud, Parity.None, 8, StopBits.One);
            s.ReadTimeout = 50;
            s.WriteTimeout = 2000;
            s.Open();
            TcpListener listener = new TcpListener(IPAddress.Any, tcpPort);
            listener.Start();
            int pid = System.Diagnostics.Process.GetCurrentProcess().Id;
            File.WriteAllText(statusPath, "READY " + port + "@" + baud + " port=" + tcpPort
                + " pid=" + pid);

            while (true)
            {
                DateTime idle = DateTime.UtcNow;
                while (!listener.Pending())
                {
                    if ((DateTime.UtcNow - idle).TotalSeconds > idleSeconds)
                    {
                        File.AppendAllText(statusPath, " IDLE-EXIT");
                        return;
                    }
                    Thread.Sleep(100);
                }
                using (TcpClient client = listener.AcceptTcpClient())
                {
                    client.NoDelay = true;
                    Note(statusPath, "CLIENT-IN " + DateTime.Now.ToString("HH:mm:ss"));
                    NetworkStream stream = client.GetStream();
                    stop = false;
                    SerialPort sp = s;
                    Thread pump = new Thread(delegate()
                    {
                        byte[] buf = new byte[8192];
                        while (!stop)
                        {
                            try
                            {
                                int n = sp.Read(buf, 0, buf.Length);
                                if (n > 0) { stream.Write(buf, 0, n); stream.Flush(); }
                            }
                            catch (TimeoutException) { }
                            catch (Exception) { break; }
                        }
                    });
                    pump.IsBackground = true;
                    pump.Start();
                    byte[] back = new byte[8192];
                    try
                    {
                        while (true)
                        {
                            int n = stream.Read(back, 0, back.Length);
                            if (n <= 0) { break; }
                            sp.Write(back, 0, n);
                        }
                    }
                    catch (Exception) { }
                    stop = true;
                    Thread.Sleep(60);
                    Note(statusPath, "CLIENT-OUT " + DateTime.Now.ToString("HH:mm:ss"));
                }
            }
        }
        catch (Exception e)
        {
            File.WriteAllText(statusPath, "ERROR " + e.Message.Replace("\r", " ").Replace("\n", " "));
        }
    }

    private static volatile bool stop;

    private static void Note(string path, string text)
    {
        try { File.AppendAllText(path, text + "\r\n"); } catch (Exception) { }
    }
}
"""


# ---------------------------------------------------------------------------
# PowerShell plumbing
# ---------------------------------------------------------------------------

_PS_S_RE = re.compile(r"<S[^>]*>(.*?)</S>", re.S)


def find_powershell():
    return shutil.which("powershell.exe")


def ps_encode(text):
    return base64.b64encode(text.encode("utf-16-le")).decode("ascii")


def clean_ps_output(text):
    """Drop CLIXML framing but keep the error text it carries."""
    text = text.replace("\r\n", "\n")
    keep, xml = [], []
    for line in text.split("\n"):
        stripped = line.strip()
        if stripped.startswith("#< CLIXML") or stripped.startswith("<"):
            xml.append(line)
        else:
            keep.append(line)
    for chunk in _PS_S_RE.findall("\n".join(xml)):
        clean = chunk.replace("_x000D_", "").replace("_x000A_", "\n").strip()
        if clean:
            keep.append(clean)
    return "\n".join(line for line in keep if line.strip())


def run_ps(powershell, script, timeout=120):
    """Run a PowerShell script, return (rc, cleaned stdout+stderr)."""
    cmd = [powershell, "-NoProfile", "-NonInteractive", "-EncodedCommand", ps_encode(script)]
    try:
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=timeout)
    except subprocess.TimeoutExpired:
        return 124, "<timeout after %ss>" % timeout
    return proc.returncode, clean_ps_output(proc.stdout.decode("utf-8", "replace"))


def ps_header():
    return ('[Console]::OutputEncoding = [System.Text.Encoding]::UTF8\n'
            'Add-Type -TypeDefinition ([System.IO.File]::ReadAllText("%s")) '
            '-Language CSharp -ErrorAction Stop\n')


def win_to_wsl_path(path):
    """C:\\Users\\x\\AppData -> /mnt/c/Users/x/AppData (None if not a drive path)."""
    match = re.match(r"^([A-Za-z]):[\\/](.*)$", path.strip())
    if not match:
        return None
    return "/mnt/%s/%s" % (match.group(1).lower(), match.group(2).replace("\\", "/"))


def parse_default_gateway(route_text):
    for line in route_text.splitlines():
        parts = line.split()
        if parts[:1] == ["default"] and "via" in parts:
            return parts[parts.index("via") + 1]
    return None


# ---------------------------------------------------------------------------
# Port / baud discovery
# ---------------------------------------------------------------------------

def list_com_ports(powershell):
    script = ('Get-CimInstance Win32_PnPEntity | Where-Object { $_.Name -match "\\(COM\\d+\\)" } '
              '| ForEach-Object { $_.Name }')
    _rc, out = run_ps(powershell, script, timeout=90)
    ports = []
    for line in out.splitlines():
        match = re.search(r"\((COM\d+)\)", line)
        if match:
            ports.append((match.group(1), line.strip()))
    return ports


def pick_com(ports, wanted=None):
    """Return (com, note) or (None, reason)."""
    if wanted:
        for com, _name in ports:
            if com.upper() == wanted.upper():
                return com, "指定"
        return wanted, "指定（设备列表里没看到，仍按指定试）"
    usb = [(com, name) for com, name in ports
           if any(h in name.upper() for h in USB_SERIAL_HINTS)
           and not any(h in name.upper() for h in FC_HINTS)]
    if len(usb) == 1:
        return usb[0][0], usb[0][1]
    if len(ports) == 1:
        return ports[0][0], ports[0][1]
    if not ports:
        return None, "Windows 上没有任何 COM 口"
    listing = "、".join("%s(%s)" % (com, name) for com, name in ports)
    return None, "有多个候选口，无法自动确定：%s —— 请用 --com 指定" % listing


def count_frames(data):
    """How many frames in `data` authenticate with the repo key, plus diag."""
    if not data:
        return 0, {}
    shell = oc.SerialShell(oc.K_SERIAL_DEV_PLACEHOLDER)
    diag = shell.enable_diag()
    shell.push(data)
    count = 0
    while shell.next() is not None:
        count += 1
    return count, diag


def looks_like_mavlink(data):
    """Cheap sniff: MAVLink v2/v1 start bytes are 0xFD/0xFE."""
    return data.count(b"\xfd") > 3 or data.count(b"\xfe") > 3


# ---------------------------------------------------------------------------
# Steps
# ---------------------------------------------------------------------------

def step(number, total, text):
    print("[%d/%d] %s" % (number, total, text))
    sys.stdout.flush()


def start_bridge(powershell, win_dir, com, baud, tcp_port, idle_seconds):
    """Launch the bridge on the Windows side; return (proc, pid, status_text)."""
    status_win = win_dir + "\\ou_bench.status"
    status_wsl = win_to_wsl_path(status_win)
    if os.path.exists(status_wsl):
        os.remove(status_wsl)
    script = ps_header() % (win_dir + "\\ou_bench.cs")
    script += '[OuBench]::Start("%s", %d, %d, "%s", %f)\n' % (com, baud, tcp_port, status_win,
                                                              idle_seconds)
    proc = subprocess.Popen([powershell, "-NoProfile", "-NonInteractive",
                             "-EncodedCommand", ps_encode(script)],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                            start_new_session=True)
    # Monotonic: this box's wall clock gets stepped (observed jumping ~37 s),
    # which would expire this deadline early and report a bridge that is fine.
    deadline = time.monotonic() + 40
    while time.monotonic() < deadline:
        if os.path.exists(status_wsl):
            text = open(status_wsl, encoding="utf-8", errors="replace").read().strip()
            if text.startswith("READY") or text.startswith("ERROR"):
                return proc, text
        if proc.poll() is not None:
            return proc, "ERROR 桥进程退出 (rc=%s)" % proc.returncode
        time.sleep(0.25)
    return proc, "ERROR 等桥就绪超时"


def probe_bauds(powershell, win_dir, com, seconds=1.2):
    """Capture every candidate baud; return dict {baud: (bytes, frames, diag)}."""
    script = ps_header() % (win_dir + "\\ou_bench.cs")
    script += '[OuBench]::Probe("%s", "%s", %f, "%s")\n' % (
        com, ",".join(str(b) for b in PROBE_BAUDS), seconds, win_dir)
    _rc, out = run_ps(powershell, script, timeout=180)
    results = {}
    for baud in PROBE_BAUDS:
        path = win_to_wsl_path("%s\\probe_%d.bin" % (win_dir, baud))
        try:
            data = open(path, "rb").read()
        except OSError:
            data = b""
        frames, diag = count_frames(data)
        results[baud] = (len(data), frames, diag, data)
    return results, out


def reachable_host(port, candidates):
    for addr in candidates:
        try:
            sock = socket.create_connection((addr, port), timeout=2.0)
            sock.close()
            return addr
        except OSError:
            continue
    return None


def dashboard_reports_data(http_port, timeout=25.0):
    """Poll /api/state until the dashboard serves; return (state, last_error).

    Durations use the monotonic clock: this box's wall clock gets stepped (a
    forward step would cut the wait short and report a healthy dashboard as
    dead, which is exactly the kind of false alarm this tool must not produce).
    """
    import http.client
    deadline = time.monotonic() + timeout
    last = "还没试过"
    while time.monotonic() < deadline:
        try:
            conn = http.client.HTTPConnection("127.0.0.1", http_port, timeout=3)
            conn.request("GET", "/api/state")
            resp = conn.getresponse()
            body = resp.read()
            conn.close()
            if resp.status == 200:
                return json.loads(body.decode("utf-8")), None
            last = "HTTP %s" % resp.status
        except Exception as exc:                                      # noqa: BLE001
            last = "%s: %s" % (type(exc).__name__, exc)
        time.sleep(0.4)
    return None, last


def http_port_owner(http_port, timeout=1.5):
    """What already answers on http_port, before we launch anything.

    Returns ("dashboard", decoder_row) / ("http", None) / (None, None).

    Without this, a dashboard left over from a previous run answers the
    readiness poll below and the launcher prints *its* rows as if they were the
    ones it just started -- which is exactly how you would talk yourself into
    believing the SDK backend is live when it is not.
    """
    import http.client
    try:
        conn = http.client.HTTPConnection("127.0.0.1", http_port, timeout=timeout)
        conn.request("GET", "/api/state")
        resp = conn.getresponse()
        body = resp.read()
        conn.close()
    except Exception:                                                 # noqa: BLE001
        return None, None
    try:
        state = json.loads(body.decode("utf-8"))
        rows = dict(state["stats"])
    except Exception:                                                 # noqa: BLE001
        return "http", None
    return "dashboard", rows.get("解密后端")


def windows_can_reach(powershell, url):
    script = ("try { $r = Invoke-WebRequest -UseBasicParsing -TimeoutSec 8 '%s'; "
              "Write-Output ('HTTP ' + $r.StatusCode) } catch { Write-Output 'FAIL' }" % url)
    _rc, out = run_ps(powershell, script, timeout=60)
    return "HTTP 200" in out, out.strip()


def load_state(path=None):
    try:
        with open(path or STATE_PATH, encoding="utf-8") as handle:
            state = json.load(handle)
    except (OSError, ValueError):
        return {}
    return state if isinstance(state, dict) else {}


def save_state(path=None, **fields):
    state = load_state(path)
    state.update(fields)
    try:
        with open(path or STATE_PATH, "w", encoding="utf-8") as handle:
            json.dump(state, handle)
    except OSError:
        pass


def runnable():
    """A copy-pasteable way to run this script from the current directory.

    `sys.argv[0]` is just "ou_bench.py" when the script is run from inside
    Tools/, and printing that as advice produced a literal
    "ou_bench.py: command not found".
    """
    return "python3 %s" % os.path.relpath(os.path.abspath(__file__))


def process_is(pid, fragment):
    """True when `pid` is alive and its command line really is ours.

    Guards every recorded-pid kill against a recycled pid: we only ever signal a
    process that is still the tool we wrote down, never whatever happened to
    inherit the number.
    """
    try:
        with open("/proc/%d/cmdline" % pid, "rb") as handle:
            return fragment in handle.read().decode("utf-8", "replace")
    except OSError:
        return False


def stop_recorded_bridge(powershell):
    """Kill the bridge we started, but keep the seq memory for the next run."""
    state = load_state()
    pid = state.get("pid")
    if not pid:
        return False
    run_ps(powershell, "Stop-Process -Id %d -Force -ErrorAction SilentlyContinue" % pid,
           timeout=30)
    print("已停掉上次的桥 (pid %s)" % pid)
    save_state(pid=None)
    return True


def stop_recorded_dashboard(path=None):
    """Stop a dashboard left over from a previous run (keeps the seq memory).

    This is not just tidiness: a launcher started as a background job inherits
    SIG_IGN for SIGINT, so Ctrl-C on it is a no-op, its cleanup never runs, and
    the dashboard keeps the HTTP port (and the serial link) forever.  Killing
    the dashboard also unblocks such a launcher, which is sitting in wait().
    """
    pid = load_state(path).get("dash_pid")
    if not (isinstance(pid, int) and process_is(pid, "ou_dashboard.py")):
        return False
    try:
        os.kill(pid, signal.SIGTERM)
    except OSError:
        return False
    print("已停掉上次的仪表盘 (pid %d)" % pid)
    save_state(path, dash_pid=None)
    time.sleep(0.5)                    # let it let go of the HTTP port
    return True


# ---------------------------------------------------------------------------
# Self-check (no hardware, no Windows needed)
# ---------------------------------------------------------------------------

def self_check(verbose=True):
    checks = [0]

    def check(label, got, want):
        checks[0] += 1
        if got != want:
            raise AssertionError("%s:\n  got  %s\n  want %s" % (label, got, want))
        if verbose:
            print("  ok  %s" % label)

    # --- Windows <-> WSL path mapping ---
    check("win_to_wsl_path C:/Users/qiao/AppData",
          win_to_wsl_path("C:\\Users\\qiao\\AppData\\Local"), "/mnt/c/Users/qiao/AppData/Local")
    check("win_to_wsl_path lowercase drive",
          win_to_wsl_path("d:\\tmp\\x.bin"), "/mnt/d/tmp/x.bin")
    check("win_to_wsl_path rejects junk", win_to_wsl_path("/dev/ttyUSB0"), None)

    # --- gateway parsing ---
    check("default gateway parsed",
          parse_default_gateway("default via 172.29.208.1 dev eth0 proto kernel onlink\n"
                                "172.29.208.0/20 dev eth0 scope link"),
          "172.29.208.1")
    check("no default route", parse_default_gateway("172.29.208.0/20 dev eth0"), None)

    # --- port picking: must never grab Mission Planner's FC USB port ---
    real = [("COM4", "ArduPilot (COM4)"), ("COM6", "USB-SERIAL CH340 (COM6)")]
    check("picks the CH340, not the FC USB port", pick_com(real), ("COM6", "USB-SERIAL CH340 (COM6)"))
    check("explicit --com wins", pick_com(real, "com4"), ("COM4", "指定"))
    check("single port is used", pick_com([("COM3", "Some Port (COM3)")])[0], "COM3")
    check("two unknown ports refuse to guess", pick_com(
        [("COM1", "A (COM1)"), ("COM2", "B (COM2)")])[0], None)
    check("no ports at all", pick_com([])[0], None)

    # --- baud detection with genuinely sealed frames ---
    frame = ost.encode_frame(ost.TYPE_HEARTBEAT, mode=0, system_type=0, fw_version=4,
                             system_state=3)
    peer = oc.SerialShell(oc.K_SERIAL_DEV_PLACEHOLDER, side="fc")
    good = b"".join(peer.seal(frame) for _ in range(5))
    check("5 sealed frames authenticate", count_frames(good)[0], 5)
    check("garbage does not authenticate", count_frames(bytes(range(256)) * 4)[0], 0)
    check("plaintext frame does not authenticate", count_frames(frame * 4)[0], 0)
    check("empty input", count_frames(b"")[0], 0)
    check("mavlink sniff on 0xFD stream", looks_like_mavlink(b"\xfd\x09\x00" * 4), True)
    check("mavlink sniff on OU frames", looks_like_mavlink(good), False)

    # --- CLIXML error extraction (this bit us: errors were invisible) ---
    blob = ('COMPILE OK\n#< CLIXML\n<Objs Version="1.1.0.1" xmlns="x"><S S="Error">'
            'Cannot open COM6_x000D__x000A_</S></Objs>')
    cleaned = clean_ps_output(blob)
    check("clixml keeps plain lines", cleaned.splitlines()[0], "COMPILE OK")
    check("clixml surfaces the error text", "Cannot open COM6" in cleaned, True)

    # --- the embedded C# must expose what the launcher calls ---
    check("bridge exposes Probe", "public static string Probe(" in BRIDGE_CS, True)
    check("bridge exposes Start", "public static void Start(" in BRIDGE_CS, True)
    check("bridge records its pid", '" pid=" + pid' in BRIDGE_CS, True)
    check("bridge can idle-exit so it never holds COM forever",
          "IDLE-EXIT" in BRIDGE_CS, True)
    check("bridge listens on all interfaces", "IPAddress.Any" in BRIDGE_CS, True)
    check("bridge disables Nagle", "client.NoDelay = true" in BRIDGE_CS, True)

    # --- anti-replay seq bootstrapping (the "no ack" trap) ---
    with tempfile.TemporaryDirectory() as tmp:
        state = os.path.join(tmp, "state.json")
        check("start_seq defaults to now",
              initial_start_seq(None, state, now=1000), 1000)
        check("state file written", save_state(state, start_seq=5000), None)
        check("state roundtrips", load_state(state).get("start_seq"), 5000)
        check("start_seq jumps above the last session",
              initial_start_seq(None, state, now=1000), 5000 + SEQ_STEP)
        check("a later clock still picks the higher value",
              initial_start_seq(None, state, now=10 ** 9), 10 ** 9)
        check("explicit --start-seq wins", initial_start_seq(42, state, now=1000), 42)
        check("unreadable state falls back to now",
              initial_start_seq(None, os.path.join(tmp, "missing.json"), now=777), 777)
        # A session that runs for a while and exits must not reset the counter.
        save_state(state, pid=None)
        check("stopping the bridge keeps the seq memory", load_state(state).get("pid"), None)
        check("seq still above the last session after a stop",
              initial_start_seq(None, state, now=1000), 5000 + SEQ_STEP)

    # --- every embedded C# line survives flake8's 127 columns ---
    longest = max(len(line) for line in BRIDGE_CS.splitlines())
    check("embedded C# lines <= 120 columns", longest <= 120, True)

    # --- decrypt backend: the SDK is the default, python stays reachable ---
    def dash_args(**kw):
        base = dict(http_port=8770, decoder="sdk", allow_control=False,
                    stream="0x18,0x1a,0x1b", no_stream=False)
        base.update(kw)
        return argparse.Namespace(**base)

    cmd = dashboard_command(dash_args(), "tcp:1.2.3.4:5555", 1792378051, 57600)
    check("dashboard is launched with --decoder", "--decoder" in cmd, True)
    check("the default backend is the SDK", cmd[cmd.index("--decoder") + 1], "sdk")
    check("a bench-sized start-seq survives the handoff",
          cmd[cmd.index("--start-seq") + 1], "1792378051")
    check("baud is passed for display", cmd[cmd.index("--baud") + 1], "57600")
    check("no --baud when the rate is unknown",
          "--baud" in dashboard_command(dash_args(), "x", 1, None), False)
    python_cmd = dashboard_command(dash_args(decoder="python"), "x", 1, None)
    check("--decoder python is still an escape hatch",
          python_cmd[python_cmd.index("--decoder") + 1], "python")
    check("--no-stream suppresses --stream",
          "--stream" in dashboard_command(dash_args(no_stream=True), "x", 1, None), False)
    check("--allow-control reaches the dashboard",
          "--allow-control" in dashboard_command(dash_args(allow_control=True), "x", 1, None),
          True)

    ok, detail = sdk_status()
    check("sdk_status returns (bool, reason)", isinstance(ok, bool) and bool(detail), True)
    check("the SDK hint names an extractable artifact", "ou-sdk-0.4.1" in SDK_ROOT_HINT, True)
    check("a bogus SDK root is rejected before any build runs",
          build_sdk_wrapper("/nonexistent/ou-sdk")[0], False)
    check("...and says what is missing",
          "crypto.hpp" in build_sdk_wrapper("/nonexistent/ou-sdk")[1], True)

    # --- a stale dashboard must not be mistaken for ours -------------------
    check("a free http port reports no owner", http_port_owner(49999), (None, None))

    # --- stopping a leftover run -------------------------------------------
    # A launcher started as a background job ignores SIGINT, so its cleanup
    # never runs and --stop is the only way out.  It must never signal a pid
    # that was recycled in the meantime.
    with tempfile.TemporaryDirectory() as tmp:
        spath = os.path.join(tmp, "state.json")
        check("no recorded dashboard means nothing to stop",
              stop_recorded_dashboard(spath), False)
        save_state(spath, dash_pid=os.getpid())   # alive, but not a dashboard
        check("a recycled pid is not signalled", stop_recorded_dashboard(spath), False)
        check("...and its record is left alone",
              load_state(spath).get("dash_pid"), os.getpid())
    check("process_is matches our own cmdline",
          process_is(os.getpid(), "ou_bench.py"), True)
    check("process_is rejects a foreign cmdline",
          process_is(os.getpid(), "ou_dashboard.py"), False)
    check("process_is is safe on a dead pid",
          process_is(1 << 22, "ou_bench.py"), False)
    check("runnable() is copy-pasteable", runnable().startswith("python3 "), True)
    check("runnable() names this script", runnable().endswith("ou_bench.py"), True)
    return checks[0]


def initial_start_seq(explicit, state_path, now=None):
    """Pick an outgoing seq above every previous session's, for the replay window.

    The dashboard sends ~1 heartbeat/s, so a session can advance the counter by
    thousands.  Jump a full day's worth past the last session's start instead of
    by one, so a clock that stepped backwards (or two runs in the same second)
    still lands strictly above whatever the FC has already accepted.

    This one deliberately uses the wall clock, not the monotonic one: the value
    outlives the process (it is remembered in the state file) and only has to be
    a big number that grows, so it must be comparable across reboots.
    """
    if explicit is not None:
        return explicit
    seq = int(now if now is not None else time.time())
    previous = load_state(state_path).get("start_seq")
    if isinstance(previous, int):
        seq = max(seq, previous + SEQ_STEP)
    return seq


# ---------------------------------------------------------------------------
# Decrypt backend
# ---------------------------------------------------------------------------

SDK_ROOT_HINT = "ou-sdk-0.4.1"


def sdk_status():
    """(usable, detail): can the dashboard decrypt through ou_sdk 0.4.1?"""
    try:
        import ou_sdk_bridge
        return True, ou_sdk_bridge.version()
    except Exception as exc:                                    # noqa: BLE001
        return False, str(exc)


def build_sdk_wrapper(sdk_root=None):
    """Build Tools/ou_sdk_wrapper against an extracted ou_sdk tree.

    Returns (ok, detail). cmake when present, else the plain Makefile: every
    other tool here is pure stdlib, so make is the floor, not cmake.
    """
    root = sdk_root or os.environ.get("OU_SDK_ROOT")
    if not root:
        return False, ("OU_SDK_ROOT 没设；指向解出来的 %s（里面要有 include/ 和 lib/）"
                       % SDK_ROOT_HINT)
    if not os.path.exists(os.path.join(root, "include", "ou", "crypto.hpp")):
        # Check the tree before shelling out, so a typo yields one clear line
        # instead of a cmake error dump.
        return False, ("%s 里没有 include/ou/crypto.hpp -- 不是 ou_sdk 头文件树" % root)
    wrapper = os.path.join(HERE, "ou_sdk_wrapper")
    build = os.path.join(wrapper, "build")
    if shutil.which("cmake"):
        steps = [(["cmake", "-S", wrapper, "-B", build, "-DOU_SDK_ROOT=" + root],
                  "cmake configure"),
                 (["cmake", "--build", build, "-j"], "cmake build")]
    elif shutil.which("make"):
        steps = [(["make", "-C", wrapper, "OU_SDK_ROOT=" + root], "make")]
    else:
        return False, "既没有 cmake 也没有 make，没法构建封装层"

    for argv, what in steps:
        proc = subprocess.run(argv, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        if proc.returncode != 0:
            tail = proc.stdout.decode("utf-8", "replace").strip().splitlines()[-4:]
            return False, "%s 失败:\n      %s" % (what, "\n      ".join(tail))
    return True, "%s ok" % steps[-1][1]


def ensure_sdk_decoder():
    """Fail fast when --decoder sdk was asked for but the wrapper will not load.

    Runs before the COM port is touched, so a broken SDK tree does not leave a
    half-started bench behind. Returns (ok, detail).
    """
    ok, detail = sdk_status()
    if ok or not os.environ.get("OU_SDK_ROOT"):
        return ok, detail
    built, log = build_sdk_wrapper()
    if not built:
        return False, log
    ok, detail = sdk_status()
    return ok, detail


def dashboard_command(args, dash_port, start_seq, baud, python=None):
    """The exact dashboard argv this launcher uses.

    Pure, so --self-test can assert on it -- in particular that the decrypt
    backend reaches the dashboard as --decoder.
    """
    cmd = [python or sys.executable, DASHBOARD, "--port", dash_port,
           "--http-port", str(args.http_port), "--no-browser",
           "--start-seq", str(start_seq), "--decoder", args.decoder]
    if baud:
        # Display only (the port is already open on the other side), but a wrong
        # header rate is confusing on a bench where 57600 is the real one.
        cmd += ["--baud", str(baud)]
    if args.allow_control:
        cmd.append("--allow-control")
    if args.stream and not args.no_stream:
        cmd += ["--stream", args.stream]
    return cmd


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="one-click OU v0.4 bench: find the FC's serial port, bridge it if "
                    "needed, and open the dashboard.")
    parser.add_argument("--port", default=None,
                        help="run the dashboard directly on this endpoint "
                             "(/dev/ttyUSB0 or tcp:HOST:PORT) and skip the bridge")
    parser.add_argument("--com", default=None, help="Windows COM port of the USB-TTL")
    parser.add_argument("--baud", type=int, default=None,
                        help="skip the baud probe and use this rate")
    parser.add_argument("--tcp-port", type=int, default=5555)
    parser.add_argument("--http-port", type=int, default=8770)
    parser.add_argument("--stream", default="0x18,0x1a,0x1b",
                        help="optional streams to enable (default: the three echoes)")
    parser.add_argument("--no-stream", action="store_true", help="do not enable any stream")
    parser.add_argument("--allow-control", action="store_true",
                        help="unlock ARM / SET_MODE / SET_PWM / GO_HOME in the dashboard")
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument("--start-seq", type=int, default=None,
                        help="outgoing seq to start at (default: a value above every "
                             "previous session, so the FC's anti-replay window accepts us)")
    parser.add_argument("--decoder", choices=["sdk", "python"], default="sdk",
                        help="which implementation authenticates and decrypts the link: "
                             "'sdk' (ou_sdk 0.4.1 through Tools/ou_sdk_wrapper, the "
                             "default) or 'python' (the zero-dependency reference in "
                             "Tools/ou_crypto.py). The two are byte-compatible.")
    parser.add_argument("--idle-timeout", type=float, default=900.0,
                        help="the Windows bridge exits after this many idle seconds")
    parser.add_argument("--stop", action="store_true",
                        help="stop a bridge left over from a previous run and exit")
    parser.add_argument("--self-test", action="store_true",
                        help="validate the launcher's logic offline and exit")
    args = parser.parse_args()

    if args.self_test:
        count = self_check(verbose=True)
        print("ou_bench self-test: %u checks passed" % count)
        return 0

    powershell = find_powershell()

    if args.stop:
        # The dashboard first: it works without powershell, and it releases the
        # HTTP port. Then the Windows bridge, which is what holds the COM port.
        stopped = stop_recorded_dashboard()
        if powershell:
            stopped = stop_recorded_bridge(powershell) or stopped
        if not stopped:
            print("状态文件里没有记录到要停的仪表盘或桥 —— 没什么可停的")
        return 0

    total = (2 if args.port else 5) + (1 if args.decoder == "sdk" else 0)
    n = 0
    baud = args.baud              # display only; the port is opened on the other side

    # -- decrypt backend, before anything touches the COM port --------------
    if args.decoder == "sdk":
        n += 1
        step(n, total, "确认 ou_sdk 0.4.1 解密后端 ...")
        ok, detail = ensure_sdk_decoder()
        if not ok:
            print("      %s" % detail)
            print("")
            print("  下行解密要走厂商 SDK，但它没就绪。二选一：")
            print("   1) 装好它（构建一次即可）：")
            print("        export OU_SDK_ROOT=/path/to/%s" % SDK_ROOT_HINT)
            print("        make -C Tools/ou_sdk_wrapper OU_SDK_ROOT=$OU_SDK_ROOT")
            print("   2) 这次仍用 Python 参考实现（两者字节相同）：")
            print("        %s --decoder python" % runnable())
            return 2
        print("      -> %s" % detail)

    # -- never report on somebody else's dashboard ---------------------------
    # Do this before the COM port and bridge work: a leftover dashboard would
    # silently answer the readiness poll later and make the summary below
    # describe the old process instead of the one we start.
    kind, other_decoder = http_port_owner(args.http_port)
    if kind:
        print("")
        if kind == "dashboard":
            print("  HTTP 端口 %d 已经有一个仪表盘在跑%s。"
                  % (args.http_port,
                     "（解密后端：%s）" % other_decoder if other_decoder
                     else "（没标明后端：早于 --decoder 之前的版本）"))
        else:
            print("  HTTP 端口 %d 已经被别的进程占用。" % args.http_port)
        print("  再往下走，最后的统计会来自那个进程，而不是我们新启动的这个 ——")
        print("  那会让人以为新后端已经生效。")
        print("  注意：只换 --http-port 通常不够 —— 旧实例往往还占着 USB-TTL 的")
        print("  COM 口（Windows 侧的桥），新实例会开不了串口。先收干净再来：")
        print("      %s --stop      # 停掉旧仪表盘和 Windows 桥" % runnable())
        print("      %s" % runnable())
        print("  （若旧实例用的是别的串口、不冲突，也可以只换端口：%s --http-port %d）"
              % (runnable(), args.http_port + 1))
        return 2

    # The FC's anti-replay window only accepts strictly increasing seq and only
    # resets when *it* reboots, so every restart of this tool would otherwise
    # have its commands silently dropped.  Start above every previous session.
    start_seq = initial_start_seq(args.start_seq, STATE_PATH)

    # -- direct endpoint (plain Linux box, or an explicit tcp:) ---------------
    bridge_proc = None
    bridge_pid = None
    if args.port:
        n += 1
        step(n, total, "直接用 --port %s（不经过 Windows 桥）" % args.port)
        dash_port = args.port
        save_state(start_seq=start_seq)
    else:
        if not powershell:
            print("这台机器上找不到 powershell.exe。")
            print("要么把 USB-TTL 插到本机并用 --port /dev/ttyUSB0，")
            print("要么在 WSL 里运行（WSL 才能驱动 Windows 的 COM 口）。")
            return 2

        n += 1
        step(n, total, "在 Windows 上找 USB-TTL 串口 ...")
        _rc, win_temp = run_ps(powershell, "[Console]::Out.Write($env:LOCALAPPDATA)", timeout=60)
        win_dir = win_temp.strip() + "\\ou_bench"
        wsl_dir = win_to_wsl_path(win_dir)
        if not wsl_dir:
            print("拿不到 Windows 的 LOCALAPPDATA（返回 %r）" % win_temp)
            return 2
        os.makedirs(wsl_dir, exist_ok=True)
        with open(os.path.join(wsl_dir, "ou_bench.cs"), "w", encoding="utf-8") as handle:
            handle.write(BRIDGE_CS)

        ports = list_com_ports(powershell)
        com, note = pick_com(ports, args.com)
        if not com:
            print("  %s" % note)
            return 2
        print("      -> %s  (%s)" % (com, note))

        if args.baud:
            baud = args.baud
            n += 1
            step(n, total, "使用指定波特率 %d" % baud)
        else:
            n += 1
            step(n, total, "探测波特率（%s），按能否通过验签判定 ..."
                 % "/".join(str(b) for b in PROBE_BAUDS))
            results, _probe_out = probe_bauds(powershell, win_dir, com)
            for rate in PROBE_BAUDS:
                nbytes, frames, _diag, _data = results[rate]
                print("      %6d: %6d 字节, 验签通过 %d 帧%s"
                      % (rate, nbytes, frames, "  <== 就是它" if frames else ""))
            best = max(PROBE_BAUDS, key=lambda r: results[r][1])
            if results[best][1] == 0:
                print("")
                print("  探测不到 OU 帧，先别急着上仪表盘。逐个排查：")
                any_bytes = [r for r in PROBE_BAUDS if results[r][0] > 0]
                if not any_bytes:
                    print("   * 所有波特率都是 0 字节 -> 线序（TX/RX 交叉、GND 共地）、"
                          "该口没在发、或 SERIALx_PROTOCOL 未生效（改完要重启飞控）")
                elif looks_like_mavlink(results[any_bytes[0]][3]):
                    print("   * 收到的是 MAVLink（0xFD 帧头）-> 这个口的 SERIALx_PROTOCOL "
                          "还是 2；要跑 OU 得设成 49")
                else:
                    print("   * 有字节但没有一帧能验签 -> 密钥不一致（本仓库密钥指纹 "
                          "%s），或该口不是 OU 协议" % sm3_fingerprint())
                print("   * 参考文档 §10.1 的排查顺序")
                return 3
            baud = best
            print("      -> %d" % baud)

        n += 1
        step(n, total, "在 Windows 上起串口桥（COM -> TCP %d）..." % args.tcp_port)
        stop_recorded_bridge(powershell)
        bridge_proc, status = start_bridge(powershell, win_dir, com, baud,
                                           args.tcp_port, args.idle_timeout)
        if not status.startswith("READY"):
            print("      %s" % status)
            if "Access" in status or "denied" in status.lower() or "拒绝" in status:
                print("      COM 口被别的程序占着：关掉串口助手，或用 --stop 清理上次的桥")
            return 3
        bridge_pid = int(re.search(r"pid=(\d+)", status).group(1))
        save_state(pid=bridge_pid, com=com, baud=baud, tcp_port=args.tcp_port,
                   start_seq=start_seq)
        print("      -> %s  (Windows pid %d)" % (status.split(" pid=")[0], bridge_pid))

        n += 1
        step(n, total, "确认这边能连上桥 ...")
        gateway = parse_default_gateway(
            subprocess.run(["ip", "route"], stdout=subprocess.PIPE).stdout.decode())
        host = reachable_host(args.tcp_port, [a for a in (gateway, "127.0.0.1") if a])
        if not host:
            print("      连不上桥（试过 %s 和 127.0.0.1）" % gateway)
            stop_recorded_bridge(powershell)
            return 3
        print("      -> %s:%d" % (host, args.tcp_port))
        dash_port = "tcp:%s:%d" % (host, args.tcp_port)

    # -- dashboard -----------------------------------------------------------
    if not os.path.exists(DASHBOARD):
        print("找不到 %s" % DASHBOARD)
        return 2
    cmd = dashboard_command(args, dash_port, start_seq, baud)

    n += 1
    step(n, total, "启动仪表盘 (%s) ..." % dash_port)
    dash = subprocess.Popen(cmd, start_new_session=False)
    save_state(dash_pid=dash.pid)
    url = "http://localhost:%d/" % args.http_port
    try:
        state, poll_error = dashboard_reports_data(args.http_port)
        if state is None:
            print("      仪表盘没起来：%s" % poll_error)
            dash_state = "还在跑" if dash.poll() is None else "已退出 rc=%s" % dash.returncode
            print("      仪表盘进程状态: %s" % dash_state)
            if dash.poll() is None:
                print("      （端口 %d 可能被占；或启动流阶段还没走完）" % args.http_port)
            return 3
        rows = dict(state["stats"])
        print("      -> 解密后端 %s，合法帧 %s，验签失败 %s，防重放 %s"
              % (rows.get("解密后端"), rows.get("合法帧"),
                 rows.get("验签失败 (auth_fail)"), rows.get("防重放丢弃 (replay)")))

        browser_ok = False
        if not args.no_browser and powershell:
            ok, detail = windows_can_reach(powershell, url)
            browser_ok = ok
            if not ok:
                print("      Windows 侧打开 %s 失败（%s）" % (url, detail))
        if not args.no_browser and powershell and browser_ok:
            run_ps(powershell, "Start-Process '%s'" % url, timeout=30)

        print("")
        print("=" * 68)
        print(" OU 台架已就绪")
        if args.port:
            print("   串口      %s" % args.port)
        else:
            print("   串口      %s @ %d" % (com, baud))
            print("   桥        Windows pid %d -> %s:%d" % (bridge_pid, host, args.tcp_port))
        print("   仪表盘    %s" % url)
        print("   解密后端  %s" % (rows.get("解密后端") or "(未标明)"))
        print("   控制权限  %s" % ("已解锁" if args.allow_control else "只读"))
        print("   起始 seq  %d  (防重放窗口会接受它)" % start_seq)
        print("   Ctrl-C 停止（会自动关掉 Windows 侧的桥，不占 COM 口）")
        print("=" * 68)
        dash.wait()
        return 0
    except KeyboardInterrupt:
        print("\n收摊 ...")
        return 0
    finally:
        if dash.poll() is None:
            dash.terminate()
            try:
                dash.wait(timeout=5)
            except subprocess.TimeoutExpired:
                dash.kill()
        save_state(dash_pid=None)
        if bridge_pid and powershell:
            stop_recorded_bridge(powershell)


def sm3_fingerprint():
    """Same value the dashboard prints, so a diagnosis can be compared directly."""
    try:
        return oc.sm3_hmac(oc.K_SERIAL_DEV_PLACEHOLDER, b"ou-dashboard").hex()[:12]
    except Exception:                                                 # noqa: BLE001
        return "?"


if __name__ == "__main__":
    sys.exit(main())
