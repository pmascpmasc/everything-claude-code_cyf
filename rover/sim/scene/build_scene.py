"""Author the 沙崙 obstacle course as SimReady OpenUSD.

Each obstacle type is its own SimReady prop package (validated against the
Robotics-Prop profile); course.usda composes them at their race positions and
adds the ground, physics scene, lighting and cameras for Isaac Sim.

    python build_scene.py            # writes ./out
"""
import json
import math
import os
import shutil
from datetime import date

from pxr import Gf, Sdf, Usd, UsdGeom, UsdLux, UsdPhysics, UsdSemantics, UsdShade, Vt

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out")
SPEC = json.load(open(os.path.join(HERE, "course_spec.json"), encoding="utf-8"))
TODAY = date.today().isoformat()

# ---------------------------------------------------------------- materials
# Visual (UsdPreviewSurface) and physical (UsdPhysics.MaterialAPI) values per class.
# Friction values match the browser simulator so both tools agree.
MATERIALS = {
    "asphalt":  dict(color=(0.32, 0.33, 0.34), rough=0.9, metal=0.0, sf=0.9, df=0.8, rest=0.05, density=2300, cls="asphalt", finish="rough"),
    "concrete": dict(color=(0.72, 0.71, 0.68), rough=0.85, metal=0.0, sf=0.9, df=0.8, rest=0.05, density=2400, cls="concrete", finish="rough"),
    "steel_grate": dict(color=(0.61, 0.64, 0.67), rough=0.5, metal=1.0, sf=0.9, df=0.8, rest=0.1, density=7850, cls="metal", finish="brushed"),
    "plywood":  dict(color=(0.79, 0.64, 0.42), rough=0.8, metal=0.0, sf=0.8, df=0.7, rest=0.1, density=600, cls="wood", finish="unfinished"),
    "mud":      dict(color=(0.37, 0.25, 0.15), rough=0.35, metal=0.0, sf=0.15, df=0.15, rest=0.0, density=1700, cls="soil", finish="wet"),
    "gravel":   dict(color=(0.55, 0.54, 0.51), rough=0.95, metal=0.0, sf=0.7, df=0.6, rest=0.05, density=1600, cls="stone", finish="loose"),
    "cone_pvc": dict(color=(0.94, 0.35, 0.10), rough=0.6, metal=0.0, sf=0.5, df=0.4, rest=0.2, density=1300, cls="plastic", finish="matte"),
    "hazard_yellow": dict(color=(0.95, 0.77, 0.0), rough=0.6, metal=0.0, sf=0.6, df=0.5, rest=0.1, density=1200, cls="plastic", finish="painted"),
}

# Semantic class labels (LabelsAPI, taxonomy "class"), chosen for a ground-robot obstacle course.
# qcode: Wikidata item; left empty where it could not be looked up (see validation report).
ASSETS_META = {}


# ---------------------------------------------------------------- geometry helpers
def _tri_normals(points, tris):
    """Per-face-vertex normals (faceVarying) for flat shading; unit length, outward with CCW winding."""
    normals = []
    for a, b, c in tris:
        pa, pb, pc = (Gf.Vec3f(*points[i]) for i in (a, b, c))
        n = Gf.Cross(pb - pa, pc - pa)
        n = n.GetNormalized() if n.GetLength() > 1e-12 else Gf.Vec3f(0, 0, 1)
        normals += [n, n, n]
    return normals


def box_tris(cx, cy, cz, sx, sy, sz):
    """Axis-aligned box as 12 CCW triangles. Returns (points, tris)."""
    x0, x1, y0, y1, z0, z1 = cx - sx / 2, cx + sx / 2, cy - sy / 2, cy + sy / 2, cz - sz / 2, cz + sz / 2
    p = [(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0), (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)]
    quads = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
    t = []
    for a, b, c, d in quads:
        t += [(a, b, c), (a, c, d)]
    return p, fix_winding(p, t)


