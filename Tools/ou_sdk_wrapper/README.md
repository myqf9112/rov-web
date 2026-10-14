# ou_sdk_wrapper — the sealed-link layer ou_sdk 0.4.1 does not ship

`ou_sdk` gives you the pieces but not their composition:

| ou_sdk 0.4.1 component | what it does |
| --- | --- |
| `ou::crypto::ShellCrypto` | `seal()` / `open()` — SM4-CBC + HMAC-SM3 frame outer shell |
| `ou::channel::FrameChannel` | raw byte transport (`SerialChannel`, `UdpChannel`) |
| `ou::link::FrameLink` | plaintext frame ⟷ bytes (`FrameParser`) |

What no component does is **the sealed stream itself**: scan for `AA55`, read the
length byte, size the shell frame, authenticate, and — when a candidate is
rejected — step forward one byte and try again. Every consumer would otherwise
re-derive that (and re-derive which way round the flow labels go, where a slip
is invisible until nothing decrypts).

`SealedLink` is exactly that layer, so a host station, an RK3588 or an MCU can
drop it in and speak the same wire format as the ArduSub v0.4 firmware:

```
AA55 | ver(0x04) | len | seq(u32 BE) | IV(16) | SM4-CBC(type|payload|pad) | tag(16)
  len          = plaintext length = 1 + payload_size
  ciphertext   = 16 * (len / 16 + 1)
  tag          = HMAC-SM3(key, flow_id|ver|len|seq|IV|ciphertext) truncated to 16
  flow_id      = never on the wire; agreed by direction
```

Direction table (`SealedLink::Side`):

| endpoint | tx flow | rx flow |
| --- | --- | --- |
| `Side::Board` — PC / RK3588 / host | `BoardToFc` (0x03) | `FcToBoard` (0x04) |
| `Side::Fc` — flight controller | `FcToBoard` (0x04) | `BoardToFc` (0x03) |

## Build

Get the SDK artifact first (Harbor, `oras`): `ou_sdk-headers-0.4.1.tar.gz` and
`ou_sdk-x86_64-0.4.1.tar.gz`, then lay them out as `include/` + `lib/`:

```sh
mkdir -p ~/ou-sdk-0.4.1 && tar -xf ou_sdk-headers-0.4.1.tar.gz -C ~/ou-sdk-0.4.1
tar -xf ou_sdk-x86_64-0.4.1.tar.gz -C ~/ou-sdk-0.4.1
export OU_SDK_ROOT=~/ou-sdk-0.4.1
```

```sh
# CMake (preferred)
cmake -S Tools/ou_sdk_wrapper -B Tools/ou_sdk_wrapper/build -DOU_SDK_ROOT=$OU_SDK_ROOT
cmake --build Tools/ou_sdk_wrapper/build -j

# or, without CMake
make -C Tools/ou_sdk_wrapper OU_SDK_ROOT=$OU_SDK_ROOT
```

Both drop `libou_link_wrap.so` in `Tools/ou_sdk_wrapper/build/`, which is where
`Tools/ou_sdk_bridge.py` looks. The rpath points at `$OU_SDK_ROOT/lib`, so no
`LD_LIBRARY_PATH` is needed while the SDK stays put.

## Verify

```sh
python3 Tools/ou_sdk_interop.py          # wrapper vs ou_sdk vs Python reference
python3 Tools/ou_sdk_bridge.py --self-test
Tools/ou_sdk_wrapper/build/ou_link_probe --selftest
```

`ou_sdk_interop.py` byte-compares the wrapper's `seal` output against the
independent pure-Python implementation in `Tools/ou_crypto.py` for all 16 golden
frames, and round-trips them both ways with live IVs.

## C++

```cpp
#include "ou_wrap/sealed_link.hpp"

ou::crypto::Key key = /* 16 bytes */;
ou::wrap::SealedLink link(key, ou::wrap::Side::Board);   // nullptr IV source = host CSPRNG

auto shell = link.seal(plaintext_frame);                 // AA55|ver|len|type|payload
transport.write(shell);

link.push(bytes_from_transport);
std::vector<uint8_t> wire, plain;
while (link.next(&wire, &plain)) {
    // wire is the exact bytes on the wire, plain is the decoded frame
}
```

## C ABI

`include/ou_wrap/ou_link.h` — for ctypes, C, or any non-C++ consumer. Opaque
handle, caller-owned buffers, nothing throws across the boundary:

```c
ou_link* link = ou_link_create(key16, OU_LINK_SIDE_BOARD);
ou_link_set_start_seq(link, last_seq + 1);      // resume above the peer's window
size_t n = ou_link_seal(link, frame, frame_len, out, sizeof out);
ou_link_push(link, rx, rx_len);
int got = ou_link_next(link, plain, sizeof plain, &plain_len,
                       wire, sizeof wire, &wire_len);
ou_link_stats st; ou_link_get_stats(link, &st);
ou_link_destroy(link);
```

## Python

`Tools/ou_sdk_bridge.py` is a drop-in for `ou_crypto.SerialShell`, so
`Tools/ou_dashboard.py --decoder sdk` and `Tools/ou_serial_test.py --decoder sdk`
run the browser UI and the CLI unchanged while the vendor SDK does the
authenticating and decrypting:

```sh
python3 Tools/ou_dashboard.py --port /dev/ttyUSB0 --key OU_SERIAL_KEY_01 --decoder sdk
```

## What is whose

| concern | owner |
| --- | --- |
| **inbound**: MAC check, anti-replay window, decrypt, unpad | **ou_sdk 0.4.1** — `ShellCrypto::open()` end to end |
| **outbound**: SM4-CBC, HMAC-SM3, padding | **ou_sdk 0.4.1 primitives** — `sm4_encrypt_block`, `sm3_hmac` |
| **outbound**: frame assembly and the tx sequence | **this wrapper** (see below) |
| shell frame layout, flow direction | **ou_sdk 0.4.1** |
| stream scanning, resync policy, buffers | **this wrapper** |
| rejection *classification* for the bench UI | **this wrapper** — `open()` is still the accept/reject authority; `auth_fail` is re-derived with the SDK's own `sm3_hmac`, and `replay` vs `unpad_fail` splits the remainder using a mirror of the accepted-seq window |

### Why outbound is assembled here

`ou_sdk` exposes `tx_sequence()` but no setter, and `ShellCrypto::seal()` is the
only way in. A host that must resume above the peer's anti-replay window could
therefore only re-seal once per skipped seq — and this repo's bench seeds
`--start-seq` from the wall clock (`Tools/ou_bench.py:initial_start_seq` adds a
day per session on top of `time.time()`), i.e. **~1.8e9**. That is not "a few
extra seals", it is hours.

So the outbound frame is assembled here from the SDK's own primitives, which
makes the tx sequence ours to write. That equivalence is pinned, not assumed:

* `ou_link_probe --selftest` diffs it against `ShellCrypto::seal` at seq 0 for
  all 16 golden frames — byte-identical;
* `Tools/ou_sdk_interop.py` diffs it against the independent Python
  implementation at seq 1792378051 — byte-identical.

Consequence for threading: the wrapper is safe for one sealing thread plus one
reader thread (the dashboard's shape), because `tx_seq_` and `rx_`/buffers are
disjoint. It is not a general-purpose thread-safe queue.

## Not settled yet

* Which `flow_id` the two ends actually agree on for uploads vs downloads —
  the golden vectors pin the frame bodies, not the flow labels. A mismatch is
  loud (100% tag failures), not silent.
* Whether any framing exists *inside* the sealed plaintext beyond
  `AA55|ver|len|type|payload` when a board multiplexes several links.
