"""Isaac Sim 5.0 checks for out/course.usda: real PhysX behaviour + RTX robot-eye renders.

Run with Isaac Sim's own Python (Windows example):

    C:\\isaacsim\\python.bat rover\\sim\\scene\\isaac\\run_isaac_checks.py
    C:\\isaacsim\\python.bat rover\\sim\\scene\\isaac\\run_isaac_checks.py --gui      # watch it

Writes rover/sim/scene/out/isaac/: report.json, renders/ (RGB + semantic per FPV camera).
Each test is independent; a failing test is recorded and the next one still runs.
"""
import argparse
import json
import math
import os
import sys
import time
import traceback

parser = argparse.ArgumentParser()
parser.add_argument("--gui", action="store_true", help="open a window instead of running headless")
parser.add_argument("--skip-render", action="store_true")
args, _ = parser.parse_known_args()

from isaacsim import SimulationApp  # noqa: E402  (must start before any omni import)

app = SimulationApp({"headless": not args.gui, "width": 1280, "height": 720})

import numpy as np  # noqa: E402
import omni.usd  # noqa: E402
from pxr import Gf, Usd, UsdGeom, UsdPhysics  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.normpath(os.path.join(HERE, "..", "out"))
COURSE = os.path.join(OUT, "course.usda")
RESULT_DIR = os.path.join(OUT, "isaac")
os.makedirs(RESULT_DIR, exist_ok=True)
ROUTE = json.load(open(os.path.join(OUT, "route.json"), encoding="utf-8"))
SPEC = json.load(open(os.path.join(HERE, "..", "course_spec.json"), encoding="utf-8"))

report = {"isaac_sim": None, "course": COURSE, "tests": [], "renders": {}, "started": time.strftime("%Y-%m-%d %H:%M:%S")}
try:
    from isaacsim.core.version import get_version
    report["isaac_sim"] = ".".join(str(v) for v in get_version()[:3])
except Exception:  # version helper moved between releases; not essential
    pass


def record(name, passed, detail, data=None):
    report["tests"].append({"name": name, "status": "pass" if passed else "fail", "detail": detail, "data": data or {}})
    print(f"[{'PASS' if passed else 'FAIL'}] {name}: {detail}", flush=True)


def run_test(name, fn):
    try:
        fn()
    except Exception as e:  # keep going; the traceback goes in the report
        report["tests"].append({"name": name, "status": "error", "detail": repr(e), "trace": traceback.format_exc()})
        print(f"[ERROR] {name}: {e!r}", flush=True)


def wait_frames(n=10):
    for _ in range(n):
        app.update()


# ------------------------------------------------------------------ open the stage
ctx = omni.usd.get_context()
ok = ctx.open_stage(COURSE)
wait_frames(30)
while ctx.get_stage_loading_status()[2] > 0:
    app.update()
stage = ctx.get_stage()
record("stage_opens", bool(ok and stage and stage.GetPrimAtPath("/course").IsValid()), f"opened {COURSE}")
meshes = [p for p in stage.Traverse() if p.IsA(UsdGeom.Mesh)]
bodies = [p for p in stage.Traverse() if p.HasAPI(UsdPhysics.RigidBodyAPI)]
record("stage_contents", len(meshes) >= 40 and len(bodies) == 16,
       f"{len(meshes)} meshes, {len(bodies)} rigid bodies (expected 49 / 16)",
       {"meshes": len(meshes), "bodies": len(bodies), "up_axis": UsdGeom.GetStageUpAxis(stage)})

# ------------------------------------------------------------------ RTX renders from the authored cameras
def render_fpv():
    import omni.replicator.core as rep
    cams = [str(p.GetPath()) for p in stage.Traverse() if p.IsA(UsdGeom.Camera)]
    out = os.path.join(RESULT_DIR, "renders")
    os.makedirs(out, exist_ok=True)
    rps = [rep.create.render_product(c, (1280, 720)) for c in cams]
    writer = rep.WriterRegistry.get("BasicWriter")
    writer.initialize(output_dir=out, rgb=True, semantic_segmentation=True, colorize_semantic_segmentation=True,
                      semantic_types=["class"])
    writer.attach(rps)
    for _ in range(3):
        rep.orchestrator.step(rt_subframes=16)
    rep.orchestrator.wait_until_complete()
    writer.detach()
    files = sorted(os.listdir(out))
    labels = {}
    for f in files:
        if f.startswith("semantic_segmentation_labels") and f.endswith(".json"):
            labels[f] = sorted({v.get("class", str(v)) if isinstance(v, dict) else str(v)
                                for v in json.load(open(os.path.join(out, f))).values()})
    report["renders"] = {"cameras": cams, "files": files[:60], "semantic_classes": labels}
    seen = set(c for v in labels.values() for c in v)
    want = {"hurdle", "mud", "stairs", "traffic_cone", "pitch_roll_ramp", "gravel"}
    record("rtx_render", len([f for f in files if f.endswith(".png")]) >= len(cams),
           f"{len(cams)} cameras rendered to {out}")
    record("rtx_semantics", want <= seen, f"classes seen by the RTX segmentation: {sorted(seen)}; missing: {sorted(want - seen)}")


