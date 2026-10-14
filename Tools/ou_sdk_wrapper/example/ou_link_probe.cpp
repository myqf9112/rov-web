// ou_link_probe — command-line interop probe for the ou_sdk 0.4.1 sealed link.
//
//   ou_link_probe seal <plaintext-frame-hex> [board|fc] [seq] -> shell frame hex
//   ou_link_probe open <shell-frame-hex>     [board|fc]        -> plaintext frame hex | FAIL
//   ou_link_probe --selftest                                   -> golden + shell checks
//   ou_link_probe version
//
// seal() uses a fixed IV so the output is deterministic and can be diffed
// byte-for-byte against an independent implementation (Tools/ou_crypto.py).
// [seq] sets the outgoing sequence, so arbitrary --start-seq values are
// diffable too.
#include "ou_wrap/sealed_link.hpp"

#include <golden/golden.h>
#include <ou/proto.hpp>

#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>
#include <vector>

namespace {

void fixed_iv(ou::crypto::Iv& out) {
    for (size_t i = 0; i < out.size(); ++i) {
        out[i] = static_cast<uint8_t>(0x10 + i);
    }
}

ou::crypto::Key fixed_key() {
    ou::crypto::Key key{};
    for (size_t i = 0; i < key.size(); ++i) {
        key[i] = static_cast<uint8_t>(i);
    }
    return key;
}

int nib(char c) {
    if (c >= '0' && c <= '9') return c - '0';
    if (c >= 'a' && c <= 'f') return c - 'a' + 10;
    if (c >= 'A' && c <= 'F') return c - 'A' + 10;
    return -1;
}

std::vector<uint8_t> from_hex(const char* s) {
    std::vector<uint8_t> out;
    for (const char* p = s; p[0] != '\0' && p[1] != '\0'; p += 2) {
        const int hi = nib(p[0]);
        const int lo = nib(p[1]);
        if (hi < 0 || lo < 0) break;
        out.push_back(static_cast<uint8_t>(hi * 16 + lo));
    }
    return out;
}

std::string to_hex(const std::vector<uint8_t>& v) {
    static const char* kDigits = "0123456789abcdef";
    std::string s;
    s.reserve(v.size() * 2);
    for (uint8_t b : v) {
        s.push_back(kDigits[b >> 4]);
        s.push_back(kDigits[b & 0x0F]);
    }
    return s;
}

uint32_t be32(const uint8_t* p) {
    return (static_cast<uint32_t>(p[0]) << 24) | (static_cast<uint32_t>(p[1]) << 16) |
           (static_cast<uint32_t>(p[2]) << 8) | static_cast<uint32_t>(p[3]);
}

ou::wrap::Side parse_side(int argc, char** argv) {
    return (argc >= 4 && std::strcmp(argv[3], "fc") == 0) ? ou::wrap::Side::Fc
                                                        : ou::wrap::Side::Board;
}

struct GoldenCase {
    const char* name;
    uint8_t type;
    const uint8_t* frame;
    size_t len;
};

const GoldenCase kGolden[] = {
    {"Heartbeat", 0x50, OU_GOLDEN_HEARTBEAT_FRAME, OU_GOLDEN_HEARTBEAT_FRAME_LEN},
    {"SysStatus", 0x10, OU_GOLDEN_SYSSTATUS_FRAME, OU_GOLDEN_SYSSTATUS_FRAME_LEN},
    {"CommandAck", 0x51, OU_GOLDEN_COMMANDACK_FRAME, OU_GOLDEN_COMMANDACK_FRAME_LEN},
    {"PoseNed", 0x13, OU_GOLDEN_POSENED_FRAME, OU_GOLDEN_POSENED_FRAME_LEN},
    {"EkfStatusReport", 0x14, OU_GOLDEN_EKFSTATUSREPORT_FRAME,
     OU_GOLDEN_EKFSTATUSREPORT_FRAME_LEN},
    {"VfrHud", 0x15, OU_GOLDEN_VFRHUD_FRAME, OU_GOLDEN_VFRHUD_FRAME_LEN},
    {"GlobalPositionInt", 0x16, OU_GOLDEN_GLOBALPOSITIONINT_FRAME,
     OU_GOLDEN_GLOBALPOSITIONINT_FRAME_LEN},
    {"GpsRawInt", 0x18, OU_GOLDEN_GPSRAWINT_FRAME, OU_GOLDEN_GPSRAWINT_FRAME_LEN},
    {"WaterDepth", 0x19, OU_GOLDEN_WATERDEPTH_FRAME, OU_GOLDEN_WATERDEPTH_FRAME_LEN},
    {"DistanceSensor", 0x52, OU_GOLDEN_DISTANCESENSOR_FRAME,
     OU_GOLDEN_DISTANCESENSOR_FRAME_LEN},
    {"ManualControl", 0x30, OU_GOLDEN_MANUALCONTROL_FRAME,
     OU_GOLDEN_MANUALCONTROL_FRAME_LEN},
    {"Command", 0x32, OU_GOLDEN_COMMAND_FRAME, OU_GOLDEN_COMMAND_FRAME_LEN},
    {"RcChannels", 0x1A, OU_GOLDEN_RCCHANNELS_FRAME, OU_GOLDEN_RCCHANNELS_FRAME_LEN},
    {"ServoOutputRaw", 0x1B, OU_GOLDEN_SERVOOUTPUTRAW_FRAME,
     OU_GOLDEN_SERVOOUTPUTRAW_FRAME_LEN},
    {"ParamSet", 0x33, OU_GOLDEN_PARAMSET_FRAME, OU_GOLDEN_PARAMSET_FRAME_LEN},
    {"ParamValue", 0x1D, OU_GOLDEN_PARAMVALUE_FRAME, OU_GOLDEN_PARAMVALUE_FRAME_LEN},
};

int selftest() {
    int failures = 0;
    const auto key = fixed_key();

    // 1) Every golden frame must parse with ou_sdk's own validator.
    for (const auto& c : kGolden) {
        const std::span<const uint8_t> frame(c.frame, c.len);
        const auto payload = ou::frame_payload(frame);
        const bool ok = !payload.empty() && ou::frame_type(frame) == c.type &&
                        payload.size() == c.len - ou::kFrameOverhead;
        std::printf("  %-18s type=0x%02X len=%-3zu %s\n", c.name, c.type, c.len,
                    ok ? "ok" : "FAIL");
        if (!ok) {
            ++failures;
        }
    }

    // 2) Seal then open must round-trip through the SDK's shell, both sides.
    for (const auto& c : kGolden) {
        ou::wrap::SealedLink fc_side(key, ou::wrap::Side::Fc, fixed_iv);
        ou::wrap::SealedLink board_side(key, ou::wrap::Side::Board, fixed_iv);
        const std::span<const uint8_t> frame(c.frame, c.len);
        const auto shell = fc_side.seal(frame);
        if (shell.empty()) {
            std::printf("  %-18s seal FAIL\n", c.name);
            ++failures;
            continue;
        }
        board_side.push(shell);
        std::vector<uint8_t> wire, plain;
        if (!board_side.next(&wire, &plain) || plain.size() != c.len ||
            std::memcmp(plain.data(), c.frame, c.len) != 0) {
            std::printf("  %-18s round-trip FAIL\n", c.name);
            ++failures;
        }
    }

    // 2b) The outbound assembly (our CBC + padding + MAC input, on ou_sdk's
    //     sm4_encrypt_block/sm3_hmac) must equal ou_sdk's own ShellCrypto::seal
    //     byte for byte. A fresh ShellCrypto starts at seq 0, so this pins the
    //     whole layout against the real thing rather than against our reading of
    //     it.
    for (const auto& c : kGolden) {
        const ou::crypto::Key key = fixed_key();
        ou::wrap::SealedLink mine(key, ou::wrap::Side::Fc, fixed_iv);
        ou::crypto::ShellCrypto theirs(key, ou::crypto::FlowId::FcToBoard, fixed_iv);
        const std::span<const uint8_t> frame(c.frame, c.len);
        const auto ours = mine.seal(frame);
        const auto reference = theirs.seal(frame);
        const bool ok = !ours.empty() && ours == reference;
        std::printf("  %-18s seal == ShellCrypto %s\n", c.name, ok ? "ok" : "FAIL");
        if (!ok) {
            ++failures;
        }
    }

    // 3) A frame sealed for one direction must not open in the other.
    {
        ou::wrap::SealedLink a(key, ou::wrap::Side::Fc, fixed_iv);
        ou::wrap::SealedLink b(key, ou::wrap::Side::Fc, fixed_iv);  // same direction
        const std::span<const uint8_t> frame(kGolden[0].frame, kGolden[0].len);
        b.push(a.seal(frame));
        std::vector<uint8_t> wire, plain;
        const bool opened = b.next(&wire, &plain);
        std::printf("  direction binding  %s\n", opened ? "FAIL (accepted)" : "ok (rejected)");
        if (opened) {
            ++failures;
        }
    }

    // 4) Resync: junk prefix must be skipped, then the frame must come out.
    {
        ou::wrap::SealedLink a(key, ou::wrap::Side::Fc, fixed_iv);
        ou::wrap::SealedLink b(key, ou::wrap::Side::Board, fixed_iv);
        const std::span<const uint8_t> frame(kGolden[0].frame, kGolden[0].len);
        const auto shell = a.seal(frame);
        const uint8_t junk[] = {0x00, 0xAA, 0x11, 0x55, 0x42};
        b.push(junk);
        b.push(shell);
        std::vector<uint8_t> wire, plain;
        const bool ok = b.next(&wire, &plain) && plain.size() == frame.size() &&
                        std::memcmp(plain.data(), frame.data(), frame.size()) == 0;
        std::printf("  resync over junk   %s (resync_bytes=%llu)\n",
                    ok ? "ok" : "FAIL",
                    static_cast<unsigned long long>(b.stats().resync_bytes));
        if (!ok) {
            ++failures;
        }
    }

    // 5) A tampered tag must be rejected as auth_fail (not accepted).
    {
        ou::wrap::SealedLink a(key, ou::wrap::Side::Fc, fixed_iv);
        ou::wrap::SealedLink b(key, ou::wrap::Side::Board, fixed_iv);
        const std::span<const uint8_t> frame(kGolden[0].frame, kGolden[0].len);
        auto shell = a.seal(frame);
        shell.back() ^= 0x01;
        b.push(shell);
        std::vector<uint8_t> wire, plain;
        const bool opened = b.next(&wire, &plain);
        const bool classified = b.stats().auth_fail == 1;
        std::printf("  tampered tag       %s (auth_fail=%llu)\n",
                    (!opened && classified) ? "ok" : "FAIL",
                    static_cast<unsigned long long>(b.stats().auth_fail));
        if (opened || !classified) {
            ++failures;
        }
    }

    // 6) --start-seq must accept any 32-bit value, including the wall-clock
    //    sized seqs this repo's bench seeds (Tools/ou_bench.py) -- and must not
    //    cost one seal per skipped seq.
    {
        const uint32_t wanted = 1792378051u;
        ou::wrap::SealedLink link(fixed_key(), ou::wrap::Side::Fc, fixed_iv);
        link.set_start_seq(wanted);
        const std::span<const uint8_t> frame(kGolden[0].frame, kGolden[0].len);
        const auto shell = link.seal(frame);
        const bool ok = !shell.empty() && be32(shell.data() + 4) == wanted &&
                        link.tx_sequence() == wanted + 1u;
        std::printf("  bench-sized seq    %s (seq=%u, next=%u)\n", ok ? "ok" : "FAIL",
                    ok ? be32(shell.data() + 4) : 0u, link.tx_sequence());
        if (!ok) {
            ++failures;
        }
    }

    // 7) A bench-sized seq must still produce a frame the SDK accepts, with the
    //    replay window starting fresh (that is the whole point of --start-seq).
    {
        const uint32_t wanted = 1792378051u;
        ou::wrap::SealedLink sender(fixed_key(), ou::wrap::Side::Fc, fixed_iv);
        ou::wrap::SealedLink receiver(fixed_key(), ou::wrap::Side::Board, fixed_iv);
        sender.set_start_seq(wanted);
        const std::span<const uint8_t> frame(kGolden[0].frame, kGolden[0].len);
        receiver.push(sender.seal(frame));
        std::vector<uint8_t> wire, plain;
        const bool ok = receiver.next(&wire, &plain) && plain.size() == frame.size() &&
                        std::memcmp(plain.data(), frame.data(), frame.size()) == 0;
        std::printf("  bench-sized seq open %s (auth_fail=%llu)\n", ok ? "ok" : "FAIL",
                    static_cast<unsigned long long>(receiver.stats().auth_fail));
        if (!ok) {
            ++failures;
        }
    }

    std::printf("\nou_sdk_wrapper selftest: %s (%d failure(s))\n",
                failures == 0 ? "PASS" : "FAIL", failures);
    return failures == 0 ? 0 : 1;
}

}  // namespace

