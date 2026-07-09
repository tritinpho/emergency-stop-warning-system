// ESW IF-4 sign controller -- doc 10 firmware scaffold (RQ-H2).
//
// THE ONE RULE (doc 10 §1): the sign displays SHOW only while a fresh, valid,
// AUTHENTICATED assertion arrived within T_signhold; otherwise it blanks. There
// is no "off" message and this firmware must never grow one -- a dead edge box,
// a crashed state machine, or a cut/jammed link all blank the sign by
// construction, because what they have in common is that nothing arrives.
//
// This scaffold runs the REAL verify (if4_verify.cpp, the C mirror of
// esw/if4.py) over a BENCH transport: hex-encoded frames, one per line, on the
// USB serial port. The LoRa bearer (SX1276, ADR-0014 -- still an open bench
// decision) is a drop-in: replace bench_poll_line() with radio receive; the
// verify + dead-man's logic must not change.
//
// Bench line protocol (115200 8N1; every line \n-terminated):
//   <hex>          a frame, hex-encoded (29 bytes = 58 hex chars; other lengths
//                  are passed to verify so the rej-len path is wire-testable)
//   T<ms>          edge clock sync: ms since the agreed epoch (doc 10 "Time" --
//                  the edge-synced-clock option; GNSS/PPS replaces this later)
//   K<64hex>       provision a 32-byte link key into NVS (bench provisioning;
//                  the real mechanism is the doc 10 §8.3 open handoff)
//   KDEV           clear NVS key, revert to the built-in dev key
//   V              re-run the boot self-test vectors
//   S              print an immediate STAT line
// Output lines: BOOT/KEY/VECTORS/CLOCK/ACC?/REJ/SIGN/STAT (bench_send.py parses
// STAT and SIGN; everything else is for humans).

#include <Arduino.h>
#include <Preferences.h>
#include "mbedtls/md.h"

#include "config.h"
#include "if4_verify.h"
#include "dev_key.h"
#include "test_vectors.h"

// ---- HMAC provider: bind the platform-free verify core to mbedtls ------------------
void if4_hmac_sha256(const uint8_t *key, size_t key_len,
                     const uint8_t *msg, size_t msg_len, uint8_t out[32]) {
    const mbedtls_md_info_t *info = mbedtls_md_info_from_type(MBEDTLS_MD_SHA256);
    mbedtls_md_hmac(info, key, key_len, msg, msg_len, out);
}

// ---- controller state (mirror of harness/sign.py) ----------------------------------
static uint8_t link_key[32];
static bool key_is_dev = true;

static int64_t last_show_local_ms = -1;   // when the last VALID SHOW arrived (local clock)
static bool have_last_seq = false;        // false == Python's last_seq = None
static uint32_t last_seq = 0;
static uint8_t message_id = 0;
static bool sign_on = false;

static uint32_t n_accepted = 0;
static uint32_t n_rejects = 0;            // total, mirrors sign.py's `rejects`
static uint32_t rej_by[6] = {0, 0, 0, 0, 0, 0};   // indexed by if4_result_t

// Edge-clock sync (freshness runs on the EDGE epoch; the hold timer runs on the
// LOCAL monotonic clock -- staleness-of-arrival must not depend on sync messages).
static int64_t edge_clock_offset_ms = 0;
static bool clock_synced = false;

static Preferences prefs;

static int64_t now_local_ms() {
    return (int64_t)(esp_timer_get_time() / 1000);   // 64-bit, no millis() wrap
}

static int64_t now_edge_ms() {
    return now_local_ms() + edge_clock_offset_ms;
}

// ---- sign drive ---------------------------------------------------------------------
static void drive_sign(bool on) {
    digitalWrite(ESW_SIGN_GPIO, on ? HIGH : LOW);
#ifndef ESW_NO_NEOPIXEL
    if (on) {
        neopixelWrite(ESW_NEOPIXEL_PIN, 64, 0, 0);   // red = SHOW asserted
    } else {
        neopixelWrite(ESW_NEOPIXEL_PIN, 0, 0, 0);    // dark = blank (fail-safe state)
    }
#endif
}

