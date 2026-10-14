/* ou_link.h — C ABI over the ou_sdk 0.4.1 sealed link.
 *
 * ou_sdk is a C++20 closed-source shared library, so a Python/ctypes dashboard
 * (or any other language, or an MCU-side integration) needs a flat entry point.
 * This is it: an opaque handle plus the seven calls the host tools need.
 *
 * Every function is noexcept-by-contract: it never throws across the boundary
 * and never allocates on the caller's behalf. Buffers are caller-owned.
 */
#ifndef OU_WRAP_LINK_H
#define OU_WRAP_LINK_H

#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

/* Frame geometry (v0.4 outer shell). */
#define OU_LINK_HEADER_SIZE 24u /* AA55 | ver | len | seq(4) | IV(16) */
#define OU_LINK_TAG_SIZE 16u
#define OU_LINK_MAX_PLAIN 512u
#define OU_LINK_MAX_SHELL 296u

#define OU_LINK_SIDE_BOARD 0
#define OU_LINK_SIDE_FC 1

typedef struct ou_link ou_link;

typedef struct ou_link_stats {
    uint64_t frames_ok;    /* open() accepted */
    uint64_t auth_fail;    /* HMAC-SM3 tag mismatch */
    uint64_t replay;       /* authentic, stale seq */
    uint64_t unpad_fail;   /* authentic, fresh seq, bad padding */
    uint64_t resync_bytes; /* bytes skipped hunting for the next frame */
} ou_link_stats;

/* Create a link endpoint. key is 16 bytes; side is OU_LINK_SIDE_BOARD (host /
 * RK3588: tx BoardToFc, rx FcToBoard) or OU_LINK_SIDE_FC (the flight controller).
 * Returns NULL on NULL key. The outbound IV comes from ou_sdk's host CSPRNG. */
ou_link* ou_link_create(const uint8_t* key, int side);

void ou_link_destroy(ou_link* link);

/* Sender's next seq. A restarted host must resume above the last seq it sent,
 * because the peer's anti-replay window only ever moves forward. */
void ou_link_set_start_seq(ou_link* link, uint32_t seq);
uint32_t ou_link_tx_sequence(const ou_link* link);

/* Receiver restart: accept the next valid frame whatever its seq. */
void ou_link_reset_receiver(ou_link* link);

/* Wrap one plaintext frame (AA55|ver|len|type|payload) into a shell frame.
 * Returns the shell length written to out, or 0 on failure. */
size_t ou_link_seal(ou_link* link, const uint8_t* frame, size_t frame_len,
                    uint8_t* out, size_t out_cap);

/* Append raw bytes as read from the link. Bounded, drop-oldest. */
void ou_link_push(ou_link* link, const uint8_t* data, size_t len);

/* Extract the next authentic frame.
 * Returns 1 when a frame was produced (plain_out/wire_out filled), 0 when more
 * bytes are needed. wire_out receives the exact wire bytes, so a bench tool can
 * show the sealed frame next to the decoded values. */
int ou_link_next(ou_link* link,
                 uint8_t* plain_out, size_t plain_cap, size_t* plain_len,
                 uint8_t* wire_out, size_t wire_cap, size_t* wire_len);

/* Cumulative counters. */
void ou_link_get_stats(const ou_link* link, ou_link_stats* out);

/* HMAC-SM3 truncated to 16 bytes, straight from ou_sdk's crypto core. Lets a
 * consumer check at startup that its key derivation agrees with the SDK. */
void ou_link_sm3_hmac16(const uint8_t* key, const uint8_t* msg, size_t msg_len,
                        uint8_t out[OU_LINK_TAG_SIZE]);

/* SM3 digest, 32 bytes. */
void ou_link_sm3(const uint8_t* msg, size_t msg_len, uint8_t out[32]);

/* Human-readable SDK/components version this wrapper was built against. */
const char* ou_link_version(void);

#ifdef __cplusplus
}
#endif

#endif /* OU_WRAP_LINK_H */