int main(int argc, char** argv) {
    if (argc < 2) {
        std::fprintf(stderr, "usage: %s seal|open <hex> [board|fc] [seq] | --selftest | version\n",
                     argv[0]);
        return 2;
    }
    if (std::strcmp(argv[1], "version") == 0) {
        std::printf("wrapper: ou_sdk_wrapper 0.1.0\nsdk: ou_sdk-0.4.1 headers, protocol v0.4.0\n");
        return 0;
    }
    if (std::strcmp(argv[1], "--selftest") == 0) {
        return selftest();
    }
    if (argc < 3) {
        std::fprintf(stderr, "usage: %s seal|open <hex> [board|fc] [seq]\n", argv[0]);
        return 2;
    }

    const auto side = parse_side(argc, argv);
    const auto bytes = from_hex(argv[2]);
    if (bytes.empty()) {
        std::fprintf(stderr, "bad hex\n");
        return 2;
    }

    ou::wrap::SealedLink link(fixed_key(), side, fixed_iv);
    if (std::strcmp(argv[1], "seal") == 0) {
        if (argc >= 5) {
            // [seq]: the outgoing sequence to start at. This is what
            // --start-seq needs, and what ou_sdk's ShellCrypto cannot do.
            link.set_start_seq(static_cast<uint32_t>(std::strtoul(argv[4], nullptr, 0)));
        }
        const auto shell = link.seal(std::span<const uint8_t>(bytes.data(), bytes.size()));
        if (shell.empty()) {
            std::printf("FAIL\n");
            return 1;
        }
        std::printf("%s\n", to_hex(shell).c_str());
        return 0;
    }

    std::vector<uint8_t> wire, plain;
    link.push(bytes);
    if (!link.next(&wire, &plain)) {
        std::printf("FAIL\n");
        return 1;
    }
    std::printf("%s\n", to_hex(plain).c_str());
    return 0;
}
