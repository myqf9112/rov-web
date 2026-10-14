#include "ou_wrap/ou_link.h"

#include "ou_wrap/sealed_link.hpp"

#include <cstring>
#include <new>

struct ou_link {
    ou::wrap::SealedLink* impl;
};

namespace {

ou::crypto::Key to_key(const uint8_t* key) {
    ou::crypto::Key k{};
    std::memcpy(k.data(), key, k.size());
    return k;
}

}  // namespace

extern "C" {

ou_link* ou_link_create(const uint8_t* key, int side) {
    if (key == nullptr) {
        return nullptr;
    }
    try {
        auto* handle = new ou_link{nullptr};
        handle->impl = new ou::wrap::SealedLink(
            to_key(key),
            side == OU_LINK_SIDE_FC ? ou::wrap::Side::Fc : ou::wrap::Side::Board,
            nullptr);
        return handle;
    } catch (const std::bad_alloc&) {
        return nullptr;
    }
}

void ou_link_destroy(ou_link* link) {
    if (link == nullptr) {
        return;
    }
    delete link->impl;
    delete link;
}

void ou_link_set_start_seq(ou_link* link, uint32_t seq) {
    if (link != nullptr) {
        link->impl->set_start_seq(seq);
    }
}

uint32_t ou_link_tx_sequence(const ou_link* link) {
    return link != nullptr ? link->impl->tx_sequence() : 0;
}

void ou_link_reset_receiver(ou_link* link) {
    if (link != nullptr) {
        link->impl->reset_receiver();
    }
}

size_t ou_link_seal(ou_link* link, const uint8_t* frame, size_t frame_len,
                    uint8_t* out, size_t out_cap) {
    if (link == nullptr || frame == nullptr || out == nullptr) {
        return 0;
    }
    const auto sealed = link->impl->seal(std::span<const uint8_t>(frame, frame_len));
    if (sealed.empty() || sealed.size() > out_cap) {
        return 0;
    }
    std::memcpy(out, sealed.data(), sealed.size());
    return sealed.size();
}

void ou_link_push(ou_link* link, const uint8_t* data, size_t len) {
    if (link == nullptr || data == nullptr || len == 0) {
        return;
    }
    link->impl->push(std::span<const uint8_t>(data, len));
}

int ou_link_next(ou_link* link,
                 uint8_t* plain_out, size_t plain_cap, size_t* plain_len,
                 uint8_t* wire_out, size_t wire_cap, size_t* wire_len) {
    if (plain_len != nullptr) {
        *plain_len = 0;
    }
    if (wire_len != nullptr) {
        *wire_len = 0;
    }
    if (link == nullptr) {
        return 0;
    }

    std::vector<uint8_t> wire;
    std::vector<uint8_t> plain;
    if (!link->impl->next(&wire, &plain)) {
        return 0;
    }
    if (plain.size() > plain_cap || wire.size() > wire_cap) {
        // Caller buffers are undersized: drop rather than truncate a frame into
        // something that would decode as a different message.
        return 0;
    }
    std::memcpy(plain_out, plain.data(), plain.size());
    std::memcpy(wire_out, wire.data(), wire.size());
    if (plain_len != nullptr) {
        *plain_len = plain.size();
    }
    if (wire_len != nullptr) {
        *wire_len = wire.size();
    }
    return 1;
}

void ou_link_get_stats(const ou_link* link, ou_link_stats* out) {
    if (link == nullptr || out == nullptr) {
        return;
    }
    const auto& s = link->impl->stats();
    out->frames_ok = s.frames_ok;
    out->auth_fail = s.auth_fail;
    out->replay = s.replay;
    out->unpad_fail = s.unpad_fail;
    out->resync_bytes = s.resync_bytes;
}

void ou_link_sm3_hmac16(const uint8_t* key, const uint8_t* msg, size_t msg_len,
                        uint8_t out[OU_LINK_TAG_SIZE]) {
    if (key == nullptr || out == nullptr) {
        return;
    }
    ou::crypto::Tag tag{};
    ou::crypto::sm3_hmac(to_key(key),
                         std::span<const uint8_t>(msg, msg == nullptr ? 0 : msg_len),
                         tag);
    std::memcpy(out, tag.data(), tag.size());
}

void ou_link_sm3(const uint8_t* msg, size_t msg_len, uint8_t out[32]) {
    if (out == nullptr) {
        return;
    }
    const auto digest =
        ou::crypto::sm3(std::span<const uint8_t>(msg, msg == nullptr ? 0 : msg_len));
    std::memcpy(out, digest.data(), digest.size());
}

const char* ou_link_version(void) {
    return "ou_sdk_wrapper 0.1.0 (built against ou_sdk 0.4.1, protocol v0.4.0)";
}

}  // extern "C"