// ---- self-test: the Python-generated conformance vectors ---------------------------
static bool run_vectors() {
    unsigned pass = 0;
    for (unsigned i = 0; i < IF4_N_VECTORS; i++) {
        const if4_vector_t *t = &IF4_VECTORS[i];
        if4_verdict_t v = if4_verify(ESW_DEV_KEY, sizeof(ESW_DEV_KEY),
                                     t->frame, t->frame_len,
                                     t->have_last != 0, t->last_seq,
                                     t->now_ms, t->window_ms);
        if (v.result == t->expect && v.message_id == t->exp_message_id &&
            v.seq == t->exp_seq) {
            pass++;
        } else {
            Serial.printf("VECFAIL %s got=%s mid=%u seq=%lu\n", t->name,
                          if4_reason(v.result), v.message_id, (unsigned long)v.seq);
        }
    }
    Serial.printf("VECTORS %s %u/%u\n",
                  pass == IF4_N_VECTORS ? "PASS" : "FAIL", pass, (unsigned)IF4_N_VECTORS);
    return pass == IF4_N_VECTORS;
}

// ---- key handling -------------------------------------------------------------------
static void load_key() {
    prefs.begin("esw", false);
    size_t n = prefs.getBytesLength("if4key");
    if (n == sizeof(link_key)) {
        prefs.getBytes("if4key", link_key, sizeof(link_key));
        key_is_dev = false;
        Serial.println("KEY nvs (provisioned)");
    } else {
        memcpy(link_key, ESW_DEV_KEY, sizeof(link_key));
        key_is_dev = true;
        Serial.println("KEY dev -- BENCH ONLY, provision with K<64hex> "
                       "(real provisioning: doc 10 s8.3 open handoff)");
    }
}

// ---- bench line protocol ------------------------------------------------------------
static char line_buf[192];
static size_t line_len = 0;

static int hex_nibble(char c) {
    if (c >= '0' && c <= '9') return c - '0';
    if (c >= 'a' && c <= 'f') return c - 'a' + 10;
    if (c >= 'A' && c <= 'F') return c - 'A' + 10;
    return -1;
}

// Decode an all-hex line into buf; returns byte count or -1 if not hex / too long.
static int parse_hex(const char *s, size_t len, uint8_t *buf, size_t buf_max) {
    if (len == 0 || (len % 2) != 0 || len / 2 > buf_max) {
        return -1;
    }
    for (size_t i = 0; i < len; i += 2) {
        int hi = hex_nibble(s[i]);
        int lo = hex_nibble(s[i + 1]);
        if (hi < 0 || lo < 0) {
            return -1;
        }
        buf[i / 2] = (uint8_t)((hi << 4) | lo);
    }
    return (int)(len / 2);
}

static void print_stat() {
    Serial.printf("STAT on=%d msg=%u seq=%lu acc=%lu rej=%lu auth=%lu replay=%lu "
                  "stale=%lu len=%lu proto=%lu sync=%d dev=%d\n",
                  sign_on ? 1 : 0, message_id, (unsigned long)(have_last_seq ? last_seq : 0),
                  (unsigned long)n_accepted, (unsigned long)n_rejects,
                  (unsigned long)rej_by[IF4_REJ_AUTH], (unsigned long)rej_by[IF4_REJ_REPLAY],
                  (unsigned long)rej_by[IF4_REJ_STALE], (unsigned long)rej_by[IF4_REJ_LEN],
                  (unsigned long)rej_by[IF4_REJ_PROTO],
                  clock_synced ? 1 : 0, key_is_dev ? 1 : 0);
}

// One received frame -> the doc 10 §3 receive() half. Rejects are counted and
// logged but change NOTHING (fail-closed).
static void receive_frame(const uint8_t *frame, size_t n) {
    if4_verdict_t v = if4_verify(link_key, sizeof(link_key), frame, n,
                                 have_last_seq, last_seq,
                                 now_edge_ms(), ESW_REPLAY_WINDOW_MS);
    if (v.result == IF4_OK) {
        last_show_local_ms = now_local_ms();
        have_last_seq = true;
        last_seq = v.seq;
        message_id = v.message_id;
        n_accepted++;
    } else {
        n_rejects++;
        rej_by[v.result]++;
        Serial.printf("REJ %s\n", if4_reason(v.result));
    }
}