def prism_tris(profile, y0, y1):
    """Extrude a CCW polygon in the XZ plane (list of (x, z)) along Y. Convex or simple fan-able polygons only."""
    n = len(profile)
    p = [(x, y0, z) for x, z in profile] + [(x, y1, z) for x, z in profile]
    t = []
    for i in range(1, n - 1):
        t.append((0, i, i + 1))              # y0 face, normal -Y for CCW-in-XZ profile
        t.append((n, n + i + 1, n + i))      # y1 face
    for i in range(n):
        j = (i + 1) % n
        t += [(i, j, n + j), (i, n + j, n + i)]
    return p, fix_winding(p, t)


def merge(*parts):
    pts, tris = [], []
    for p, t in parts:
        off = len(pts)
        pts += p
        tris += [(a + off, b + off, c + off) for a, b, c in t]
    return pts, tris


def heightfield_tris(length, width, nu, nv, fn, base=0.0):
    """Closed solid under a height function z = fn(u, v), u in [0, length], v in [0, width] (v measured from -width/2)."""
    du, dv = length / nu, width / nv
    top = [(i * du, -width / 2 + j * dv, fn(i * du, j * dv)) for i in range(nu + 1) for j in range(nv + 1)]
    idx = lambda i, j: i * (nv + 1) + j
    t = []
    for i in range(nu):
        for j in range(nv):
            a, b, c, d = idx(i, j), idx(i + 1, j), idx(i + 1, j + 1), idx(i, j + 1)
            t += [(a, b, c), (a, c, d)]
    # skirt down to base so the collider is a closed solid
    pts = list(top)
    ring = [idx(i, 0) for i in range(nu + 1)] + [idx(nu, j) for j in range(1, nv + 1)] + \
           [idx(i, nv) for i in range(nu - 1, -1, -1)] + [idx(0, j) for j in range(nv - 1, 0, -1)]
    base_ids = []
    for k in ring:
        x, y, _ = top[k]
        base_ids.append(len(pts))
        pts.append((x, y, base))
    m = len(ring)
    for k in range(m):
        a, b = ring[k], ring[(k + 1) % m]
        ba, bb = base_ids[k], base_ids[(k + 1) % m]
        t += [(a, ba, bb), (a, bb, b)]
    center = len(pts)
    pts.append((length / 2, 0.0, base))
    for k in range(m):
        t.append((center, base_ids[(k + 1) % m], base_ids[k]))
    return pts, t


def cone_tris(h, base, top_r=0.035, bottom_r=0.17, seg=24):
    """Traffic cone: square base plate + truncated cone."""
    plate = box_tris(0, 0, 0.015, base, base, 0.03)
    p, t = [], []
    for k in range(seg):
        a = 2 * math.pi * k / seg
        p.append((bottom_r * math.cos(a), bottom_r * math.sin(a), 0.03))
        p.append((top_r * math.cos(a), top_r * math.sin(a), h))
    for k in range(seg):
        i0, i1, j0, j1 = 2 * k, 2 * k + 1, 2 * ((k + 1) % seg), 2 * ((k + 1) % seg) + 1
        t += [(i0, j0, j1), (i0, j1, i1)]
    ct = len(p)
    p.append((0, 0, h))
    for k in range(seg):
        t.append((ct, 2 * k + 1, 2 * ((k + 1) % seg) + 1))
    return merge(plate, (p, fix_winding(p, t)))


def fix_winding(points, tris):
    """Flip triangles whose normal points toward the centroid. Only valid for a single convex part."""
    c = Gf.Vec3f(*[sum(q[i] for q in points) / len(points) for i in range(3)])
    out = []
    for a, b, cc in tris:
        pa, pb, pc = (Gf.Vec3f(*points[i]) for i in (a, b, cc))
        n = Gf.Cross(pb - pa, pc - pa)
        mid = (pa + pb + pc) / 3.0
        out.append((a, cc, b) if Gf.Dot(n, mid - c) < 0 else (a, b, cc))
    return out


