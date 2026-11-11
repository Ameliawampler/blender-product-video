"""Example mascot: a little owl, 8-bit voxel version: built from 1 cm painted wood cubes (about 12 x 16 cm).
Front faces -Y. pose: 'perch' or 'spread'."""
import bpy, bmesh, math
from mathutils import Matrix
import build as B

V = 0.01  # voxel size, metres

def _mats():
    g = bpy.data.materials.get
    def painted(name, hexcol, rough=0.6, coat=0.0):
        return g(name) or B.simple(name, B.srgb(hexcol), rough, coat=coat)
    return [painted("Owl forest", "#06140D"), painted("Owl wing", "#123024"), painted("Owl paper", "#D9D4C4", 0.6),
            painted("Owl marigold", "#C06A08", 0.5), g("Owl eye glass") or B.simple("Owl eye glass", (0.004, 0.004, 0.004, 1), 0.04, coat=1.0),
            painted("Owl mint", "#1F7F5C", 0.25)]
FOREST, WING, PAPER, MARI, BLACK, MINT = range(6)

def voxels(pose):
    vox = {}
    inside = lambda x, y, z: ((x + 0.5) / 6.0) ** 2 + ((y - 4) / 4.6) ** 2 + ((z - 7.5) / 8.2) ** 2 <= 1.0
    for x in range(-6, 6):
        for y in range(0, 9):
            for z in range(0, 15):
                if inside(x, y, z): vox[(x, y, z)] = FOREST
    for (x, y, z) in list(vox):                      # wings: outer side columns
        if (x <= -5 or x >= 4) and 3 <= z <= 10: vox[(x, y, z)] = WING
    front = {}
    for (x, y, z) in vox:
        if (x, z) not in front or y < front[(x, z)]: front[(x, z)] = y
    for (x, z), y in front.items():                  # face and belly are painted on the front-most voxels
        if -3 <= x <= 2 and 2 <= z <= 7: vox[(x, y, z)] = WING if (z <= 4 and (x + z) % 2 == 0) else PAPER
        if z in (10, 11, 12) and (-4 <= x <= -2 or 1 <= x <= 3): vox[(x, y, z)] = PAPER
        if z in (10, 11) and x in (-3, 2): vox[(x, y, z)] = BLACK
    for z, xs in ((15, (-5, -4, 3, 4)), (16, (-5, 4))):   # ear tufts
        for x in xs:
            for y in (3, 4): vox[(x, y, z)] = FOREST
    fy = front.get((-1, 9), 0)
    for z in (9, 8): vox[(-1, fy - 1, z)] = MARI; vox[(0, fy - 1, z)] = MARI   # beak
    vox.pop((0, fy - 1, 8)); vox[(-1, fy - 1, 8)] = MARI
    for x in (-3, -2, 1, 2):                          # feet
        for y in (1, 2, 3):
            for z in (-1, -2): vox[(x, y, z)] = MARI
    if pose == "spread":
        for i in range(1, 8):
            for sx in (-1, 1):
                x = (-6 - i) if sx < 0 else (5 + i)
                for y in (3, 4, 5):
                    for z in range(8 + i // 2, 12 + i // 2 - (i // 3)): vox[(x, y, z)] = WING if i < 6 else FOREST
    return vox

def build_owl(loc, rot_z=0.0, pose="perch"):
    for o in list(bpy.data.objects):
        if o.name.startswith("Owl"): bpy.data.objects.remove(o, do_unlink=True)
    me = bpy.data.meshes.new("Owl voxels"); bm = bmesh.new()
    for (x, y, z), m in voxels(pose).items():
        r = bmesh.ops.create_cube(bm, size=V * 0.93, matrix=Matrix.Translation(((x + 0.5) * V, (y - 4.0) * V, (z + 2.5) * V)))
        for f in {f for v in r["verts"] for f in v.link_faces}: f.material_index = m
    bm.to_mesh(me); bm.free()
    o = bpy.data.objects.new("Owl", me); bpy.context.scene.collection.objects.link(o)
    for m in _mats(): me.materials.append(m)
    bv = o.modifiers.new("Bevel", "BEVEL"); bv.width = V * 0.06; bv.segments = 2
    o.location = loc; o.rotation_euler = (0, 0, math.radians(rot_z)); o.scale = (1.3, 1.3, 1.3)
    return o
