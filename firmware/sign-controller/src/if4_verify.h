// IF-4 sign-link frame verify -- the C mirror of software/esw/if4.py::verify()
// (doc 10 §2-§4, ICD §3). RECEIVE-ONLY on purpose: the controller never encodes,
// because there is no "off"/"blank" message to send (doc 10 §1) -- OFF is the
// absence of a fresh valid SHOW, enforced by the dead-man's update() in main.cpp.
//
// Platform-free: no Arduino/ESP-IDF includes, so the core is testable anywhere.
// The HMAC primitive is injected (if4_hmac_sha256) -- main.cpp binds it to mbedtls.
#pragma once
#include <stdint.h>
#include <stddef.h>
#include <stdbool.h>

#define IF4_VERSION 1
#define IF4_MSG_SHOW 1
#define IF4_HEADER_LEN 21   // ver(1) type(1) msg_id(1) seq(4) nonce(4) cfg_ver(4) ts_ms(6)
#define IF4_TAG_LEN 8       // truncated HMAC-SHA256 (airtime vs ADR-0012 trade)
#define IF4_FRAME_LEN (IF4_HEADER_LEN + IF4_TAG_LEN)   // = 29 bytes on the wire

// Verify outcomes; the reject names match esw/if4.py's reject reasons exactly,
// so bench logs and sim logs read the same.
typedef enum {
    IF4_OK = 0,
    IF4_REJ_LEN,        // "len"    -- wrong frame length
    IF4_REJ_PROTO,      // "proto"  -- wrong version or msg type
    IF4_REJ_AUTH,       // "auth"   -- HMAC tag mismatch (forgery / wrong key)
    IF4_REJ_REPLAY,     // "replay" -- seq <= session watermark (doc 10 §4 guard 1)
    IF4_REJ_STALE,      // "stale"  -- |now - ts| > replay window  (doc 10 §4 guard 2)
} if4_result_t;

typedef struct {
    if4_result_t result;
    uint8_t message_id;   // valid only when result == IF4_OK (else 0, like Python's _bad)
    uint32_t seq;         // valid only when result == IF4_OK (else 0)
} if4_verdict_t;

// HMAC-SHA256 provider, bound by the platform layer (mbedtls on the ESP32).
// out receives the full 32-byte digest; verify truncates to IF4_TAG_LEN.
void if4_hmac_sha256(const uint8_t *key, size_t key_len,
                     const uint8_t *msg, size_t msg_len, uint8_t out[32]);

// Mirror of esw/if4.py::verify(), same check order: len -> proto -> auth ->
// replay -> stale. Fail-closed: any reject is a no-op for the caller's state.
// have_last_seq=false models Python's last_seq=None (fresh session after a blank,
// so a legitimately rebooted edge with a low seq can re-assert -- SC-15).
if4_verdict_t if4_verify(const uint8_t *key, size_t key_len,
                         const uint8_t *frame, size_t frame_len,
                         bool have_last_seq, uint32_t last_seq,
                         int64_t now_ms, int64_t replay_window_ms);

// Reject-reason string for logs/counters ("ok","len","proto","auth","replay","stale").
const char *if4_reason(if4_result_t r);
