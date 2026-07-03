# Synthetic sensor model (doc 07 §3): turn a scenario script into IF-2 track
# events, one snapshot per tick. Level A injects events directly at the
# Perception->SM boundary (IF-2); it does NOT render frames.
#
# A scenario track:
#   {"id","enter","leave","speed"(kph),"in_roi"(0..1),
#    "leave_speed"(kph or None -> a confirmed exit vs a silent vanish),
#    "exit_window"(s, how long it is seen moving before `leave`),
#    "gaps"[[t0,t1],...] intervals it is occluded (present but unseen),
#    "cls"}
#
# Nuisance injection (dropout rate, false detections, footprint noise, class
# confusion, lane-attribution error) hangs off this same function -- TODO for the
# scenarios that need it (SC-06..09, SC-11..13). Kept deterministic for now.


def observations_at(scenario, t):
    obs = []
    for trk in scenario.get("tracks", []):
        if not (trk["enter"] <= t < trk["leave"]):
            continue
        occluded = False
        for g in trk.get("gaps", []):
            if g[0] <= t < g[1]:
                occluded = True
                break
        if occluded:
            continue  # present in the world, but the camera cannot see it now
        speed = trk.get("speed", 0.0)
        leave_speed = trk.get("leave_speed", None)
        if leave_speed is not None and t >= trk["leave"] - trk.get("exit_window", 1.5):
            speed = leave_speed  # seen accelerating away -> a confirmed exit
        obs.append({
            "track_id": trk["id"],
            "cls": trk.get("cls", "car"),
            "in_roi": trk.get("in_roi", 1.0),
            "speed_kph": speed,
            "sensor_source": "fused",
            "ts": t,
        })
    return obs


def health_at(scenario, t):
    # Static FULL health unless a scenario scripts sensor loss (SC-25/26/27, TODO).
    base = scenario.get("health", {"camera": True, "radar": True})
    for ev in scenario.get("health_events", []):
        if t >= ev["t"]:
            base = ev["health"]
    return base