if not args.skip_render:
    run_test("rtx_render", render_fpv)

# ------------------------------------------------------------------ PhysX tests
from isaacsim.core.api import World  # noqa: E402
from isaacsim.core.api.materials import PhysicsMaterial  # noqa: E402
from isaacsim.core.api.objects import DynamicCuboid, FixedCuboid  # noqa: E402
from isaacsim.core.prims import RigidPrim  # noqa: E402

world = World(stage_units_in_meters=1.0, physics_dt=1 / 120, rendering_dt=1 / 60, physics_prim_path="/course/physics_scene")
tyre = PhysicsMaterial("/World/test_materials/rubber", static_friction=0.9, dynamic_friction=0.9, restitution=0.05)

barrier_paths = [f"/course/station_5/barrier_{i + 1}" for i in range(len(ROUTE["barriers"]))]
kinematic_paths = ["/course/station_1/hurdle_h20", "/course/station_2/mud_pit", "/course/station_3_4/stairs_platform_ramp",
                   "/course/station_6/pitch_roll_ramps", "/course/station_7/gravel_pile"]


def box(name, pos, size, mass):
    return world.scene.add(DynamicCuboid(prim_path=f"/World/tests/{name}", name=name, position=np.array(pos, dtype=float),
                                         scale=np.array(size, dtype=float), size=1.0, mass=mass,
                                         color=np.array([0.1, 0.6, 0.9]), physics_material=tyre))


# probe bodies, placed before the first reset
y_out = SPEC["lanes"]["outbound_y"]
mud_x = SPEC["mud_pit"]["x0"] + 5.0
S = SPEC["stairs"]
plat_x = S["x0"] + S["steps"] * S["rise"] / math.tan(math.radians(S["slope_deg"])) + S["platform_length"] / 2
probe_mud = box("probe_mud", [mud_x, y_out, 0.35], [0.6, 0.5, 0.3], 40.0)
probe_asphalt = box("probe_asphalt", [5.0, y_out, 0.3], [0.6, 0.5, 0.3], 40.0)
probe_platform = box("probe_platform", [plat_x, y_out, 1.6], [0.6, 0.5, 0.3], 40.0)
probe_gravel = box("probe_gravel", [SPEC["gravel"]["x0"] + 10.0, SPEC["lanes"]["return_y"], 1.8], [0.6, 0.5, 0.3], 40.0)

# pusher: a kinematic block driven through barrier 1's first cone at 1 m/s, like a robot that misses the gap
b1 = ROUTE["barriers"][0]
yaw = math.radians(b1["yaw_deg"])
cone_a = np.array([b1["x"] + 0.7 * math.sin(yaw), b1["y"] - 0.7 * math.cos(yaw)])   # local (0, -0.7) rotated by yaw
pts = np.array(ROUTE["route_xy"])
k = int(np.argmin(np.linalg.norm(pts - cone_a, axis=1)))
tangent = pts[min(k + 4, len(pts) - 1)] - pts[max(k - 4, 0)]
tangent /= np.linalg.norm(tangent)
push_start = cone_a - tangent * 2.0
pusher = world.scene.add(FixedCuboid(prim_path="/World/tests/pusher", name="pusher", position=np.array([*push_start, 0.36]),
                                     scale=np.array([0.6, 0.5, 0.7]), size=1.0, color=np.array([0.9, 0.2, 0.2])))
UsdPhysics.RigidBodyAPI.Apply(stage.GetPrimAtPath("/World/tests/pusher")).CreateKinematicEnabledAttr(True)

barriers = RigidPrim(barrier_paths, name="barriers")
fixed = RigidPrim(kinematic_paths, name="fixed_obstacles")
world.scene.add(barriers)
world.scene.add(fixed)
world.reset()


def poses(view):
    p, q = view.get_world_poses()
    return np.array(p), np.array(q)


