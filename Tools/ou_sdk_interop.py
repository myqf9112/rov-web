#!/usr/bin/env python3
"""Acceptance run for the ou_sdk 0.4.1 sealed-link wrapper (Tools/ou_sdk_wrapper).

Three independent checks, none of which needs hardware:

  1. C++ probe self-test     16 golden frames parse, seal/open round-trips, the
                             direction binding holds, resync works, a tampered
                             tag is rejected *and classified*.
  2. Byte-level seal diff    wrapper `seal` output is byte-identical to the
                             independent pure-Python `ou_crypto.seal` for all 16
                             golden frames -- at seq 0 and at a bench-sized
                             sequence (~1.8e9), with fixed key + fixed IV.
  3. Cross-implementation    SDK seals -> Python opens, Python seals -> SDK
                             opens, for every golden frame, with live (CSPRNG)
                             IVs, exactly as the dashboard runs it.

Check 2 is the one that catches "both implementations agree with themselves":
it pins two independent codebases to the same bytes.

    python3 Tools/ou_sdk_interop.py
    python3 Tools/ou_sdk_interop.py --self-test     # terse, same exit code

Exit code 0 only when every check passes.
"""

import argparse
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.realpath(__file__))
REPO = os.path.dirname(HERE)
WRAPPER_DIR = os.path.join(HERE, "ou_sdk_wrapper")
GOLDEN_H = os.path.join(REPO, "libraries", "OU_Protocol", "tests", "golden", "golden.h")

# The probe pins these so its output is reproducible and diffable.
PROBE_KEY = bytes(range(16))
PROBE_IV = bytes(range(0x10, 0x20))
# The repo's bench seeds --start-seq from the wall clock (Tools/ou_bench.py).
# Nothing about the wire format depends on the value, but the *ability to set
# it* does -- which is exactly why the outbound path is not ShellCrypto::seal.
BENCH_SEQ = 1792378051

sys.path.insert(0, HERE)

import ou_crypto as ou                                                       # noqa: E402


def load_golden(path=GOLDEN_H):
    """[(name, frame_bytes)] straight out of the AUTO-GENERATED header."""
    text = open(path, encoding="utf-8").read()
    cases = []
    for name, body in re.findall(
            r"OU_GOLDEN_([A-Z0-9]+)_FRAME\[[A-Za-z0-9_]+\] = \{(.*?)\};", text, re.S):
        cases.append((name, bytes(int(b, 16) for b in re.findall(r"0x([0-9A-Fa-f]{2})", body))))
    return cases


def find_probe(explicit=None):
    candidates = [explicit] if explicit else []
    candidates += [
        os.environ.get("OU_SDK_WRAPPER_PROBE"),
        os.path.join(WRAPPER_DIR, "build", "ou_link_probe"),
        os.path.join(WRAPPER_DIR, "build", "Release", "ou_link_probe"),
        os.path.join(WRAPPER_DIR, "ou_link_probe"),
    ]
    for path in candidates:
        if path and os.path.exists(path):
            return path
    return None


