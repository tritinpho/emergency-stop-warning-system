# HM-01.. -- health-monitor unit cases (Level C). These pin esw/health.py in ISOLATION:
# given raw per-tick liveness / GNSS-lock / self-test inputs, assert the derived
# {camera, radar, time_valid, force_safe, status}. The Level-A closed-loop side
# (SC-35/36/37) proves the monitor drives the state machine + sign correctly; these
# pin the derivation logic itself.
#
# A case: windows say when each input is "good".
#   "live": {sensor: [[t0,t1],...]}   ticks the sensor delivers fresh data (absent key = always live)
#   "gnss_loss": [[t0,t1],...]         windows GNSS/PPS is unlocked (absent = always locked)
#   "hm_fault":  [[t0,t1],...]         windows the critical self-test fails (absent = always OK)
# "checks" assert any of camera/radar/time_valid/force_safe/status at a time.

CASES = [
    {
        "id": "HM-01", "status": "impl",
        "title": "Both sensors live, GNSS locked, self-test OK -> healthy / OK",
        "duration": 3.0,
        "checks": [{"t": 1.0, "camera": True, "radar": True, "time_valid": True,
                    "force_safe": False, "status": "OK"},
                   {"t": 2.5, "camera": True, "radar": True, "status": "OK"}],
    },
    {
        "id": "HM-02", "status": "impl",
        "title": "Sustained camera loss -> camera DOWN after T_sensor_timeout -> DEGRADED",
        "duration": 4.0,
        "config_push": {"T_sensor_timeout": 0.5},
        "live": {"camera": [[0.0, 2.0]]},          # camera silent from t=2; radar always live
        "checks": [{"t": 1.5, "camera": True, "status": "OK"},
                   {"t": 2.3, "camera": True},                        # 2.3-1.9=0.4 <= 0.5 -> still healthy
                   {"t": 3.0, "camera": False, "radar": True, "status": "DEGRADED"}],  # 1.1 > 0.5 -> DOWN
    },
    {
        "id": "HM-03", "status": "impl",
        "title": "Brief camera blink (< T_sensor_timeout) -> debounced, stays healthy",
        "duration": 4.0,
        "config_push": {"T_sensor_timeout": 0.5},
        "live": {"camera": [[0.0, 2.0], [2.3, 4.1]]},   # 0.3 s blink at 2.0-2.3
        "checks": [{"t": 2.2, "camera": True, "status": "OK"}],   # 2.2-1.9=0.3 <= 0.5 -> no flap
    },
    {
        "id": "HM-04", "status": "impl",
        "title": "Radar dead from boot -> radar DOWN immediately (camera-only) -> DEGRADED",
        "duration": 3.0,
        "live": {"radar": []},                     # radar never live; camera always live (default timeout 0)
        "checks": [{"t": 1.0, "camera": True, "radar": False, "status": "DEGRADED"}],
    },
    {
        "id": "HM-05", "status": "impl",
        "title": "GNSS/PPS loss -> time_valid False past holdover; re-lock -> valid (NFR-16)",
        "duration": 6.0,
        "config_push": {"T_time_holdover": 0.5},
        "gnss_loss": [[2.0, 4.0]],
        "checks": [{"t": 1.0, "time_valid": True, "status": "OK"},
                   {"t": 3.0, "time_valid": False, "status": "DEGRADED"},   # 3.0-1.9=1.1 > 0.5 holdover
                   {"t": 5.0, "time_valid": True, "status": "OK"}],         # re-locked at 4.0
    },
    {
        "id": "HM-06", "status": "impl",
        "title": "Critical self-test fault -> force_safe (IF-5); clears when it passes",
        "duration": 6.0,
        "hm_fault": [[2.0, 4.0]],
        "checks": [{"t": 1.0, "force_safe": False, "status": "OK"},
                   {"t": 3.0, "force_safe": True, "status": "FORCE_SAFE"},
                   {"t": 5.0, "force_safe": False, "status": "OK"}],
    },
]
