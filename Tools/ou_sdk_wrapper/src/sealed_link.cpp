#include "ou_wrap/sealed_link.hpp"

#include <algorithm>
#include <cstring>
#include <random>

namespace ou::wrap {

namespace {

constexpr std::size_t kBlockSize = 16;

std::size_t ciphertext_len(std::uint8_t len_byte) {
    return kBlockSize * (static_cast<std::size_t>(len_byte) / kBlockSize + 1);
}

std::size_t shell_frame_size(std::uint8_t len_byte) {
    return kShellHeaderSize + ciphertext_len(len_byte) + kShellTagSize;
}

std::uint32_t be32(const std::uint8_t* p) {
    return (static_cast<std::uint32_t>(p[0]) << 24) |
           (static_cast<std::uint32_t>(p[1]) << 16) |
           (static_cast<std::uint32_t>(p[2]) << 8) |
           static_cast<std::uint32_t>(p[3]);
}

void put_be32(std::uint8_t* p, std::uint32_t v) {
    p[0] = static_cast<std::uint8_t>((v >> 24) & 0xFF);
    p[1] = static_cast<std::uint8_t>((v >> 16) & 0xFF);
    p[2] = static_cast<std::uint8_t>((v >> 8) & 0xFF);
    p[3] = static_cast<std::uint8_t>(v & 0xFF);
}

bool constant_time_equal(std::span<const std::uint8_t> a, std::span<const std::uint8_t> b) {
    if (a.size() != b.size()) {
        return false;
    }
    std::uint8_t diff = 0;
    for (std::size_t i = 0; i < a.size(); ++i) {
        diff = static_cast<std::uint8_t>(diff | (a[i] ^ b[i]));
    }
    return diff == 0;
}

// tag = HMAC-SM3(key, flow_id | ver | len | seq(4 BE) | IV | ciphertext)
void mac_input(ou::crypto::FlowId flow, std::uint8_t ver, std::uint8_t length,
               std::uint32_t seq, const ou::crypto::Iv& iv,
               std::span<const std::uint8_t> ciphertext,
               std::vector<std::uint8_t>& out) {
    out.clear();
    out.reserve(3 + 4 + iv.size() + ciphertext.size());
    out.push_back(static_cast<std::uint8_t>(flow));
    out.push_back(ver);
    out.push_back(length);
    std::uint8_t seq_be[4];
    put_be32(seq_be, seq);
    out.insert(out.end(), seq_be, seq_be + 4);
    out.insert(out.end(), iv.begin(), iv.end());
    out.insert(out.end(), ciphertext.begin(), ciphertext.end());
}

// PKCS#7: always appends at least one byte (matches ShellCrypto).
std::vector<std::uint8_t> pkcs7_pad(std::span<const std::uint8_t> body) {
    const std::size_t pad = kBlockSize - (body.size() % kBlockSize);
    std::vector<std::uint8_t> out(body.begin(), body.end());
    out.insert(out.end(), pad, static_cast<std::uint8_t>(pad));
    return out;
}

// SM4-CBC built from ou_sdk's single-block primitive: c[i] = E(p[i] ^ c[i-1]).
std::vector<std::uint8_t> cbc_encrypt(const ou::crypto::Key& key, const ou::crypto::Iv& iv,
                                      std::span<const std::uint8_t> plaintext) {
    std::vector<std::uint8_t> out(plaintext.size());
    ou::crypto::Block prev = iv;
    for (std::size_t off = 0; off < plaintext.size(); off += kBlockSize) {
        ou::crypto::Block blk{};
        for (std::size_t i = 0; i < kBlockSize; ++i) {
            blk[i] = static_cast<std::uint8_t>(plaintext[off + i] ^ prev[i]);
        }
        ou::crypto::Block enc{};
        ou::crypto::sm4_encrypt_block(key, blk, enc);
        std::memcpy(out.data() + off, enc.data(), kBlockSize);
        prev = enc;
    }
    return out;
}

}  // namespace

SealedLink::SealedLink(const ou::crypto::Key& key, Side side,
                       ou::crypto::IvSource iv_source) noexcept
    : key_(key),
      rx_flow_(side == Side::Fc ? ou::crypto::FlowId::BoardToFc
                                : ou::crypto::FlowId::FcToBoard),
      tx_flow_(side == Side::Fc ? ou::crypto::FlowId::FcToBoard
                                : ou::crypto::FlowId::BoardToFc),
      iv_source_(iv_source),
      rx_(key, side == Side::Fc ? ou::crypto::FlowId::BoardToFc
                                : ou::crypto::FlowId::FcToBoard,
          iv_source) {}

void SealedLink::next_iv(ou::crypto::Iv& out) {
    if (iv_source_ != nullptr) {
        iv_source_(out);
        return;
    }
    // IVs are transmitted in the clear, so unpredictability is all that matters.
    // std::random_device is the platform CSPRNG (/dev/urandom on Linux).
    std::random_device rd;
    for (auto& byte : out) {
        byte = static_cast<std::uint8_t>(rd());
    }
}

std::vector<std::uint8_t> SealedLink::seal(std::span<const std::uint8_t> plaintext_frame) {
    // Byte-for-byte mirror of ou::crypto::ShellCrypto::seal, except that the tx
    // sequence comes from our counter instead of ou_sdk's (see the header for
    // why). Verified against ShellCrypto::seal at seq 0 and against the Python
    // reference at arbitrary seq by Tools/ou_sdk_interop.py.
    if (plaintext_frame.size() < 5 || plaintext_frame[0] != 0xAA ||
        plaintext_frame[1] != 0x55) {
        return {};
    }
    const std::uint8_t ver = plaintext_frame[2];
    const std::uint8_t inner_len = plaintext_frame[3];
    if (plaintext_frame.size() != 5u + inner_len) {
        return {};
    }
    const std::size_t length = static_cast<std::size_t>(inner_len) + 1;
    if (length > 0xFFu) {
        return {};
    }
    const auto body = plaintext_frame.subspan(4, length);

    const std::uint32_t seq = tx_seq_;
    tx_seq_ = tx_seq_ + 1u;  // wraps at 2^32, like the SDK's counter

    ou::crypto::Iv iv{};
    next_iv(iv);

    const auto ct = cbc_encrypt(key_, iv, pkcs7_pad(body));

    std::vector<std::uint8_t> mac;
    mac_input(tx_flow_, ver, static_cast<std::uint8_t>(length), seq, iv, ct, mac);

    ou::crypto::Tag tag{};
    ou::crypto::sm3_hmac(key_, mac, tag);

    std::vector<std::uint8_t> shell;
    shell.reserve(kShellHeaderSize + ct.size() + kShellTagSize);
    shell.push_back(0xAA);
    shell.push_back(0x55);
    shell.push_back(ver);
    shell.push_back(static_cast<std::uint8_t>(length));
    std::uint8_t seq_be[4];
    put_be32(seq_be, seq);
    shell.insert(shell.end(), seq_be, seq_be + 4);
    shell.insert(shell.end(), iv.begin(), iv.end());
    shell.insert(shell.end(), ct.begin(), ct.end());
    shell.insert(shell.end(), tag.begin(), tag.end());
    return shell;
}

void SealedLink::push(std::span<const std::uint8_t> data) {
    if (data.empty()) {
        return;
    }
    if (data.size() >= kMaxPendingBytes) {
        buf_.assign(data.end() - static_cast<std::ptrdiff_t>(kMaxPendingBytes), data.end());
        return;
    }
    if (buf_.size() + data.size() > kMaxPendingBytes) {
        const std::size_t drop = buf_.size() + data.size() - kMaxPendingBytes;
        buf_.erase(buf_.begin(), buf_.begin() + static_cast<std::ptrdiff_t>(drop));
    }
    buf_.insert(buf_.end(), data.begin(), data.end());
}

bool SealedLink::next(std::vector<std::uint8_t>* sealed_out,
                      std::vector<std::uint8_t>* plain_out) {
    if (sealed_out != nullptr) {
        sealed_out->clear();
    }
    if (plain_out != nullptr) {
        plain_out->clear();
    }

    while (buf_.size() >= 2) {
        // Resync to the next AA55.
        std::size_t start = 0;
        while (start + 1 < buf_.size() &&
               !(buf_[start] == 0xAA && buf_[start + 1] == 0x55)) {
            ++start;
        }
        if (start > 0) {
            buf_.erase(buf_.begin(), buf_.begin() + static_cast<std::ptrdiff_t>(start));
            stats_.resync_bytes += start;
        }
        if (buf_.size() < kShellHeaderSize) {
            return false;
        }

        const std::uint8_t length = buf_[3];
        if (length == 0) {
            buf_.erase(buf_.begin());
            ++stats_.resync_bytes;
            continue;
        }
        const std::size_t total = shell_frame_size(length);
        if (buf_.size() < total) {
            return false;  // half a frame: wait for more bytes
        }

        std::vector<std::uint8_t> candidate(
            buf_.begin(), buf_.begin() + static_cast<std::ptrdiff_t>(total));
        auto opened = rx_.open(
            std::span<const std::uint8_t>(candidate.data(), candidate.size()));
        if (!opened.has_value()) {
            diagnose(std::span<const std::uint8_t>(candidate.data(), candidate.size()));
            buf_.erase(buf_.begin());  // one byte at a time, so a false AA55 cannot
            ++stats_.resync_bytes;      // make us swallow a real frame after it
            continue;
        }

        last_seq_ = be32(candidate.data() + 4);
        rx_ready_ = true;
        buf_.erase(buf_.begin(), buf_.begin() + static_cast<std::ptrdiff_t>(total));
        ++stats_.frames_ok;
        if (sealed_out != nullptr) {
            *sealed_out = std::move(candidate);
        }
        if (plain_out != nullptr) {
            *plain_out = std::move(*opened);
        }
        return true;
    }
    return false;
}

void SealedLink::reset_receiver() noexcept {
    rx_.reset_receiver();
    last_seq_ = 0;
    rx_ready_ = false;
}

void SealedLink::diagnose(std::span<const std::uint8_t> shell) {
    // open() already rejected this candidate. Classify why, so the dashboard can
    // still show the "silent failure" breakdown it shows for the Python shell.
    // The accept/reject decision itself is ou_sdk's; this only names the cause.
    if (shell.size() < kShellHeaderSize) {
        ++stats_.auth_fail;
        return;
    }
    const std::uint8_t ver = shell[2];
    const std::uint8_t length = shell[3];
    if (length == 0 || shell.size() != shell_frame_size(length)) {
        ++stats_.auth_fail;
        return;
    }

    const std::size_t ct_len = ciphertext_len(length);
    const std::uint32_t seq = be32(shell.data() + 4);

    std::vector<std::uint8_t> mac;
    ou::crypto::Iv iv{};
    std::memcpy(iv.data(), shell.data() + 8, iv.size());
    mac_input(rx_flow_, ver, length, seq, iv,
              std::span<const std::uint8_t>(shell.data() + kShellHeaderSize, ct_len), mac);

    ou::crypto::Tag expect{};
    ou::crypto::sm3_hmac(key_, mac, expect);
    const std::span<const std::uint8_t> got(
        shell.data() + kShellHeaderSize + ct_len, kShellTagSize);
    if (!constant_time_equal(std::span<const std::uint8_t>(expect.data(), expect.size()),
                             got)) {
        ++stats_.auth_fail;
        return;
    }
    // The tag is authentic, so open() can only have rejected it as stale (the
    // replay window) or as malformed padding.
    if (rx_ready_ && seq <= last_seq_) {
        ++stats_.replay;
        return;
    }
    ++stats_.unpad_fail;
}

}  // namespace ou::wrap