# ---------------------------------------------------------------- USD authoring
def define_mesh(stage, path, points, tris):
    m = UsdGeom.Mesh.Define(stage, path)
    m.CreatePointsAttr(Vt.Vec3fArray([Gf.Vec3f(*q) for q in points]))
    m.CreateFaceVertexCountsAttr(Vt.IntArray([3] * len(tris)))
    m.CreateFaceVertexIndicesAttr(Vt.IntArray([i for tri in tris for i in tri]))
    m.CreateSubdivisionSchemeAttr(UsdGeom.Tokens.none)
    m.CreateOrientationAttr(UsdGeom.Tokens.rightHanded)
    m.CreateNormalsAttr(Vt.Vec3fArray(_tri_normals(points, tris)))
    m.SetNormalsInterpolation(UsdGeom.Tokens.faceVarying)
    m.CreateExtentAttr(UsdGeom.Boundable.ComputeExtentFromPlugins(m, Usd.TimeCode.Default()))
    return m


def define_material(stage, root, key):
    v = MATERIALS[key]
    mat = UsdShade.Material.Define(stage, f"{root}/Looks/{key}")
    sh = UsdShade.Shader.Define(stage, f"{root}/Looks/{key}/PreviewSurface")
    sh.CreateIdAttr("UsdPreviewSurface")
    sh.CreateInput("diffuseColor", Sdf.ValueTypeNames.Color3f).Set(Gf.Vec3f(*v["color"]))
    sh.CreateInput("roughness", Sdf.ValueTypeNames.Float).Set(v["rough"])
    sh.CreateInput("metallic", Sdf.ValueTypeNames.Float).Set(v["metal"])
    mat.CreateSurfaceOutput().ConnectToSource(sh.ConnectableAPI(), "surface")
    pm = UsdPhysics.MaterialAPI.Apply(mat.GetPrim())
    pm.CreateStaticFrictionAttr(v["sf"])
    pm.CreateDynamicFrictionAttr(v["df"])
    pm.CreateRestitutionAttr(v["rest"])
    pm.CreateDensityAttr(v["density"])
    UsdSemantics.LabelsAPI.Apply(mat.GetPrim(), "material").CreateLabelsAttr(Vt.TokenArray([v["cls"]]))
    return mat


def bind(prim, mat):
    api = UsdShade.MaterialBindingAPI.Apply(prim)
    api.Bind(mat)
    api.Bind(mat, materialPurpose="physics")


def label(prim, cls):
    api = UsdSemantics.LabelsAPI.Apply(prim, "class")
    api.CreateLabelsAttr(Vt.TokenArray([cls]))


def new_stage(path, root_name):
    stage = Usd.Stage.CreateNew(path)
    UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.z)
    UsdGeom.SetStageMetersPerUnit(stage, 1.0)
    UsdPhysics.SetStageKilogramsPerUnit(stage, 1.0)
    root = UsdGeom.Xform.Define(stage, f"/{root_name}")
    stage.SetDefaultPrim(root.GetPrim())
    return stage, root


def build_prop(name, category, cls, parts, mass, kinematic, qcode=""):
    """One SimReady prop package: out/assets/<name>/simready_usd/sm_<name>.usda.

    parts: list of (part_name, material_key, (points, tris), collision_approximation, part_label)
    """
    folder = os.path.join(OUT, "assets", name, "simready_usd")
    os.makedirs(folder, exist_ok=True)
    fname = f"sm_{name}.usda"
    path = os.path.join(folder, fname)
    if os.path.exists(path):
        os.remove(path)
    stage, root = new_stage(path, name)
    rp = root.GetPrim()
    rb = UsdPhysics.RigidBodyAPI.Apply(rp)
    if kinematic:
        rb.CreateKinematicEnabledAttr(True)       # course furniture: fixed in the world but still a body
    UsdPhysics.MassAPI.Apply(rp).CreateMassAttr(float(mass))
    label(rp, cls)
    mats = {}
    lo, hi = [1e9] * 3, [-1e9] * 3
    for part, mkey, (pts, tris), approx, plabel in parts:
        if mkey not in mats:
            mats[mkey] = define_material(stage, f"/{name}", mkey)
        mesh = define_mesh(stage, f"/{name}/{part}", pts, tris)
        UsdPhysics.CollisionAPI.Apply(mesh.GetPrim())
        mc = UsdPhysics.MeshCollisionAPI.Apply(mesh.GetPrim())
        mc.CreateApproximationAttr(approx)
        bind(mesh.GetPrim(), mats[mkey])
        if plabel:
            label(mesh.GetPrim(), plabel)
        for q in pts:
            for i in range(3):
                lo[i], hi[i] = min(lo[i], q[i]), max(hi[i], q[i])
    extents = [round(hi[i] - lo[i], 4) for i in range(3)]
    meta = {"asset_name": name, "asset_type": "prop", "source_file": "rover/sim/scene/course_spec.json",
            "usd_date_generated": TODAY}
    stage.GetRootLayer().customLayerData = {"SimReady_Metadata": meta}
    stage.GetRootLayer().Save()
    sidecar = {"author": "rover team", "asset_license": "CC-BY 4.0", "category": category, "qcode": qcode,
               "rigid_body_count": 1, "asset_extents": extents, "mass": float(mass)}
    json.dump(sidecar, open(os.path.join(folder, f"sm_{name}.json"), "w"), indent=2)
    ASSETS_META[name] = {"path": os.path.relpath(path, OUT), "class": cls, "extents": extents, "mass": mass,
                         "kinematic": kinematic, "materials": sorted(mats)}
    return path


