"""Flatten USD meshes to JSON (world-space triangles, colour, class label) for the preflight renderer."""
import json
import os
import sys

from pxr import Usd, UsdGeom, UsdSemantics, UsdShade

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "out")


def class_of(prim):
    p = prim
    while p and not p.IsPseudoRoot():
        if p.HasAPI(UsdSemantics.LabelsAPI, "class"):
            lb = UsdSemantics.LabelsAPI(p, "class").GetLabelsAttr().Get()
            if lb:
                return lb[0]
        p = p.GetParent()
    return None


def export(usd_path):
    stage = Usd.Stage.Open(usd_path)
    xc = UsdGeom.XformCache()
    meshes = []
    for prim in stage.Traverse():
        if not prim.IsA(UsdGeom.Mesh):
            continue
        m = UsdGeom.Mesh(prim)
        xf = xc.GetLocalToWorldTransform(prim)
        pts = [xf.Transform(p) for p in m.GetPointsAttr().Get()]
        mat, _ = UsdShade.MaterialBindingAPI(prim).ComputeBoundMaterial()
        color = None
        if mat:
            for sh in mat.GetPrim().GetChildren():
                inp = UsdShade.Shader(sh).GetInput("diffuseColor")
                if inp and inp.Get() is not None:
                    color = list(inp.Get())
        meshes.append({"path": str(prim.GetPath()), "label": class_of(prim), "color": color,
                       "positions": [round(c, 4) for p in pts for c in p],
                       "indices": list(m.GetFaceVertexIndicesAttr().Get())})
    cams = []
    for prim in stage.Traverse():
        if prim.IsA(UsdGeom.Camera):
            c = UsdGeom.Camera(prim).GetCamera()
            fr = c.frustum
            cams.append({"name": prim.GetName(), "position": list(fr.GetPosition()),
                         "target": list(fr.GetPosition() + fr.ComputeViewDirection() * 10),
                         "fov_deg": c.GetFieldOfView(c.FOVVertical), "near": c.clippingRange.min})
    return {"meshes": meshes, "cameras": cams}


if __name__ == "__main__":
    os.makedirs(os.path.join(OUT, "preview"), exist_ok=True)
    json.dump(export(os.path.join(OUT, "course.usda")), open(os.path.join(OUT, "preview", "course.json"), "w"))
    idx = json.load(open(os.path.join(OUT, "assets_index.json")))
    for name, meta in idx.items():
        json.dump(export(os.path.join(OUT, meta["path"])), open(os.path.join(OUT, "preview", f"asset_{name}.json"), "w"))
    print("exported", 1 + len(idx), "scenes")