def run_probe(probe, *args):
    proc = subprocess.run([probe] + list(args), capture_output=True, text=True)  # noqa: S603
    return proc.returncode, proc.stdout.strip(), proc.stderr.strip()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--self-test", action="store_true",
                        help="terse pass/fail output (same checks, same exit code)")
    parser.add_argument("--probe", default=None, help="path to ou_link_probe")
    parser.add_argument("--sdk-root", default=os.environ.get("OU_SDK_ROOT"),
                        help="ou_sdk 0.4.1 root (include/ + lib/), for the report")
    args = parser.parse_args(argv)

    verbose = not args.self_test
    failures = []

    def out(line=""):
        if verbose:
            print(line)

    print("ou_sdk 0.4.1 wrapper acceptance")
    print("  golden vectors : %s" % GOLDEN_H)
    print("  sdk root       : %s" % (args.sdk_root or "(unset)"))
    print()

    # -- backend availability ------------------------------------------------
    try:
        import ou_sdk_bridge
        bridge_version = ou_sdk_bridge.version()
    except Exception as exc:                                                # noqa: BLE001
        print("FAIL: cannot load the SDK wrapper: %s" % exc)
        return 2
    probe = find_probe(args.probe)
    print("  wrapper lib    : %s" % bridge_version)
    print("  probe binary   : %s" % (probe or "(missing -- build it first)"))
    print()

    # -- 1. C++ probe self-test ---------------------------------------------
    print("[1/3] C++ probe self-test")
    if probe is None:
        failures.append("probe binary not built")
        print("  skipped: build with "
              "cmake -S Tools/ou_sdk_wrapper -B Tools/ou_sdk_wrapper/build "
              "-DOU_SDK_ROOT=<ou-sdk-0.4.1>")
    else:
        code, stdout, stderr = run_probe(probe, "--selftest")
        if verbose:
            for line in stdout.splitlines():
                print("  | %s" % line)
        if code != 0:
            failures.append("probe self-test failed")
            if not verbose:
                print(stdout)
        print("  -> %s" % ("PASS" if code == 0 else "FAIL"))
    print()

    # -- 2. byte-level seal diff --------------------------------------------
    print("[2/3] byte-level seal diff (fixed key + fixed IV)")
    cases = load_golden()
    if not cases:
        failures.append("no golden frames found")
    if probe is None:
        failures.append("byte diff skipped (no probe)")
        print("  skipped: needs the probe binary")
    else:
        checked = 0
        seq_failures = []
        for name, frame in cases:
            # A fresh ShellCrypto per vector on both sides: the probe starts a
            # new process (seq 0) for each call, so the Python side must too.
            py_fc = ou.ShellCrypto(PROBE_KEY, ou.FlowId.FC_TO_BOARD,
                                   iv_source=lambda: PROBE_IV)
            py_board = ou.ShellCrypto(PROBE_KEY, ou.FlowId.BOARD_TO_FC,
                                      iv_source=lambda: PROBE_IV)
            # producer: both sides must emit identical bytes
            code, wrapper_hex, _ = run_probe(probe, "seal", frame.hex(), "fc")
            want = py_fc.seal(frame).hex()
            ok = code == 0 and wrapper_hex == want
            if verbose:
                print("  %-18s seal     %s" % (name, "ok" if ok else "MISMATCH"))
                if not ok:
                    print("      wrapper: %s" % wrapper_hex)
                    print("      python : %s" % want)
            if not ok:
                failures.append("%s: seal bytes differ" % name)
            checked += 1

            # consumer: the wrapper must open what Python produced
            code, plain_hex, _ = run_probe(probe, "open", py_board.seal(frame).hex(), "fc")
            ok = code == 0 and plain_hex.lower() == frame.hex()
            if verbose:
                print("  %-18s open     %s" % (name, "ok" if ok else "MISMATCH"))
            if not ok:
                failures.append("%s: open failed" % name)
            checked += 1

            # Resuming above the peer's window is the case ou_sdk's own
            # ShellCrypto cannot express: --start-seq is wall-clock sized.
            py_seq = ou.ShellCrypto(PROBE_KEY, ou.FlowId.FC_TO_BOARD,
                                    iv_source=lambda: PROBE_IV)
            py_seq.tx_seq = BENCH_SEQ
            code, wrapper_hex, _ = run_probe(probe, "seal", frame.hex(), "fc", str(BENCH_SEQ))
            ok = code == 0 and wrapper_hex == py_seq.seal(frame).hex()
            if verbose:
                print("  %-18s seal@%-10u %s"
                      % (name, BENCH_SEQ, "ok" if ok else "MISMATCH"))
            if not ok:
                seq_failures.append(name)
            checked += 1
        if seq_failures:
            failures.append("seq=%u seal bytes differ for: %s"
                            % (BENCH_SEQ, ", ".join(seq_failures)))
        print("  -> %s (%u vectors byte-compared, incl. seq=%u)" % (
            "PASS" if not any("seal bytes differ" in f or "open failed" in f
                              for f in failures) else "FAIL", checked, BENCH_SEQ))
    print()

    # -- 3. cross-implementation round trips --------------------------------
    print("[3/3] cross-implementation round trips (live CSPRNG IVs)")
    try:
        count = ou_sdk_bridge.self_test(verbose=verbose)
        print("  -> PASS (%u checks)" % count)
    except AssertionError as exc:
        failures.append("bridge self-test: %s" % exc)
        print("  -> FAIL: %s" % exc)
    print()

    if failures:
        print("ACCEPTANCE: FAIL (%u problem(s))" % len(failures))
        for item in failures:
            print("  - %s" % item)
        return 1
    print("ACCEPTANCE: PASS -- the wrapper, ou_sdk and the Python reference all "
          "produce and accept the same bytes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