# ---------------------------------------------------------------- the props
def build_props():
    H = SPEC["hurdles"]
    for h in H["height"]:
        cm = int(round(h * 100))
        build_prop(f"hurdle_h{cm:02d}", "obstacle", "hurdle",
                   [("bar", "hazard_yellow", box_tris(0, 0, h / 2, H["thickness"], H["width"], h), "convexHull", None)],
                   mass=H["thickness"] * H["width"] * h * 600, kinematic=True)

    c = SPEC["cone"]
    build_prop("traffic_cone", "obstacle", "traffic_cone",
               [("cone", "cone_pvc", cone_tris(c["height"], c["base"]), "convexHull", None)], mass=c["mass"], kinematic=False)

    # barrier: two cones + striped bar, one rigid body so a hit knocks it over as a unit
    off = SPEC["cone_barriers"]["cone_offsets"]
    span = off[1] - off[0]
    bar_h = SPEC["cone_barriers"]["bar_height"]
    cones = [cone_tris(c["height"], c["base"]) for _ in off]
    shifted = [([(x, y + s, z) for x, y, z in p], t) for (p, t), s in zip(cones, (-span / 2, span / 2))]
    build_prop("cone_barrier", "obstacle", "barrier",
               [("cone_a", "cone_pvc", shifted[0], "convexHull", "traffic_cone"),
                ("cone_b", "cone_pvc", shifted[1], "convexHull", "traffic_cone"),
                ("bar", "hazard_yellow", box_tris(0, 0, bar_h, 0.06, span, 0.06), "convexHull", "barrier_bar")],
               mass=2 * c["mass"] + 0.8, kinematic=False)

    # mud pit: mud surface (low friction) + two 10 cm curbs
    M = SPEC["mud_pit"]
    mud = heightfield_tris(M["length"], M["width"], 80, 10,
                           lambda u, v: 0.03 + 0.03 * math.sin(u * 1.7) * math.cos(v * 2.3), base=0.0)
    mud = ([(x - M["length"] / 2, y, z) for x, y, z in mud[0]], mud[1])
    curbs = [box_tris(0, s * (M["width"] / 2 + 0.05), M["curb_height"] / 2, M["length"] + 0.2, 0.1, M["curb_height"]) for s in (-1, 1)]
    build_prop("mud_pit", "obstacle", "mud_pit",
               [("mud", "mud", mud, "none", "mud"), ("curb_s", "concrete", curbs[0], "convexHull", "curb"),
                ("curb_n", "concrete", curbs[1], "convexHull", "curb")],
               mass=M["length"] * M["width"] * 0.05 * 1700, kinematic=True)

    # stairs (5 x 20 cm at 35°) + 4 m platform + 20° ramp down, one steel unit
    S = SPEC["stairs"]
    tread = S["rise"] / math.tan(math.radians(S["slope_deg"]))
    top = S["rise"] * S["steps"]
    ramp = top / math.tan(math.radians(S["ramp_deg"]))
    steps = [box_tris(i * tread + tread / 2, 0, S["rise"] * (i + 1) / 2, tread, S["width"], S["rise"] * (i + 1)) for i in range(S["steps"])]
    px0 = S["steps"] * tread
    platform = box_tris(px0 + S["platform_length"] / 2, 0, top / 2, S["platform_length"], S["width"], top)
    rx0 = px0 + S["platform_length"]
    ramp_p = prism_tris([(rx0, 0.0), (rx0 + ramp, 0.0), (rx0, top)], -S["width"] / 2, S["width"] / 2)
    parts = [(f"step_{i + 1}", "steel_grate", st, "convexHull", "stairs") for i, st in enumerate(steps)]
    parts += [("platform", "steel_grate", platform, "convexHull", "platform"), ("ramp", "steel_grate", ramp_p, "convexHull", "ramp")]
    build_prop("stairs_platform_ramp", "obstacle", "stairs", parts, mass=1500.0, kinematic=True)

    # crossing pitch / roll ramps: 15° triangular waves, phase-shifted across the lane
    P = SPEC["pitch_roll"]
    k = math.tan(math.radians(P["slope_deg"]))
    wl = P["wavelength"]
    tri = lambda x, ph: k * abs((((x + ph) % wl) + wl) % wl - wl / 2)

    def pr(u, v):
        s = v / P["width"]
        e = max(0.0, min(1.0, u / 1.2, (P["length"] - u) / 1.2))
        return 0.002 + (0.02 + tri(u, 0) * (1 - s) + tri(u, wl / 2) * s) * e
    field = heightfield_tris(P["length"], P["width"], 160, 16, pr)
    field = ([(x - P["length"] / 2, y, z) for x, y, z in field[0]], field[1])
    curbs = [box_tris(0, s * (P["width"] / 2 + 0.05), P["curb_height"] / 2, P["length"] + 0.2, 0.1, P["curb_height"]) for s in (-1, 1)]
    build_prop("pitch_roll_ramps", "obstacle", "pitch_roll_ramp",
               [("ramps", "plywood", field, "none", None), ("curb_s", "concrete", curbs[0], "convexHull", "curb"),
                ("curb_n", "concrete", curbs[1], "convexHull", "curb")],
               mass=600.0, kinematic=True)

    # gravel pile up to 1 m between 0.6 m concrete walls
    G = SPEC["gravel"]

    def gfn(u, v):
        t = u / G["length"]
        base = max(0.0, math.sin(math.pi * t)) ** 0.75 * (0.88 + 0.12 * math.sin(math.pi * v / G["width"]))
        return max(0.02, base * 0.94 * G["max_height"] + 0.04 * (math.sin(u * 7.1 + v * 3.3) + math.sin(u * 13.7 - v * 9.1)) * 0.5)
    pile = heightfield_tris(G["length"], G["width"], 100, 14, gfn)
    pile = ([(x - G["length"] / 2, y, z) for x, y, z in pile[0]], pile[1])
    walls = [box_tris(0, s * (G["width"] / 2 + 0.1), G["wall_height"] / 2, G["length"] + 0.4, 0.2, G["wall_height"]) for s in (-1, 1)]
    build_prop("gravel_pile", "obstacle", "gravel",
               [("pile", "gravel", pile, "none", None), ("wall_s", "concrete", walls[0], "convexHull", "wall"),
                ("wall_n", "concrete", walls[1], "convexHull", "wall")],
               mass=G["length"] * G["width"] * 0.5 * 1600, kinematic=True)


