// ou_sdk_wrapper — the "sealed link" layer that ou_sdk 0.4.1 does not ship.
//
// ou_sdk 0.4.1 gives you the pieces but not their composition:
//   ou::crypto::ShellCrypto   seal()/open()  SM4-CBC + HMAC-SM3 frame outer shell
//   ou::channel::FrameChannel raw byte transport (SerialChannel / UdpChannel)
//   ou::link::FrameLink       plaintext frame <-> bytes (FrameParser)
//
// What it does NOT give you is the sealed stream itself: scan for AA55, read the
// length byte, size the shell frame, authenticate, and resync one byte at a time
// when a candidate is rejected. Every consumer would otherwise re-derive that
// logic (and re-derive which way round the flow labels go).
//
// SealedLink is exactly that layer, so a host station or a compute board can
// drop it in and speak the same wire format as the ArduSub v0.4 firmware:
//
//   AA55 | ver(0x04) | len | seq(u32 BE) | IV(16) | SM4-CBC(type|payload|pad) | tag(16)
//     len = plaintext length = 1 + payload_size, ciphertext = 16*(len/16 + 1)
//     tag = HMAC-SM3(key, flow_id|ver|len|seq|IV|ciphertext) truncated to 16
//
// Direction (never on the wire, agreed by both ends):
//   Side::Board (PC / RK3588) : tx = BoardToFc, rx = FcToBoard
//   Side::Fc    (flight ctrl): tx = FcToBoard, rx = BoardToFc
//
// WHERE THE CRYPTO LIVES
// ----------------------
//   inbound  (open)  : ou_sdk's ou::crypto::ShellCrypto::open() end to end --
//                      MAC check, anti-replay window, decrypt, unpad.
//   outbound (seal)  : ou_sdk's own primitives (sm4_encrypt_block, sm3_hmac),
//                      with the frame assembled here.
// Why not ShellCrypto::seal for outbound too? Because ou_sdk exposes no
// set_tx_sequence(), so a host that must resume above the peer's anti-replay
// window either re-seals S times (one SM4+HMAC pass per skipped seq) or cannot
// resume at all. This repo's bench seeds --start-seq from the wall clock
// (~1.8e9, see Tools/ou_bench.py:initial_start_seq) and adds a day per session,
// so "re-seal a few times" is off by six orders of magnitude. The outbound
// assembly below is therefore ours, and Tools/ou_sdk_interop.py pins it
// byte-for-byte against ShellCrypto::seal at seq 0 and against the independent
// Python implementation at arbitrary seq.
//
// The accept/reject decision is always ou_sdk's; the cause classification below
// only labels a rejection after the fact, for the bench dashboard.
#pragma once

#include <ou/crypto.hpp>

#include <cstddef>
#include <cstdint>
#include <span>
#include <vector>

namespace ou::wrap {

enum class Side : std::uint8_t { Board = 0, Fc = 1 };

// Frame geometry of the v0.4 outer shell. Kept here because ou_sdk exposes the
// crypto core but not these derived sizes.
inline constexpr std::size_t kShellHeaderSize = 24;  // AA55|ver|len|seq(4)|IV(16)
inline constexpr std::size_t kShellTagSize = 16;
inline constexpr std::size_t kMaxPlainFrame = 512;
inline constexpr std::size_t kMaxShellFrame = kShellHeaderSize + 256 + kShellTagSize;

struct Stats {
    std::uint64_t frames_ok = 0;     // open() accepted
    std::uint64_t auth_fail = 0;     // HMAC-SM3 tag mismatch
    std::uint64_t replay = 0;        // authentic, but stale/replayed seq
    std::uint64_t unpad_fail = 0;    // authentic and fresh, but bad padding
    std::uint64_t resync_bytes = 0;  // bytes skipped hunting for the next frame
};

class SealedLink {
public:
    static constexpr std::size_t kMaxPendingBytes = 64 * 1024;

    // iv_source = nullptr selects this build's host CSPRNG. A firmware build
    // would inject a hardware RNG. Pass a fixed-IV callable for reproducible
    // bytes (the probe does).
    SealedLink(const ou::crypto::Key& key, Side side,
               ou::crypto::IvSource iv_source = nullptr) noexcept;

    SealedLink(const SealedLink&) = delete;
    SealedLink& operator=(const SealedLink&) = delete;

    // Outbound: wrap one plaintext frame (AA55|ver|len|type|payload).
    // Empty vector when the input is not a valid plaintext frame.
    std::vector<std::uint8_t> seal(std::span<const std::uint8_t> plaintext_frame);

    // Inbound: append raw bytes as read from the link (bounded, drop-oldest).
    void push(std::span<const std::uint8_t> data);

    // Inbound: extract the next authentic frame.
    //   true  -> *sealed_out is the exact wire bytes, *plain_out the plaintext
    //   false -> not enough bytes buffered yet, or nothing authentic in them
    bool next(std::vector<std::uint8_t>* sealed_out, std::vector<std::uint8_t>* plain_out);

    // Receiver restart: accept the next valid frame whatever its seq.
    void reset_receiver() noexcept;

    // The peer's anti-replay window only moves forward, so a host that restarts
    // must resume above the last seq it sent. Any value is accepted; this costs
    // nothing (the sequence is ours to write, not ou_sdk's).
    void set_start_seq(std::uint32_t seq) noexcept { tx_seq_ = seq; }

    std::uint32_t tx_sequence() const noexcept { return tx_seq_; }

    const Stats& stats() const noexcept { return stats_; }

private:
    void diagnose(std::span<const std::uint8_t> shell);
    void next_iv(ou::crypto::Iv& out);

    ou::crypto::Key key_;
    ou::crypto::FlowId rx_flow_;
    ou::crypto::FlowId tx_flow_;
    ou::crypto::IvSource iv_source_ = nullptr;
    ou::crypto::ShellCrypto rx_;
    std::uint32_t tx_seq_ = 0;    // ours: see "WHERE THE CRYPTO LIVES"
    std::vector<std::uint8_t> buf_;
    Stats stats_{};
    std::uint32_t last_seq_ = 0;  // mirror of accepted seqs, for classification
    bool rx_ready_ = false;       // mirror of the replay window's ready flag
};

}  // namespace ou::wrap
