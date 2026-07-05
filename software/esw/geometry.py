# Ground-plane geometry for ROI gating (doc 02 §4 "calibration is load-bearing").
#
# A detection is an image bounding box; the ROI is a polygon on the GROUND. To gate
# a detection we map its ground contact point through the per-site ground-plane
# homography, build a class-sized ground footprint, and measure how much of that
# footprint falls inside the ROI polygon (the IF-2 `in_roi` fraction, doc 08 §2).
#
# Ships to the K230: MicroPython-safe subset (pure float/list math, no numpy).


def apply_homography(h, x, y):
    """Map an image point (x, y) to ground coords through a 3x3 homography `h`."""
    a, b, c = h[0]
    d, e, f = h[1]
    g, i, j = h[2]
    w = g * x + i * y + j
    if w == 0.0:
        w = 1e-9
    return (a * x + b * y + c) / w, (d * x + e * y + f) / w


def bbox_ground_point(h, bbox):
    """Ground (x, y) of a detection = its image bbox bottom-centre (the ground
    contact line) through the homography. bbox = [x1, y1, x2, y2] in image pixels."""
    x1, y1, x2, y2 = bbox
    return apply_homography(h, 0.5 * (x1 + x2), y2)


def footprint_box(cx, cy, w, length):
    """A first-order ground footprint: a class-sized axis-aligned box (width w, length
    `length`, metres) centred on the contact point. A camera-height/depth model is a
    later refinement; this is enough to gate ROI overlap. Wound CCW (for the clipper)."""
    hw = 0.5 * w
    hl = 0.5 * length
    return [(cx - hw, cy - hl), (cx + hw, cy - hl),
            (cx + hw, cy + hl), (cx - hw, cy + hl)]


def polygon_area(poly):
    """Absolute area of a polygon via the shoelace formula."""
    n = len(poly)
    if n < 3:
        return 0.0
    s = 0.0
    k = n - 1
    for m in range(n):
        xk, yk = poly[k]
        xm, ym = poly[m]
        s += (xk + xm) * (yk - ym)
        k = m
    return abs(s) * 0.5


def _inside(p, a, b):
    """True if p is on the interior (left) side of the directed edge a->b (CCW clip)."""
    return (b[0] - a[0]) * (p[1] - a[1]) - (b[1] - a[1]) * (p[0] - a[0]) >= 0.0


def _edge_intersect(s, e, a, b):
    """Intersection of segment s-e with the (infinite) line through a-b."""
    x1, y1 = s
    x2, y2 = e
    x3, y3 = a
    x4, y4 = b
    den = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4)
    if den == 0.0:
        return e
    t = ((x1 - x3) * (y3 - y4) - (y1 - y3) * (x3 - x4)) / den
    return (x1 + t * (x2 - x1), y1 + t * (y2 - y1))


def clip_polygon(subject, clip):
    """Sutherland-Hodgman: `subject` clipped by a CONVEX, CCW `clip` polygon.
    Returns the (possibly empty) intersection polygon."""
    output = list(subject)
    m = len(clip)
    for c in range(m):
        a = clip[c]
        b = clip[(c + 1) % m]
        current = output
        output = []
        k = len(current)
        if k == 0:
            break
        s = current[k - 1]
        for idx in range(k):
            pt = current[idx]
            if _inside(pt, a, b):
                if not _inside(s, a, b):
                    output.append(_edge_intersect(s, pt, a, b))
                output.append(pt)
            elif _inside(s, a, b):
                output.append(_edge_intersect(s, pt, a, b))
            s = pt
    return output


def overlap_fraction(footprint, roi):
    """Fraction (0..1) of `footprint`'s area that lies inside the convex, CCW `roi`.
    This is the IF-2 `in_roi` value the state machine gates on (roi_overlap_gate)."""
    fa = polygon_area(footprint)
    if fa <= 0.0:
        return 0.0
    inter = clip_polygon(footprint, roi)
    if len(inter) < 3:
        return 0.0
    frac = polygon_area(inter) / fa
    if frac > 1.0:
        frac = 1.0
    return frac
