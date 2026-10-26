"""Tessellation and a small GLB writer.

The GLB is written directly from the B-rep triangulation so the simulator gets exactly the frame it uses (X forward,
Y up, Z right, metres) with no exporter axis conversion in between. Normals are averaged within each B-rep face only,
so curved faces shade smoothly and the edges between faces stay sharp.
"""
import json
import struct

import numpy as np
from OCP.BRep import BRep_Tool
from OCP.BRepMesh import BRepMesh_IncrementalMesh
from OCP.TopAbs import TopAbs_FACE, TopAbs_REVERSED
from OCP.TopExp import TopExp_Explorer
from OCP.TopLoc import TopLoc_Location
from OCP.TopoDS import TopoDS


def tessellate(shape, lin=0.08, ang=0.35):
    """Triangulate a build123d shape (mm). Returns (positions mm, normals, indices) as numpy arrays."""
    w = shape.wrapped
    BRepMesh_IncrementalMesh(w, lin, False, ang, True)
    P, N, I = [], [], []
    base = 0
    exp = TopExp_Explorer(w, TopAbs_FACE)
    while exp.More():
        face = TopoDS.Face(exp.Current())
        loc = TopLoc_Location()
        tri = BRep_Tool.Triangulation_s(face, loc)
        exp.Next()
        if tri is None:
            continue
        trsf = loc.Transformation()
        nn = tri.NbNodes()
        pts = np.empty((nn, 3))
        for i in range(1, nn + 1):
            p = tri.Node(i).Transformed(trsf)
            pts[i - 1] = (p.X(), p.Y(), p.Z())
        nt = tri.NbTriangles()
        idx = np.empty((nt, 3), dtype=np.int64)
        rev = face.Orientation() == TopAbs_REVERSED
        for i in range(1, nt + 1):
            a, b, c = tri.Triangle(i).Get()
            idx[i - 1] = (a - 1, c - 1, b - 1) if rev else (a - 1, b - 1, c - 1)
        # area-weighted vertex normals within this face
        fn = np.cross(pts[idx[:, 1]] - pts[idx[:, 0]], pts[idx[:, 2]] - pts[idx[:, 0]])
        vn = np.zeros_like(pts)
        for k in range(3):
            np.add.at(vn, idx[:, k], fn)
        ln = np.linalg.norm(vn, axis=1, keepdims=True)
        ln[ln == 0] = 1
        P.append(pts)
        N.append(vn / ln)
        I.append(idx + base)
        base += nn
    if not P:
        return np.zeros((0, 3)), np.zeros((0, 3)), np.zeros((0, 3), dtype=np.int64)
    return np.vstack(P), np.vstack(N), np.vstack(I)


def write_glb(path, meshes, extras=None):
    """meshes: list of dicts {name, positions (mm), normals, indices, extras}. Writes metres, one node per mesh."""
    bin_chunks = []
    offset = 0
    buffer_views, accessors, gl_meshes, nodes = [], [], [], []

    def add_view(arr, target):
        nonlocal offset
        data = arr.tobytes()
        pad = (-len(data)) % 4
        bin_chunks.append(data + b"\0" * pad)
        buffer_views.append({"buffer": 0, "byteOffset": offset, "byteLength": len(data), "target": target})
        offset += len(data) + pad
        return len(buffer_views) - 1

    for m in meshes:
        pos = (np.asarray(m["positions"], dtype=np.float64) / 1000.0).astype(np.float32)
        nor = np.asarray(m["normals"], dtype=np.float32)
        idx = np.asarray(m["indices"]).reshape(-1)
        big = pos.shape[0] > 65535
        idx = idx.astype(np.uint32 if big else np.uint16)
        vp = add_view(pos, 34962)
        accessors.append({"bufferView": vp, "componentType": 5126, "count": int(pos.shape[0]), "type": "VEC3",
                          "min": pos.min(0).tolist(), "max": pos.max(0).tolist()})
        ap = len(accessors) - 1
        vn = add_view(nor, 34962)
        accessors.append({"bufferView": vn, "componentType": 5126, "count": int(nor.shape[0]), "type": "VEC3"})
        an = len(accessors) - 1
        vi = add_view(idx, 34963)
        accessors.append({"bufferView": vi, "componentType": 5125 if big else 5123, "count": int(idx.shape[0]), "type": "SCALAR"})
        ai = len(accessors) - 1
        gl_meshes.append({"name": m["name"], "primitives": [{"attributes": {"POSITION": ap, "NORMAL": an}, "indices": ai}]})
        node = {"name": m["name"], "mesh": len(gl_meshes) - 1}
        if m.get("extras"):
            node["extras"] = m["extras"]
        nodes.append(node)

    gltf = {
        "asset": {"version": "2.0", "generator": "docs/arhud-cad (build123d + OCP triangulation)"},
        "scene": 0, "scenes": [{"name": "housing", "nodes": list(range(len(nodes)))}],
        "nodes": nodes, "meshes": gl_meshes, "accessors": accessors, "bufferViews": buffer_views,
        "buffers": [{"byteLength": offset}],
    }
    if extras:
        gltf["extras"] = extras
    js = json.dumps(gltf, separators=(",", ":")).encode()
    js += b" " * ((-len(js)) % 4)
    binary = b"".join(bin_chunks)
    total = 12 + 8 + len(js) + 8 + len(binary)
    with open(path, "wb") as f:
        f.write(struct.pack("<III", 0x46546C67, 2, total))
        f.write(struct.pack("<II", len(js), 0x4E4F534A))
        f.write(js)
        f.write(struct.pack("<II", len(binary), 0x004E4942))
        f.write(binary)
    return total
