# Synthetic sensor model (doc 07 §3): turn a scenario script into IF-2 track
# events, one snapshot per tick. Level A injects events directly at the
# Perception->SM boundary (IF-2); it does NOT render frames.
#
# A scenario track:
#   {"id","enter","leave","speed"(kph),"in_roi"(0..1),
#    "leave_speed"(kph or None -> a confirmed exit vs a silent vanish),
#    "exit_window"(s, how long it is seen moving before `leave`),
#    "speed_windows"[[t0,t1,kph],...] mid-life speed overrides (a transient blip),
#    "gaps"[[t0,t1],...] intervals it is occluded (present but unseen),
#    "cls"}
#
# Nuisance injection (dropout rate, false detections, footprint noise, class
# confusion, lane-attribution error) hangs off this same function -- TODO for the
# scenarios that need it (SC-06..09, SC-11..13). Kept deterministic for now.


def observations_at(scenario, t):
    """IF-2 track events for tick t, tagged by sensor_source (camera / radar / fused).

    The camera reports a present track unless it is in a scripted occlusion `gap` or
    the camera is unhealthy. Radar corroborates a present track when it has an RCS
    (`radar_visible`, default True) and radar is healthy -- radar is NOT blocked by a
    camera occlusion, which is exactly what makes the occlusion hold possible. A
    `radar_ghosts` entry adds a mis-attributed radar-only corroboration for a track_id
    (weak criterion (b), SC-09) even after the real object has departed.
    """
    health = health_at(scenario, t)
    cam_ok = health.get("camera", True)
    rad_ok = health.get("radar", True)
    obs = []
    for trk in scenario.get("tracks", []):
        if not (trk["enter"] <= t < trk["leave"]):
            continue
        occluded = False
        for g in trk.get("gaps", []):
            if g[0] <= t < g[1]:
                occluded = True
                break
        camera_sees = cam_ok and not occluded
        radar_sees = rad_ok and trk.get("radar_visible", True)
        if not (camera_sees or radar_sees):
            continue  # present in the world, but neither channel can report it now
        speed = trk.get("speed", 0.0)
        for sw in trk.get("speed_windows", []):
            if sw[0] <= t < sw[1]:
                speed = sw[2]    # scripted mid-life speed blip (centroid jump / door-open)
                break
        leave_speed = trk.get("leave_speed", None)
        if leave_speed is not None and t >= trk["leave"] - trk.get("exit_window", 1.5):
            speed = leave_speed  # seen accelerating away -> a confirmed exit
        if camera_sees and radar_sees:
            source = "fused"
        elif camera_sees:
            source = "camera"        # radar dead: camera-only (CAMERA-ONLY)
        else:
            source = "radar"         # camera occluded / dead: radar corroboration only
        stale = False
        if camera_sees:
            for w in trk.get("stale", []):
                if w[0] <= t < w[1]:
                    stale = True     # frozen/wedged camera: a repeated frame, not fresh (SC-28)
                    break
        obs.append({
            "track_id": trk["id"],
            "cls": trk.get("cls", "car"),
            "in_roi": trk.get("in_roi", 1.0),
            "speed_kph": speed,
            "sensor_source": source,
            "stale": stale,
            "ts": t,
        })
    # Weak-(b) mis-attributed radar corroboration: a through-lane return pinned to a
    # departed shoulder track_id -- radar-only, in-ROI, no camera (drives SC-09).
    if rad_ok:
        for gh in scenario.get("radar_ghosts", []):
            if gh["from"] <= t < gh["to"]:
                obs.append({
                    "track_id": gh["track_id"],
                    "cls": "unknown",
                    "in_roi": gh.get("in_roi", 1.0),
                    "speed_kph": gh.get("speed_kph", 0.0),
                    "sensor_source": "radar",
                    "ts": t,
                })
    return obs


def health_at(scenario, t):
    # Static FULL health unless a scenario scripts sensor loss (SC-25/26/27).
    base = scenario.get("health", {"camera": True, "radar": True})
    for ev in scenario.get("health_events", []):
        if t >= ev["t"]:
            base = ev["health"]
    return base


def override_at(scenario, t):
    """The operative IF-10 override as of tick t: the most-recently-issued command whose
    `issued` time has arrived (None if none). The SUT enforces its own bounds/auto-expiry
    (ADR-0010) -- the harness only delivers the command the TMC is currently asserting."""
    cur = None
    for ov in scenario.get("overrides", []):
        if ov.get("issued", 0.0) <= t:
            cur = ov
    return cur


def ota_at(scenario, t):
    """True once a signed OTA / restart has been requested (latched) -- IF-9, FR-21."""
    for req in scenario.get("ota_requests", []):
        if t >= req:
            return True
    return False


def drift_at(scenario, t):
    """True while an injected calibration-drift residual exceeds tolerance (FR-10, R15) -- a
    bench-injectable synthetic homography shift; real drift is field-deferred."""
    for w in scenario.get("drift", []):
        if w[0] <= t < w[1]:
            return True
    return False


def gnss_at(scenario, t):
    """GNSS/PPS lock state at tick t for the health monitor (NFR-16): False while a
    `gnss_loss` window is scripted, True (locked) otherwise."""
    for w in scenario.get("gnss_loss", []):
        if w[0] <= t < w[1]:
            return False
    return True


def selftest_at(scenario, t):
    """Critical health self-test result at tick t (FR-10): False while an `hm_fault` window
    is scripted (a compute/memory/link/sign self-check failure), which trips the health
    monitor's independent force-safe (IF-5). True (passing) otherwise."""
    for w in scenario.get("hm_fault", []):
        if w[0] <= t < w[1]:
            return False
    return True


def ack_at(scenario, t):
    """The operator's most-recent acknowledgement as of tick t: the alarm_count value the
    operator has acked (None if none) -- IF-10, ADR-0011 §2. The SUT scopes it to the epoch
    (acking N does not ack N+1), so the harness only latches the last count the operator sent.

    A scenario ack: {"t": seconds, "count": alarm_count-being-acked}."""
    cur = None
    for a in scenario.get("acks", []):
        if a.get("t", 0.0) <= t:
            cur = a.get("count")
    return cur