# ---------------------------------------------------------------- route (same curve as the browser simulator)
class CatmullRom:
    """Centripetal Catmull-Rom through 2D points, arc-length parameterised like three.js CatmullRomCurve3."""

    def __init__(self, pts, divisions=200):
        self.p = [Gf.Vec2d(*q) for q in pts]
        self.lengths = [0.0]
        last = self.point(0.0)
        for i in range(1, divisions + 1):
            cur = self.point(i / divisions)
            self.lengths.append(self.lengths[-1] + (cur - last).GetLength())
            last = cur

    def point(self, t):
        p, l = self.p, len(self.p)
        x = (l - 1) * t
        i = int(math.floor(x))
        w = x - i
        if i >= l - 1:
            i, w = l - 2, 1.0
        p0 = p[i - 1] if i > 0 else p[0] * 2 - p[1]
        p1, p2 = p[i], p[i + 1]
        p3 = p[i + 2] if i + 2 < l else p[l - 1] * 2 - p[l - 2]
        dt0, dt1, dt2 = ((b - a).GetLength() ** 0.5 for a, b in ((p0, p1), (p1, p2), (p2, p3)))
        dt1 = dt1 if dt1 >= 1e-4 else 1.0
        dt0 = dt0 if dt0 >= 1e-4 else dt1
        dt2 = dt2 if dt2 >= 1e-4 else dt1
        out = []
        for k in range(2):
            x0, x1, x2, x3 = p0[k], p1[k], p2[k], p3[k]
            t1 = ((x1 - x0) / dt0 - (x2 - x0) / (dt0 + dt1) + (x2 - x1) / dt1) * dt1
            t2 = ((x2 - x1) / dt1 - (x3 - x1) / (dt1 + dt2) + (x3 - x2) / dt2) * dt1
            c2, c3 = -3 * x1 + 3 * x2 - 2 * t1 - t2, 2 * x1 - 2 * x2 + t1 + t2
            out.append(x1 + t1 * w + c2 * w * w + c3 * w * w * w)
        return Gf.Vec2d(*out)

    def length(self):
        return self.lengths[-1]

    def point_at(self, u):
        target, L = u * self.lengths[-1], self.lengths
        lo, hi = 0, len(L) - 1
        while lo < hi - 1:
            mid = (lo + hi) // 2
            lo, hi = (mid, hi) if L[mid] <= target else (lo, mid)
        seg = L[hi] - L[lo]
        t = (lo + ((target - L[lo]) / seg if seg > 0 else 0)) / (len(L) - 1)
        return self.point(t)

    def tangent_at(self, u, d=1e-4):
        a, b = self.point_at(max(0, u - d)), self.point_at(min(1, u + d))
        return (b - a).GetNormalized()