static void handle_line(const char *s, size_t len) {
    if (len == 0) {
        return;
    }
    if (s[0] == 'T' && len > 1) {                      // edge clock sync
        int64_t edge_ms = 0;
        bool ok = true;
        for (size_t i = 1; i < len; i++) {
            if (s[i] < '0' || s[i] > '9') { ok = false; break; }
            edge_ms = edge_ms * 10 + (s[i] - '0');
        }
        if (ok) {
            edge_clock_offset_ms = edge_ms - now_local_ms();
            if (!clock_synced) {
                Serial.println("CLOCK synced (edge-synced mode, doc 10 \"Time\")");
            }
            clock_synced = true;
        }
        return;
    }
    if (len == 4 && strncmp(s, "KDEV", 4) == 0) {      // revert to dev key
        prefs.remove("if4key");
        load_key();
        return;
    }
    if (s[0] == 'K' && len == 65) {                    // provision key (bench)
        uint8_t k[32];
        if (parse_hex(s + 1, 64, k, sizeof(k)) == 32) {
            prefs.putBytes("if4key", k, sizeof(k));
            load_key();
        } else {
            Serial.println("KEY bad hex");
        }
        return;
    }
    if (len == 1 && s[0] == 'V') {
        run_vectors();
        return;
    }
    if (len == 1 && s[0] == 'S') {
        print_stat();
        return;
    }
    uint8_t frame[64];
    int n = parse_hex(s, len, frame, sizeof(frame));
    if (n >= 0) {                                      // a frame (any length: verify gates)
        receive_frame(frame, (size_t)n);
        return;
    }
    Serial.printf("# unknown line (%u chars) -- see banner for protocol\n", (unsigned)len);
}

static void poll_serial() {
    while (Serial.available() > 0) {
        char c = (char)Serial.read();
        if (c == '\n' || c == '\r') {
            if (line_len > 0) {
                line_buf[line_len] = '\0';
                handle_line(line_buf, line_len);
                line_len = 0;
            }
        } else if (line_len < sizeof(line_buf) - 1) {
            line_buf[line_len++] = c;
        } else {
            line_len = 0;                              // overlong line: drop, stay sane
            Serial.println("# line too long, dropped");
        }
    }
}

// ---- the dead-man's switch (doc 10 §3 update()) -------------------------------------
static void update_sign() {
    int64_t now = now_local_ms();
    bool fresh = (last_show_local_ms >= 0) &&
                 (now - last_show_local_ms <= ESW_T_SIGNHOLD_MS);
    bool was_on = sign_on;
    if (fresh) {
        sign_on = true;
    } else {
        sign_on = false;
        message_id = 0;
        have_last_seq = false;    // session ends -> a legit reconnect may re-assert;
                                  // an OLD replayed frame is still blocked by freshness.
    }
    if (sign_on != was_on) {
        drive_sign(sign_on);
        Serial.printf("SIGN %s\n", sign_on ? "on" : "off");
    }
}

// ---- Arduino entry points -----------------------------------------------------------
void setup() {
    pinMode(ESW_SIGN_GPIO, OUTPUT);
    drive_sign(false);                                 // boot blank: the safe state
    Serial.begin(ESW_BAUD);
    // Native-USB boards enumerate asynchronously; wait briefly, then proceed --
    // the sign logic must never depend on a host being attached.
    int64_t t0 = now_local_ms();
    while (!Serial && now_local_ms() - t0 < 2000) {
        delay(10);
    }
    Serial.println();
    Serial.printf("BOOT esw-sign-controller doc10-scaffold T_signhold=%dms window=%dms sign_gpio=%d\n",
                  (int)ESW_T_SIGNHOLD_MS, (int)ESW_REPLAY_WINDOW_MS, (int)ESW_SIGN_GPIO);
    Serial.println("# protocol: <58hex>=frame  T<ms>=clock  K<64hex>=key  KDEV  V=vectors  S=stat");
    load_key();
    run_vectors();                                     // cross-language conformance, every boot
    print_stat();
}

void loop() {
    static int64_t last_stat = 0;
    poll_serial();
    update_sign();                                     // runs continuously -- THE rule
    int64_t now = now_local_ms();
    if (now - last_stat >= ESW_STAT_EVERY_MS) {
        last_stat = now;
        print_stat();
    }
    delay(2);                                          // ~500 Hz loop; hold check granularity ≪ T_signhold
}
