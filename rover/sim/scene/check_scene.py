"""Inventory + physics-readiness + spec-conformance checks for out/course.usda.

Deterministic checks only (no judgement): every finding names the prim and the rule.

    python check_scene.py            # writes out/reports/inventory.json and physics_readiness.json
"""
import json
import math
import os
import sys

from pxr import Usd, UsdGeom, UsdLux, UsdPhysics, UsdSemantics, UsdShade

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out")
SPEC = json.load(open(os.path.join(HERE, "course_spec.json"), encoding="utf-8"))
VISUAL_ONLY = ("start_line", "finish_line", "bypass_")   # painted markings: no collider by design
TOL = 0.005


def labels(prim, taxonomy="class"):
    if not prim.HasAPI(UsdSemantics.LabelsAPI, taxonomy):
        return []
    return list(UsdSemantics.LabelsAPI(prim, taxonomy).GetLabelsAttr().Get() or [])


def class_of(prim):
    p = prim
    while p and p.GetPath() != p.GetPath().absoluteRootPath:
        lb = labels(p)
        if lb:
            return lb[0]
        p = p.GetParent()
    return None


def main():
    stage = Usd.Stage.Open(os.path.join(OUT, "course.usda"))
    bbox = UsdGeom.BBoxCache(Usd.TimeCode.Default(), [UsdGeom.Tokens.default_])
    meshes = [p for p in stage.Traverse() if p.IsA(UsdGeom.Mesh)]
    mats = [p for p in stage.Traverse() if p.IsA(UsdShade.Material)]
    cams = [p for p in stage.Traverse() if p.IsA(UsdGeom.Camera)]
    lights = [p for p in stage.Traverse() if p.HasAPI(UsdLux.LightAPI)]
    bodies = [p for p in stage.Traverse() if p.HasAPI(UsdPhysics.RigidBodyAPI)]

    findings = []

    def find(rule, prim, msg, severity="fail"):
        findings.append({"rule": rule, "severity": severity, "prim": str(prim.GetPath()) if prim else "", "message": msg})

    # stage contract
    if UsdGeom.GetStageUpAxis(stage) != UsdGeom.Tokens.z:
        find("STAGE.UP", None, "upAxis must be Z")
    if UsdGeom.GetStageMetersPerUnit(stage) != 1.0:
        find("STAGE.UNITS", None, "metersPerUnit must be 1.0")
    if not [p for p in stage.Traverse() if p.IsA(UsdPhysics.Scene)]:
        find("PHYS.SCENE", None, "no PhysicsScene")

    # per-mesh: label, collider, physics material, triangle budget
    unlabeled, no_collider, no_phys_mat = [], [], []
    for m in meshes:
        name = m.GetName()
        visual_only = any(name.startswith(v) for v in VISUAL_ONLY)
        if not class_of(m):
            unlabeled.append(str(m.GetPath()))
            find("SEM.CLASS", m, "mesh has no class label on itself or an ancestor")
        if not visual_only and not m.HasAPI(UsdPhysics.CollisionAPI):
            no_collider.append(str(m.GetPath()))
            find("PHYS.COL", m, "solid mesh without CollisionAPI")
        if m.HasAPI(UsdPhysics.CollisionAPI):
            mat, _ = UsdShade.MaterialBindingAPI(m).ComputeBoundMaterial("physics")
            if not mat or not mat.GetPrim().HasAPI(UsdPhysics.MaterialAPI):
                no_phys_mat.append(str(m.GetPath()))
                find("PHYS.MAT", m, "collider without a bound physics material (friction would fall back to default)")
            tris = len(UsdGeom.Mesh(m).GetFaceVertexCountsAttr().Get() or [])
            approx = UsdPhysics.MeshCollisionAPI(m).GetApproximationAttr().Get() if m.HasAPI(UsdPhysics.MeshCollisionAPI) else "none"
            if approx == "none" and tris > 50000:
                find("PHYS.TRIS", m, f"triangle-mesh collider has {tris} triangles (> 50k)", "warn")

    # per-body: mass, dynamic bodies must not use triangle-mesh colliders, grounding
    dynamic, kinematic = [], []
    for b in bodies:
        rb = UsdPhysics.RigidBodyAPI(b)
        kin = bool(rb.GetKinematicEnabledAttr().Get())
        (kinematic if kin else dynamic).append(str(b.GetPath()))
        mass = UsdPhysics.MassAPI(b).GetMassAttr().Get() if b.HasAPI(UsdPhysics.MassAPI) else None
        if not mass or mass <= 0:
            find("PHYS.MASS", b, "rigid body without positive mass")
        if not kin:
            for d in Usd.PrimRange(b):
                if d.HasAPI(UsdPhysics.MeshCollisionAPI) and UsdPhysics.MeshCollisionAPI(d).GetApproximationAttr().Get() == "none":
                    find("PHYS.DYNMESH", d, "dynamic body uses a triangle-mesh collider (PhysX rejects this)")
        rng = bbox.ComputeWorldBound(b).ComputeAlignedRange()
        zmin = rng.GetMin()[2]
        if zmin > TOL:
            find("PHYS.FLOAT", b, f"floats {zmin:.3f} m above the ground")
        elif zmin < -TOL:
            find("PHYS.SINK", b, f"sinks {-zmin:.3f} m into the ground")

    # dynamic bodies must not start interpenetrating each other
    boxes = [(p, bbox.ComputeWorldBound(stage.GetPrimAtPath(p)).ComputeAlignedRange()) for p in dynamic]
    for i in range(len(boxes)):
        for j in range(i + 1, len(boxes)):
            if not boxes[i][1].IntersectWith(boxes[j][1]).IsEmpty():
                find("PHYS.OVERLAP", stage.GetPrimAtPath(boxes[i][0]), f"bounding box overlaps {boxes[j][0]}", "warn")

    # spec conformance: measured geometry against the briefing numbers
    def rng(path):
        return bbox.ComputeWorldBound(stage.GetPrimAtPath(path)).ComputeAlignedRange()
    measured = {}
    for h in SPEC["hurdles"]["height"]:
        cm = int(round(h * 100))
        z = rng(f"/course/station_1/hurdle_h{cm:02d}").GetMax()[2]
        measured[f"hurdle_{cm}cm_height"] = round(z, 4)
        if abs(z - h) > TOL:
            find("SPEC.HURDLE", stage.GetPrimAtPath(f"/course/station_1/hurdle_h{cm:02d}"), f"height {z:.3f} m, spec {h} m")
    S = SPEC["stairs"]
    steps = [rng(f"/course/station_3_4/stairs_platform_ramp/step_{i + 1}") for i in range(S["steps"])]
    rises = [round(steps[i].GetMax()[2] - (steps[i - 1].GetMax()[2] if i else 0.0), 4) for i in range(S["steps"])]
    treads = [steps[i].GetSize()[0] for i in range(S["steps"])]
    slope = math.degrees(math.atan2(rises[0], treads[0]))
    measured.update({"stair_rises_m": rises, "stair_slope_deg": round(slope, 2), "stair_width_m": round(steps[0].GetSize()[1], 3)})
    if any(abs(r - S["rise"]) > TOL for r in rises) or abs(slope - S["slope_deg"]) > 0.5:
        find("SPEC.STAIRS", stage.GetPrimAtPath("/course/station_3_4"), f"rises {rises}, slope {slope:.1f}°")
    ramp = rng("/course/station_3_4/stairs_platform_ramp/ramp")
    ramp_deg = math.degrees(math.atan2(ramp.GetSize()[2], ramp.GetSize()[0]))
    measured["ramp_deg"] = round(ramp_deg, 2)
    if abs(ramp_deg - S["ramp_deg"]) > 0.5:
        find("SPEC.RAMP", stage.GetPrimAtPath("/course/station_3_4"), f"ramp {ramp_deg:.1f}°")
    g = rng("/course/station_7/gravel_pile/pile")
    measured["gravel_peak_m"] = round(g.GetMax()[2], 3)
    if g.GetMax()[2] > SPEC["gravel"]["max_height"] + TOL:
        find("SPEC.GRAVEL", stage.GetPrimAtPath("/course/station_7"), f"peak {g.GetMax()[2]:.2f} m above 1 m")
    for st, path in (("mud_pit", "/course/station_2/mud_pit/mud"), ("pitch_roll", "/course/station_6/pitch_roll_ramps/ramps"),
                     ("gravel", "/course/station_7/gravel_pile/pile")):
        sz = rng(path).GetSize()
        measured[f"{st}_length_width_m"] = [round(sz[0], 3), round(sz[1], 3)]
        if abs(sz[0] - 20.0) > 0.05 or abs(sz[1] - 2.4) > 0.05:
            find("SPEC.FOOTPRINT", stage.GetPrimAtPath(path), f"{sz[0]:.2f} × {sz[1]:.2f} m, spec 20 × 2.4 m")
    pr = UsdGeom.Mesh(stage.GetPrimAtPath("/course/station_6/pitch_roll_ramps/ramps"))
    pts, idx = pr.GetPointsAttr().Get(), pr.GetFaceVertexIndicesAttr().Get()
    # interior: crossing 15° pitch with the lateral roll gives up to ~16.7° combined; entry/exit tapers reported apart
    steep = {"interior": 0.0, "entry_exit": 0.0}
    x_lo = min(q[0] for q in pts)
    for k in range(0, len(idx), 3):
        a, b, c = (pts[idx[k + i]] for i in range(3))
        n = (b - a) ^ (c - a)
        if n.GetLength() > 0 and n[2] > 0:
            u = (a[0] + b[0] + c[0]) / 3 - x_lo
            zone = "interior" if 1.2 <= u <= SPEC["pitch_roll"]["length"] - 1.2 else "entry_exit"
            steep[zone] = max(steep[zone], math.degrees(math.acos(min(1, n[2] / n.GetLength()))))
    measured["pitch_roll_max_slope_deg"] = {k: round(v, 2) for k, v in steep.items()}
    if steep["interior"] > SPEC["pitch_roll"]["slope_deg"] * 1.2:
        find("SPEC.PITCHROLL", pr.GetPrim(), f"interior facet {steep['interior']:.1f}°")
    if steep["entry_exit"] > SPEC["pitch_roll"]["slope_deg"] * 1.2:
        find("SPEC.PITCHROLL.ENTRY", pr.GetPrim(), f"entry/exit taper reaches {steep['entry_exit']:.1f}° (course model; real entry not yet published)", "warn")

    inventory = {
        "file": "out/course.usda", "up_axis": UsdGeom.GetStageUpAxis(stage), "meters_per_unit": UsdGeom.GetStageMetersPerUnit(stage),
        "counts": {"meshes": len(meshes), "materials": len(mats), "cameras": len(cams), "lights": len(lights),
                   "rigid_bodies": len(bodies), "dynamic_bodies": len(dynamic), "kinematic_bodies": len(kinematic)},
        "classes": sorted({c for c in (class_of(m) for m in meshes) if c}),
        "cameras": [str(c.GetPath()) for c in cams],
        "missing": {"semantic_labels": unlabeled, "collision_meshes": no_collider, "physics_materials": no_phys_mat},
    }
    physics = {"dynamic": dynamic, "kinematic": kinematic, "measured_vs_spec": measured, "findings": findings,
               "summary": {"fail": sum(f["severity"] == "fail" for f in findings), "warn": sum(f["severity"] == "warn" for f in findings)}}
    rep = os.path.join(OUT, "reports")
    os.makedirs(rep, exist_ok=True)
    json.dump(inventory, open(os.path.join(rep, "inventory.json"), "w"), indent=2, ensure_ascii=False)
    json.dump(physics, open(os.path.join(rep, "physics_readiness.json"), "w"), indent=2, ensure_ascii=False)
    print(json.dumps(inventory["counts"]), "classes:", ", ".join(inventory["classes"]))
    print("measured:", json.dumps(measured, ensure_ascii=False))
    for f in findings:
        print(f"  {f['severity'].upper():4} {f['rule']:14} {f['prim']}  {f['message']}")
    print("physics readiness:", physics["summary"])
    return 1 if physics["summary"]["fail"] else 0


if __name__ == "__main__":
    sys.exit(main())