def route():
    """Dense route polyline (USD XY) from start to finish, and barrier placements around the roundabout."""
    Ln = SPEC["lanes"]["length"]
    yo, yr = SPEC["lanes"]["outbound_y"], SPEC["lanes"]["return_y"]
    loop = CatmullRom(SPEC["roundabout"])
    pts = [(x * 0.5, yo) for x in range(int(Ln * 2) + 1)]
    pts += [tuple(loop.point_at(i / 200)) for i in range(1, 200)]
    pts += [(Ln - x * 0.5, yr) for x in range(int(Ln * 2) + 1)]
    B = SPEC["cone_barriers"]
    barriers, side, t = [], 1, B["t_start"]
    for _ in range(B["count"]):
        p, d = loop.point_at(t), loop.tangent_at(t)
        n = Gf.Vec2d(d[1], -d[0]) * side                      # lateral, alternating sides
        c = p + n * ((B["cone_offsets"][0] + B["cone_offsets"][1]) / 2)
        barriers.append({"x": c[0], "y": c[1], "yaw_deg": math.degrees(math.atan2(n[1], n[0])) - 90.0})
        side, t = -side, t + B["t_step"]
    return pts, barriers, loop.length()


# ---------------------------------------------------------------- course composition
def place(stage, path, asset, x, y, yaw=0.0, label_cls=None):
    xf = UsdGeom.Xform.Define(stage, path)
    xf.GetPrim().GetReferences().AddReference(f"../assets/{asset}/simready_usd/sm_{asset}.usda")  # relative to layers/
    api = UsdGeom.XformCommonAPI(xf)
    api.SetTranslate(Gf.Vec3d(x, y, 0.0))
    if yaw:
        api.SetRotate(Gf.Vec3f(0, 0, yaw))
    return xf


