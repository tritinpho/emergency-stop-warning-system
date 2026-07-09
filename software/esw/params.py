# Safety-parameter surface + FR-20 clamps.
#
# Authoritative source: doc 02 §7a (the "Configuration & safety-parameter surface").
# Every safety-relevant parameter -- runtime-config OR bounded-constant -- has a
# default and a hard [lo, hi] the unit clamps/rejects to (FR-20). Nothing
# safety-relevant is tunable outside this table.
#
# Times are seconds; speeds km/h; overlap a 0..1 fraction; counts are integers.

try:
    import hashlib
except ImportError:                 # MicroPython ports that only expose uhashlib
    import uhashlib as hashlib

DEFAULTS = {
    #  name                default   lo        hi        scope
    "T_dwell":          {"default": 5.0,    "lo": 3.0,  "hi": 10.0},     # runtime-config
    "T_hold":           {"default": 10.0,   "lo": 5.0,  "hi": 15.0},     # runtime-config
    "T_occlusion":      {"default": 60.0,   "lo": 0.0,  "hi": 120.0},    # runtime-config (renewable)
    "T_person_debounce":{"default": 1.5,    "lo": 0.5,  "hi": 3.0},      # runtime-config
    "speed_gate_kph":   {"default": 3.0,    "lo": 1.0,  "hi": 5.0},      # runtime-config
    "T_override_max":   {"default": 1800.0, "lo": 0.0,  "hi": 28800.0},  # runtime-config, <= 8 h
    "roi_overlap_gate": {"default": 0.5,    "lo": 0.0,  "hi": 1.0},      # runtime-config (>=50%)
    # --- bounded constants: tightly clamped so no pushed value can disable the invariant ---
    "T_degraded_max":   {"default": 300.0,  "lo": 0.0,  "hi": 600.0},    # <= 10 min (never "never")
    "T_watchdog":       {"default": 30.0,   "lo": 0.0,  "hi": 30.0},     # hard <= 30 s (NFR-04)
    "T_signhold":       {"default": 2.0,    "lo": 0.0,  "hi": 3.0},      # <= 3 s dead-man's window
    "T_assert_refresh": {"default": 0.5,    "lo": 0.0,  "hi": 0.75},     # <= 1/4 * T_signhold
    "T_activate":       {"default": 2.0,    "lo": 0.0,  "hi": 2.0},      # <= 2 s (NFR-01, LED)
    "T_sensor_timeout": {"default": 0.0,    "lo": 0.0,  "hi": 2.0},      # health monitor: sensor DOWN after
    #                                                                      this long with no fresh data (FR-10).
    #                                                                      Default 0 = react immediately (safe,
    #                                                                      conservative); tune up for anti-flap.
    "T_time_holdover":  {"default": 0.5,    "lo": 0.0,  "hi": 5.0},      # NFR-16: absolute time stays valid
    #                                                                      this long after GNSS/PPS loss (bench;
    #                                                                      real multi-hour hold-over field-deferred)
    "T_corr_tolerance": {"default": 0.5,    "lo": 0.0,  "hi": 2.0},      # radar corroboration stays LIVE this
    #                                                                      long after its last return, so one
    #                                                                      missed radar scan cannot drop an
    #                                                                      occlusion hold (ADR-0009 sC). Small
    #                                                                      vs T_hold/T_occlusion by bound.
    "T_reescalate":     {"default": 10.0,   "lo": 5.0,  "hi": 60.0},     # NFR-15/ADR-0011: an unacked CRITICAL
    #                                                                      re-escalates once per this window
    "T_drift_debounce": {"default": 2.0,    "lo": 0.0,  "hi": 10.0},     # FR-10/R15: drift residual must exceed
    #                                                                      tolerance this long before DEGRADED
    "T_sign_stuck_grace": {"default": 0.5,  "lo": 0.0,  "hi": 2.0},      # ADR-0013 sC.3: read-back may lag the
    #                                                                      commanded OFF this far past T_signhold
    "congestion_min_tracks": {"default": 4, "lo": 3,    "hi": 10},       # R14: a jam is >= this many stationary
    #                                                                      tracks scene-wide (count, not seconds).
    #                                                                      lo>=3: a lower value would suppress
    #                                                                      genuine 1-2 car shoulder warnings.
}


