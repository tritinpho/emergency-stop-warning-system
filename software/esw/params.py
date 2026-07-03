# Safety-parameter surface + FR-20 clamps.
#
# Authoritative source: doc 02 §7a (the "Configuration & safety-parameter surface").
# Every safety-relevant parameter -- runtime-config OR bounded-constant -- has a
# default and a hard [lo, hi] the unit clamps/rejects to (FR-20). Nothing
# safety-relevant is tunable outside this table.
#
# Times are seconds; speeds km/h; overlap a 0..1 fraction.

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
}


def default_config():
    cfg = {}
    for name in DEFAULTS:
        cfg[name] = DEFAULTS[name]["default"]
    return cfg


def clamp(name, value):
    """Return (clamped_value, was_clamped). Unknown names pass through untouched."""
    spec = DEFAULTS.get(name)
    if spec is None:
        return value, False
    if value < spec["lo"]:
        return spec["lo"], True
    if value > spec["hi"]:
        return spec["hi"], True
    return value, False


def clamp_config(cfg):
    """Apply FR-20 bounds to a whole config dict; return (clean_cfg, rejected_names)."""
    clean = default_config()
    rejected = []
    for name in cfg:
        value, was = clamp(name, cfg[name])
        clean[name] = value
        if was:
            rejected.append(name)
    return clean, rejected