def build_course():
    pts, barriers, loop_len = route()
    Ln, yo, yr = SPEC["lanes"]["length"], SPEC["lanes"]["outbound_y"], SPEC["lanes"]["return_y"]
    layers = os.path.join(OUT, "layers")
    os.makedirs(layers, exist_ok=True)

    # geometry layer: ground, lanes, obstacles
    g, root = new_stage(os.path.join(layers, "geometry.usda"), "course")
    gm = define_material(g, "/course", "asphalt")
    ground = define_mesh(g, "/course/ground", *box_tris(44.0, 2.0, -0.05, 260.0, 120.0, 0.1))
    UsdPhysics.CollisionAPI.Apply(ground.GetPrim())
    bind(ground.GetPrim(), gm)
    label(ground.GetPrim(), "floor")
    H = SPEC["hurdles"]
    for x, h in zip(H["x"], H["height"]):
        place(g, f"/course/station_1/hurdle_h{int(round(h * 100)):02d}", f"hurdle_h{int(round(h * 100)):02d}", x, yo)
    M = SPEC["mud_pit"]
    place(g, "/course/station_2/mud_pit", "mud_pit", M["x0"] + M["length"] / 2, yo)
    place(g, "/course/station_3_4/stairs_platform_ramp", "stairs_platform_ramp", SPEC["stairs"]["x0"], yo)
    for i, b in enumerate(barriers):
        place(g, f"/course/station_5/barrier_{i + 1}", "cone_barrier", b["x"], b["y"], b["yaw_deg"])
    P, G = SPEC["pitch_roll"], SPEC["gravel"]
    place(g, "/course/station_6/pitch_roll_ramps", "pitch_roll_ramps", P["x0"] + P["length"] / 2, yr)
    place(g, "/course/station_7/gravel_pile", "gravel_pile", G["x0"] + G["length"] / 2, yr)
    # start / finish lines and bypass lanes: visual + semantic only (no collider; robots drive over them)
    lines = define_material(g, "/course", "hazard_yellow")
    for name, y, cls in (("start_line", yo, "start_line"), ("finish_line", yr, "robot_target")):
        m = define_mesh(g, f"/course/{name}", *box_tris(0.5, y, 0.002, 0.3, 2.4, 0.004))
        bind(m.GetPrim(), lines)
        label(m.GetPrim(), cls)
    for i, b in enumerate(SPEC["bypass"]):
        m = define_mesh(g, f"/course/bypass_{i + 1}", *box_tris((b["x0"] + b["x1"]) / 2, b["y"], 0.002, b["x1"] - b["x0"], b["width"], 0.004))
        bind(m.GetPrim(), define_material(g, "/course", "concrete"))
        label(m.GetPrim(), "bypass_lane")
    g.GetRootLayer().Save()

    # physics layer: scene settings only (bodies, colliders and materials live in the props)
    ph = Usd.Stage.CreateNew(os.path.join(layers, "physics.usda"))
    UsdGeom.SetStageUpAxis(ph, UsdGeom.Tokens.z)
    UsdGeom.SetStageMetersPerUnit(ph, 1.0)
    sc = UsdPhysics.Scene.Define(ph, "/course/physics_scene")
    sc.CreateGravityDirectionAttr(Gf.Vec3f(0, 0, -1))
    sc.CreateGravityMagnitudeAttr(9.81)
    ph.GetRootLayer().Save()

    # lighting layer: sun + sky fill
    lt = Usd.Stage.CreateNew(os.path.join(layers, "lighting.usda"))
    UsdGeom.SetStageUpAxis(lt, UsdGeom.Tokens.z)
    UsdGeom.SetStageMetersPerUnit(lt, 1.0)
    sun = UsdLux.DistantLight.Define(lt, "/course/lights/sun")
    sun.CreateIntensityAttr(3000.0)
    sun.CreateAngleAttr(0.53)
    UsdGeom.XformCommonAPI(sun).SetRotate(Gf.Vec3f(-35.0, 20.0, 0.0))
    UsdLux.DomeLight.Define(lt, "/course/lights/sky").CreateIntensityAttr(600.0)
    lt.GetRootLayer().Save()

    # sensors layer: overview + robot-eye cameras before every station (0.35 m, the FPV mount height)
    sn = Usd.Stage.CreateNew(os.path.join(layers, "sensors.usda"))
    UsdGeom.SetStageUpAxis(sn, UsdGeom.Tokens.z)
    UsdGeom.SetStageMetersPerUnit(sn, 1.0)
    cams = {}

    def camera(name, eye, target, focal=18.0):
        cam = UsdGeom.Camera.Define(sn, f"/course/cameras/{name}")
        cam.CreateFocalLengthAttr(focal)
        cam.CreateHorizontalApertureAttr(36.0)
        cam.CreateVerticalApertureAttr(20.25)
        cam.CreateClippingRangeAttr(Gf.Vec2f(0.05, 500.0))
        m = Gf.Matrix4d().SetLookAt(Gf.Vec3d(*eye), Gf.Vec3d(*target), Gf.Vec3d(0, 0, 1)).GetInverse()
        cam.AddTransformOp().Set(m)
        cams[name] = {"eye": eye, "target": target, "focal": focal}

    camera("overview", (35.0, -105.0, 85.0), (58.0, 2.0, 0.0), 24.0)
    S = SPEC["stairs"]
    # FPV view 3 m before each station along the route, tilted down toward the obstacle base like a real FPV mount
    def before(tx, ty, dist=3.0):
        k = min(range(len(pts)), key=lambda i: (pts[i][0] - tx) ** 2 + (pts[i][1] - ty) ** 2)
        acc, i = 0.0, k
        while i > 0 and acc < dist:
            acc += math.hypot(pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1])
            i -= 1
        return pts[i]
    targets = {
        "fpv_station_1": (H["x"][0] + 0.5, yo), "fpv_station_2": (M["x0"] + 1.0, yo), "fpv_station_3": (S["x0"] + 0.5, yo),
        "fpv_station_5": (barriers[0]["x"], barriers[0]["y"]), "fpv_station_6": (P["x0"] + P["length"] - 1.0, yr),
        "fpv_station_7": (G["x0"] + G["length"] - 1.0, yr),
    }
    for name, (tx, ty) in targets.items():
        ex, ey = before(tx, ty)
        camera(name, (ex, ey, 0.35), (tx, ty, 0.0))
    sn.GetRootLayer().Save()

    # course.usda: the handoff file Isaac Sim opens; sublayers stay separately editable
    if os.path.exists(os.path.join(OUT, "course.usda")):
        os.remove(os.path.join(OUT, "course.usda"))
    course = Usd.Stage.CreateNew(os.path.join(OUT, "course.usda"))
    course.GetRootLayer().subLayerPaths = ["./layers/sensors.usda", "./layers/lighting.usda", "./layers/physics.usda", "./layers/geometry.usda"]
    UsdGeom.SetStageUpAxis(course, UsdGeom.Tokens.z)
    UsdGeom.SetStageMetersPerUnit(course, 1.0)
    UsdPhysics.SetStageKilogramsPerUnit(course, 1.0)
    course.SetDefaultPrim(course.GetPrimAtPath("/course"))
    course.GetRootLayer().customLayerData = {"SimReady_Metadata": {"asset_name": "shalun_course", "asset_type": "environment",
                                                                   "source_file": "rover/sim/scene/course_spec.json", "usd_date_generated": TODAY}}
    course.GetRootLayer().Save()
    json.dump({"route_xy": [[round(a, 3), round(b, 3)] for a, b in pts], "loop_length": loop_len, "barriers": barriers, "cameras": cams},
              open(os.path.join(OUT, "route.json"), "w"), indent=1)
    return course


if __name__ == "__main__":
    for sub in ("assets", "layers"):
        if os.path.isdir(os.path.join(OUT, sub)):
            shutil.rmtree(os.path.join(OUT, sub))
    build_props()
    build_course()
    json.dump(ASSETS_META, open(os.path.join(OUT, "assets_index.json"), "w"), indent=2, ensure_ascii=False)
    # material sidecar in the article's field layout; values are the ones authored into the USD materials
    json.dump({"schema_version": "1.0", "materials": [
        {"material_id": k, "material_class": v["cls"], "material_type": "UsdPreviewSurface", "finish": v["finish"], "condition": "outdoor",
         "pbr": {"diffuse_color": list(v["color"]), "roughness": v["rough"], "metallic": v["metal"]},
         "physics": {"static_friction": v["sf"], "dynamic_friction": v["df"], "restitution": v["rest"], "density_kg_m3": v["density"]},
         "tags": [v["cls"], "obstacle_course"]} for k, v in MATERIALS.items()]},
        open(os.path.join(OUT, "material_metadata.json"), "w"), indent=2)
    print("props:", ", ".join(ASSETS_META))
