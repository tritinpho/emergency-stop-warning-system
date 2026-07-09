// Sign-controller build configuration.
//
// The two timing constants are BOUNDED SAFETY CONSTANTS from doc 02 §7a
// (software/esw/params.py): set at provisioning/boot, never runtime-tunable.
// T_signhold's hard ceiling is 3.0 s -- and the LoRa airtime budget (doc 10 §6)
// makes it an ADR-grade number, not a firmware knob. Do not raise it here.
#pragma once

#ifndef ESW_T_SIGNHOLD_MS
#define ESW_T_SIGNHOLD_MS 2000        // §7a default 2.0 s, clamp hi 3.0 s
#endif

// Anti-replay freshness window (doc 10 §4 guard 2). Defaults to T_signhold --
// a frame older than the hold window is useless and suspicious -- but it is a
// DISTINCT knob (replay exposure vs blank latency), mirroring harness/sign.py.
#ifndef ESW_REPLAY_WINDOW_MS
#define ESW_REPLAY_WINDOW_MS ESW_T_SIGNHOLD_MS
#endif

// The sign drive output: HIGH = SHOW asserted, LOW = blank. Board-specific --
// set per env in platformio.ini (YoloUno bench: 48, the onboard D13 LED; real
// rig: a Grove pin driving the LED-panel relay or the panel controller's enable
// line; IF-3 read-back is a separate input, TBD with the panel hardware -- C8).
#ifndef ESW_SIGN_GPIO
#define ESW_SIGN_GPIO 2
#endif

// Onboard status pixel (YoloUno: WS2812 on GPIO45; generic S3 devkits: 48).
// Uses the arduino-esp32 built-in neopixelWrite() -- no library dependency.
// Override per env in platformio.ini; define ESW_NO_NEOPIXEL to disable.
#ifndef ESW_NEOPIXEL_PIN
#define ESW_NEOPIXEL_PIN 48
#endif

#define ESW_STAT_EVERY_MS 1000        // 1 Hz STAT line (observability, not safety)
#define ESW_BAUD 115200