# The site-tunable subset (ICD IF-8): ONLY these may change on a RUNNING unit via a config push.
# Everything else in DEFAULTS is a bounded SAFETY BACKSTOP -- set at provisioning/boot and never
# retunable at runtime, so no live reconfiguration (or a compromised uplink) can move the
# dead-man's-switch window, the watchdog, the degraded-hold ceiling, the refresh cadence, or the
# activation bound (ADR-0012 R16 unsafe-config; FR-20). Boot config (clamp_config) still clamps
# these to §7a; runtime config (clamp_update) refuses them outright.
RUNTIME_TUNABLE = ("T_dwell", "T_hold", "T_occlusion", "T_person_debounce",
                   "speed_gate_kph", "T_override_max", "roi_overlap_gate")


def default_config():
    cfg = {}
    for name in DEFAULTS:
        cfg[name] = DEFAULTS[name]["default"]
    return cfg


def clamp(name, value):
    """Return (clamped_value, was_clamped). Unknown names pass through untouched.
    A non-numeric value for a known name is out-of-bounds by definition: restore the
    vetted default and report it clamped, rather than crash the config ingest (FR-20).
    NaN is unclampable (every comparison against the bounds is False, so it would sail
    through and silently disable any timer it reaches) -> vetted default, flagged."""
    spec = DEFAULTS.get(name)
    if spec is None:
        return value, False
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return spec["default"], True   # wrong type (incl. bool) -> default, flagged
    if value != value:
        return spec["default"], True   # NaN -> default, flagged (never passes a bound check)
    if value < spec["lo"]:
        return spec["lo"], True
    if value > spec["hi"]:
        return spec["hi"], True
    return value, False


def clamp_config(cfg):
    """Apply FR-20 bounds to a whole config dict; return (clean_cfg, rejected_names).

    An unknown/misspelled name is REJECTED (reported, default retained), never silently
    kept as a dead key -- a typo'd safety parameter must not pass unnoticed with no
    effect (fail-loud, FR-21). Known names are clamped to their [lo, hi]."""
    clean = default_config()
    rejected = []
    for name in cfg:
        if name not in DEFAULTS:
            rejected.append(name)          # unknown/misspelled -> fail loud, keep the default
            continue
        value, was = clamp(name, cfg[name])
        clean[name] = value
        if was:
            rejected.append(name)
    return clean, rejected


def clamp_update(partial):
    """Apply a runtime IF-8 config push to a RUNNING unit. Returns (accepted, rejected):
    `accepted` = {name: clamped_value} to merge into the live config; `rejected` = names refused
    or adjusted (fail-loud, FR-21). REFUSED and kept last-good: an unknown/misspelled name, a
    wrong-type value, and -- the runtime safety stance -- any bounded-constant backstop (boot-only,
    not in RUNTIME_TUNABLE). A runtime-tunable name is clamped into its §7a [lo, hi] and applied
    (a clamp is still reported). Unlike clamp_config (boot), an untouched field is never reset to
    its default -- a partial push changes only what it names."""
    accepted = {}
    rejected = []
    for name in partial:
        if name not in DEFAULTS:
            rejected.append(name)              # unknown/misspelled -> refuse, keep last-good
            continue
        if name not in RUNTIME_TUNABLE:
            rejected.append(name)              # bounded backstop -> boot-only, refuse at runtime
            continue
        value = partial[name]
        if (isinstance(value, bool) or not isinstance(value, (int, float))
                or value != value):
            rejected.append(name)              # wrong type / NaN -> refuse, keep last-good
            continue
        clamped, was = clamp(name, value)
        accepted[name] = clamped
        if was:
            rejected.append(name)              # out of §7a bounds -> clamp + apply + flag
    return accepted, rejected


def cfg_fingerprint(cfg):
    """4-byte fingerprint of the active safety config (R10 audit / cfg_ver). Canonical
    "name=value;" over sorted keys so the hash is stable regardless of dict order. It is
    authenticated but OPAQUE on the wire (echoed for audit, not interpreted), so float-repr
    differences across runtimes cannot change a safety decision. Recomputed whenever the
    LIVE config changes (boot clamp AND every runtime IF-8 push), so audit records always
    bind to the config actually in force."""
    names = sorted(cfg.keys())
    s = ""
    i = 0
    while i < len(names):
        n = names[i]
        s = s + n + "=" + str(cfg[n]) + ";"
        i += 1
    return hashlib.sha256(s.encode("utf-8")).digest()[:4]