def tilt_deg(q):
    """Angle between the body's up axis and world Z, from a (w, x, y, z) quaternion."""
    w, x, y, z = q
    up_z = 1 - 2 * (x * x + y * y)
    return math.degrees(math.acos(max(-1.0, min(1.0, up_z))))


def step(seconds):
    for _ in range(int(seconds * 120)):
        world.step(render=args.gui)


# 1. start-up stability: nothing explodes, sinks or tips in the first 2 s
def t_settle():
    p0, _ = poses(barriers)
    f0, _ = poses(fixed)
    step(2.0)
    p1, q1 = poses(barriers)
    f1, _ = poses(fixed)
    moved = np.linalg.norm(p1 - p0, axis=1)
    tilts = [tilt_deg(q) for q in q1]
    fixed_moved = float(np.max(np.linalg.norm(f1 - f0, axis=1)))
    record("settle_barriers", float(moved.max()) < 0.02 and max(tilts) < 3,
           f"barriers moved at most {moved.max() * 100:.1f} cm, max tilt {max(tilts):.1f}° after 2 s idle",
           {"moved_m": moved.round(4).tolist(), "tilt_deg": [round(t, 2) for t in tilts]})
    record("fixed_obstacles_static", fixed_moved < 1e-4, f"kinematic course furniture moved {fixed_moved:.2e} m")


# 2. collider heights: probes dropped on the stair platform and the gravel pile come to rest on top
def t_rest_heights():
    pp = probe_platform.get_world_pose()[0]
    pg = probe_gravel.get_world_pose()[0]
    top = S["rise"] * S["steps"]
    record("platform_collider", abs(pp[2] - (top + 0.15)) < 0.03, f"box rests at z={pp[2]:.3f} m on the platform (expected {top + 0.15:.2f})")
    record("gravel_collider", 0.6 < pg[2] < 1.25, f"box rests at z={pg[2]:.3f} m on the gravel pile (peak ≈ 0.98 m)")


# 3. friction: slide 40 kg rubber-soled probes at 1 m/s on mud vs asphalt
def t_friction():
    d = {}
    for name, probe in (("mud", probe_mud), ("asphalt", probe_asphalt)):
        start = probe.get_world_pose()[0].copy()
        probe.set_linear_velocity(np.array([1.0, 0.0, 0.0]))
        step(2.0)
        d[name] = float(probe.get_world_pose()[0][0] - start[0])
    # mu_eff ≈ v^2 / (2 g d); mud should behave like 0.15 (min combine), asphalt like ~0.85 (average)
    mu = {k: (1.0 / (2 * 9.81 * v) if v > 1e-3 else float("inf")) for k, v in d.items()}
    record("mud_friction", 0.09 < mu["mud"] < 0.25, f"slide {d['mud']:.2f} m on mud → effective μ {mu['mud']:.2f} (target 0.15)",
           {"slide_m": d, "mu_eff": mu})
    record("asphalt_friction", mu["asphalt"] > 0.5, f"slide {d['asphalt']:.2f} m on asphalt → effective μ {mu['asphalt']:.2f}")


# 4. a robot clipping a cone knocks the barrier over / out of place
def t_knock():
    p0, _ = poses(barriers)
    for i in range(int(3.5 * 120)):
        pos = push_start + tangent * min(3.0, i / 120 * 1.0)
        pusher.set_world_pose(position=np.array([pos[0], pos[1], 0.36]))
        world.step(render=args.gui)
    step(1.0)
    p1, q1 = poses(barriers)
    moved = float(np.linalg.norm(p1[0] - p0[0]))
    tilt = tilt_deg(q1[0])
    record("barrier_knocked", moved > 0.10 or tilt > 20, f"barrier 1 moved {moved * 100:.0f} cm, tilted {tilt:.0f}° after being clipped at 1 m/s",
           {"moved_m": moved, "tilt_deg": tilt})
    others = float(np.max(np.linalg.norm(p1[1:] - p0[1:], axis=1)))
    record("other_barriers_untouched", others < 0.02, f"other barriers moved at most {others * 100:.1f} cm")


for name, fn in (("settle", t_settle), ("rest_heights", t_rest_heights), ("friction", t_friction), ("knock", t_knock)):
    run_test(name, fn)

# ------------------------------------------------------------------ report
report["finished"] = time.strftime("%Y-%m-%d %H:%M:%S")
report["summary"] = {s: sum(t["status"] == s for t in report["tests"]) for s in ("pass", "fail", "error")}
path = os.path.join(RESULT_DIR, "report.json")
json.dump(report, open(path, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
print("\nsummary:", report["summary"], "\nreport:", path, flush=True)
app.close()
sys.exit(0)
