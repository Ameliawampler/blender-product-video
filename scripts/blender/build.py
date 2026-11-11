"""
Set builder, photoreal pass (Blender 5.x, bpy). Example set: a field gate on a grassy hill.

Everything is generated in code. Units are metres; the gate stands on the crest of the hill at
the origin, +Y runs up and over the hill away from camera.

  hill      main hill (dense hair grass near the crest, sparser mid grass) on top of a 3 km
            rolling landscape so there is never an edge; aerial haze is baked into the shaders
  gate      aged five-bar field gate, galvanized hinge straps and latch
  blocks    the moving props: frosted acrylic cubes in the palette from film.json
  sky       physical sky + sun for light, a photographic sky plate on a 900 m cylinder for looks

Run headless:  blender -b -P build.py   (or `python build.py` with the bpy wheel)
In Blender Web (Puter): Scripting tab, open this file, Run.
"""
import bpy, bmesh, math, random, os, json
from mathutils import Vector

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
CFG = json.load(open(os.environ.get("FILM_CONFIG", os.path.join(ROOT, "film.json"))))
ASSETS = os.environ.get("FILM_ASSETS", os.path.join(ROOT, "assets"))
RNG = random.Random(7)

def srgb(h):
    h = h.lstrip("#"); c = [int(h[i:i+2], 16) / 255 for i in (0, 2, 4)]
    return tuple(((x + 0.055) / 1.055) ** 2.4 if x > 0.04045 else x / 12.92 for x in c) + (1.0,)
FOREST, MINT, MARIGOLD, MAUVE, PAPER, ALARM = (srgb(CFG["palette"][k]) for k in ("primary", "accent", "warm", "soft", "paper", "alarm"))
HAZE = {"golden": srgb("#D9C3A2"), "overcast": srgb("#AEB8BC")}
STATE = {"mood": "golden"}

def clear():
    bpy.ops.wm.read_factory_settings(use_empty=True)

def nodes(m):
    m.use_nodes = True; return m.node_tree.nodes, m.node_tree.links

# ---------- haze: mix every outdoor surface toward the sky colour with camera distance ----------
def haze_group():
    g = bpy.data.node_groups.get("Haze")
    if g: return g
    g = bpy.data.node_groups.new("Haze", "ShaderNodeTree")
    g.interface.new_socket("Shader", in_out="INPUT", socket_type="NodeSocketShader")
    g.interface.new_socket("Shader", in_out="OUTPUT", socket_type="NodeSocketShader")
    n, l = g.nodes, g.links
    gi = n.new("NodeGroupInput"); go = n.new("NodeGroupOutput")
    cam = n.new("ShaderNodeCameraData"); mr = n.new("ShaderNodeMapRange")
    mr.inputs["From Min"].default_value = 60; mr.inputs["From Max"].default_value = 1400
    mr.inputs["To Max"].default_value = 0.42; mr.interpolation_type = "SMOOTHSTEP"
    em = n.new("ShaderNodeEmission"); em.name = "HazeColor"; em.inputs["Strength"].default_value = 1.0
    mix = n.new("ShaderNodeMixShader")
    l.new(cam.outputs["View Distance"], mr.inputs["Value"]); l.new(mr.outputs["Result"], mix.inputs["Fac"])
    l.new(gi.outputs[0], mix.inputs[1]); l.new(em.outputs["Emission"], mix.inputs[2]); l.new(mix.outputs["Shader"], go.inputs[0])
    return g

def set_haze(mood):
    g = haze_group(); e = g.nodes["HazeColor"]
    e.inputs["Color"].default_value = HAZE[mood]; e.inputs["Strength"].default_value = 0.72 if mood == "golden" else 0.8

def with_haze(m):
    n, l = m.node_tree.nodes, m.node_tree.links
    out = next(x for x in n if x.type == "OUTPUT_MATERIAL"); src = out.inputs["Surface"].links[0].from_socket
    grp = n.new("ShaderNodeGroup"); grp.node_tree = haze_group()
    l.new(src, grp.inputs[0]); l.new(grp.outputs[0], out.inputs["Surface"])
    return m

# ---------- terrain ----------
def hill_z(x, y):
    crest = 4.2 * math.exp(-((x / 46) ** 2 + (y / 15) ** 2))
    bumps = 0.18 * math.sin(x * 0.21) * math.cos(y * 0.17) + 0.08 * math.sin(x * 0.53 + y * 0.31)
    return crest + bumps

def far_z(x, y):
    r = math.hypot(x, y); w = min(1.0, max(0.0, (r - 170) / 500)); w = w * w * (3 - 2 * w)
    rolls = 9 * (math.sin(x * 0.006 + 1.3) * math.cos(y * 0.0045) + 0.6 * math.sin(x * 0.013 - y * 0.009 + 0.7)) + 4
    return -0.06 + w * max(0.0, rolls) + (1 - w) * (0.18 * math.sin(x * 0.21) * math.cos(y * 0.17))

def ground_mat(name):
    m = bpy.data.materials.new(name); n, l = nodes(m); b = n["Principled BSDF"]
    tc = n.new("ShaderNodeTexCoord")
    big = n.new("ShaderNodeTexNoise"); big.inputs["Scale"].default_value = 0.06; big.inputs["Detail"].default_value = 6
    small = n.new("ShaderNodeTexNoise"); small.inputs["Scale"].default_value = 3.5; small.inputs["Detail"].default_value = 10
    l.new(tc.outputs["Object"], big.inputs["Vector"]); l.new(tc.outputs["Object"], small.inputs["Vector"])
    ramp = n.new("ShaderNodeValToRGB"); e = ramp.color_ramp.elements
    e[0].position, e[0].color = 0.32, srgb("#2B3E22"); e[1].position, e[1].color = 0.72, srgb("#6C7F45")
    e.new(0.52).color = srgb("#46602F")
    mixv = n.new("ShaderNodeMix"); mixv.data_type = "FLOAT"; mixv.inputs["Factor"].default_value = 0.35
    l.new(big.outputs["Fac"], mixv.inputs["A"]); l.new(small.outputs["Fac"], mixv.inputs["B"]); l.new(mixv.outputs["Result"], ramp.inputs["Fac"])
    l.new(ramp.outputs["Color"], b.inputs["Base Color"]); b.inputs["Roughness"].default_value = 0.96
    bump = n.new("ShaderNodeBump"); bump.inputs["Strength"].default_value = 0.6; l.new(small.outputs["Fac"], bump.inputs["Height"]); l.new(bump.outputs["Normal"], b.inputs["Normal"])
    return with_haze(m)

def grass_mat():
    m = bpy.data.materials.new("Grass blades"); n, l = nodes(m); b = n["Principled BSDF"]
    hi = n.new("ShaderNodeHairInfo")
    ramp = n.new("ShaderNodeValToRGB"); e = ramp.color_ramp.elements
    e[0].position, e[0].color = 0.0, srgb("#253D1C"); e[1].position, e[1].color = 1.0, srgb("#8A8A4C")
    e.new(0.45).color = srgb("#3F5C28"); e.new(0.8).color = srgb("#66743A")
    l.new(hi.outputs["Random"], ramp.inputs["Fac"])
    l.new(ramp.outputs["Color"], b.inputs["Base Color"]); b.inputs["Roughness"].default_value = 0.55
    b.inputs["Specular IOR Level"].default_value = 0.35
    tr = n.new("ShaderNodeBsdfTranslucent"); l.new(ramp.outputs["Color"], tr.inputs["Color"])
    mix = n.new("ShaderNodeMixShader"); mix.inputs["Fac"].default_value = 0.14
    out = n["Material Output"]; l.new(b.outputs["BSDF"], mix.inputs[1]); l.new(tr.outputs["BSDF"], mix.inputs[2]); l.new(mix.outputs["Shader"], out.inputs["Surface"])
    return with_haze(m)

def hair(obj, name, group, count, length, children, mat_index):
    ps = obj.modifiers.new(name, "PARTICLE_SYSTEM").particle_system; s = ps.settings
    s.type = "HAIR"; s.count = count; s.hair_length = length; s.use_advanced_hair = True
    s.child_type = "INTERPOLATED" if children else "NONE"
    if children: s.child_percent = children; s.rendered_child_count = children
    s.clump_factor = 0.08; s.roughness_endpoint = 0.0; s.roughness_1 = 0.008; s.length_random = 0.6
    s.root_radius = 1.0; s.tip_radius = 0.0; s.radius_scale = 0.0028
    s.brownian_factor = 0.0; s.factor_random = 0.025; s.normal_factor = 1.0; s.tangent_factor = 0.0
    s.material = mat_index; ps.vertex_group_density = group
    s.hair_length = length  # last: normal_factor resets the length
    return ps

def build_hill():
    bpy.ops.mesh.primitive_grid_add(x_subdivisions=300, y_subdivisions=240, size=1)
    g = bpy.context.object; g.name = "Hill"; g.scale = (300, 240, 1); bpy.ops.object.transform_apply(scale=True)
    for v in g.data.vertices: v.co.z = hill_z(v.co.x, v.co.y)
    for p in g.data.polygons: p.use_smooth = True
    g.data.materials.append(ground_mat("Ground near")); g.data.materials.append(grass_mat())
    near = g.vertex_groups.new(name="near"); mid = g.vertex_groups.new(name="mid")
    for v in g.data.vertices:
        d = math.hypot(v.co.x / 20, (v.co.y + 5) / 15)
        if d < 1: near.add([v.index], (1 - d) ** 0.4, "REPLACE")
        d2 = math.hypot(v.co.x / 70, (v.co.y + 10) / 40)
        if d2 < 1: mid.add([v.index], min(1.0, (1 - d2) * 1.6), "REPLACE")
    hair(g, "Grass near", "near", int(os.environ.get("GRASS_NEAR", "170000")), 0.30, 7, 2)
    hair(g, "Grass mid", "mid", int(os.environ.get("GRASS_MID", "160000")), 0.32, 0, 2)
    bpy.ops.mesh.primitive_grid_add(x_subdivisions=160, y_subdivisions=160, size=1)
    f = bpy.context.object; f.name = "Far landscape"; f.scale = (3200, 3200, 1); bpy.ops.object.transform_apply(scale=True)
    for v in f.data.vertices: v.co.z = far_z(v.co.x, v.co.y)
    for p in f.data.polygons: p.use_smooth = True
    f.data.materials.append(ground_mat("Ground far"))
    return g

# ---------- gate ----------
def wood_mat():
    m = bpy.data.materials.new("Aged oak"); n, l = nodes(m); b = n["Principled BSDF"]
    tc = n.new("ShaderNodeTexCoord"); mp = n.new("ShaderNodeMapping"); mp.inputs["Scale"].default_value = (0.6, 14.0, 14.0)
    l.new(tc.outputs["Object"], mp.inputs["Vector"])
    grain = n.new("ShaderNodeTexWave"); grain.wave_type = "BANDS"; grain.bands_direction = "X"
    grain.inputs["Scale"].default_value = 1.4; grain.inputs["Distortion"].default_value = 18; grain.inputs["Detail"].default_value = 6
    l.new(mp.outputs["Vector"], grain.inputs["Vector"])
    nz = n.new("ShaderNodeTexNoise"); nz.inputs["Scale"].default_value = 14; nz.inputs["Detail"].default_value = 12; l.new(tc.outputs["Object"], nz.inputs["Vector"])
    ramp = n.new("ShaderNodeValToRGB"); e = ramp.color_ramp.elements
    e[0].color = srgb("#3E372F"); e[1].color = srgb("#8C8272"); e.new(0.55).color = srgb("#655C50")
    mx = n.new("ShaderNodeMix"); mx.data_type = "FLOAT"; mx.inputs["Factor"].default_value = 0.4
    l.new(grain.outputs["Fac"], mx.inputs["A"]); l.new(nz.outputs["Fac"], mx.inputs["B"]); l.new(mx.outputs["Result"], ramp.inputs["Fac"])
    lich = n.new("ShaderNodeTexNoise"); lich.inputs["Scale"].default_value = 3.0; lich.inputs["Detail"].default_value = 8; l.new(tc.outputs["Object"], lich.inputs["Vector"])
    lr = n.new("ShaderNodeMapRange"); lr.inputs["From Min"].default_value = 0.6; lr.inputs["From Max"].default_value = 0.68; l.new(lich.outputs["Fac"], lr.inputs["Value"])
    lm = n.new("ShaderNodeMix"); lm.data_type = "RGBA"; lm.inputs["B"].default_value = srgb("#A7AE88")
    l.new(lr.outputs["Result"], lm.inputs["Factor"]); l.new(ramp.outputs["Color"], lm.inputs["A"])
    geo = n.new("ShaderNodeNewGeometry"); sep = n.new("ShaderNodeSeparateXYZ"); l.new(geo.outputs["Position"], sep.inputs["Vector"])
    dr = n.new("ShaderNodeMapRange"); dr.inputs["From Min"].default_value = hill_z(0, 0) + 0.45; dr.inputs["From Max"].default_value = hill_z(0, 0) - 0.1
    l.new(sep.outputs["Z"], dr.inputs["Value"])
    dm = n.new("ShaderNodeMix"); dm.data_type = "RGBA"; dm.blend_type = "MULTIPLY"; dm.inputs["B"].default_value = srgb("#5A5348")
    l.new(dr.outputs["Result"], dm.inputs["Factor"]); l.new(lm.outputs["Result"], dm.inputs["A"])
    l.new(dm.outputs["Result"], b.inputs["Base Color"])
    rr = n.new("ShaderNodeMapRange"); rr.inputs["To Min"].default_value = 0.7; rr.inputs["To Max"].default_value = 0.95; l.new(nz.outputs["Fac"], rr.inputs["Value"]); l.new(rr.outputs["Result"], b.inputs["Roughness"])
    bump = n.new("ShaderNodeBump"); bump.inputs["Strength"].default_value = 0.55; bump.inputs["Distance"].default_value = 0.004
    l.new(mx.outputs["Result"], bump.inputs["Height"]); l.new(bump.outputs["Normal"], b.inputs["Normal"])
    return with_haze(m)

def steel_mat():
    m = bpy.data.materials.new("Galvanized steel"); n, l = nodes(m); b = n["Principled BSDF"]
    nz = n.new("ShaderNodeTexNoise"); nz.inputs["Scale"].default_value = 40
    ramp = n.new("ShaderNodeValToRGB"); ramp.color_ramp.elements[0].color = srgb("#5E6265"); ramp.color_ramp.elements[1].color = srgb("#8B8F91")
    l.new(nz.outputs["Fac"], ramp.inputs["Fac"]); l.new(ramp.outputs["Color"], b.inputs["Base Color"])
    b.inputs["Metallic"].default_value = 1.0; b.inputs["Roughness"].default_value = 0.42
    return m

def simple(name, color, rough=0.5, coat=0.0, metal=0.0):
    m = bpy.data.materials.new(name); n, l = nodes(m); b = n["Principled BSDF"]
    b.inputs["Base Color"].default_value = color; b.inputs["Roughness"].default_value = rough; b.inputs["Metallic"].default_value = metal
    if coat: b.inputs["Coat Weight"].default_value = coat
    return m

def box(name, size, loc, material, parent=None, bevel=0.008, rot=None):
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc)
    o = bpy.context.object; o.name = name; o.scale = size; bpy.ops.object.transform_apply(scale=True)
    if rot: o.rotation_euler = rot
    if bevel:
        bm = o.modifiers.new("Bevel", "BEVEL"); bm.width = bevel; bm.segments = 3
    o.data.materials.append(material)
    if parent:
        o.parent = parent; o.matrix_parent_inverse = parent.matrix_world.inverted()
    return o

def build_gate():
    z0 = hill_z(0, 0); wood = wood_mat(); steel = steel_mat()
    box("Post · hinge", (0.17, 0.17, 1.75), (-1.62, 0, z0 + 0.52), wood, bevel=0.012)
    box("Post · latch", (0.17, 0.17, 1.75), (1.62, 0, z0 + 0.52), wood, bevel=0.012)
    for x in (-1.62, 1.62):
        box("Post cap", (0.19, 0.19, 0.03), (x, 0, z0 + 1.41), wood, bevel=0.006)
    hinge = bpy.data.objects.new("Gate hinge", None); bpy.context.collection.objects.link(hinge)
    hinge.location = (-1.52, 0, z0); bpy.context.view_layer.update()
    w = 3.0
    for i, h in enumerate((0.18, 0.42, 0.66, 0.90, 1.14)):
        box(f"Rail {i+1}", (w, 0.065, 0.095 if i else 0.11), (-1.52 + w / 2, 0, z0 + h), wood, hinge)
    for x in (0.05, w - 0.05, w * 0.5):
        box("Stile", (0.095, 0.08, 1.07), (-1.52 + x, 0, z0 + 0.66), wood, hinge)
    for h in (0.42, 1.14):
        box("Hinge strap", (0.62, 0.075, 0.05), (-1.52 + 0.3, 0, z0 + h), steel, hinge, 0.004)
        box("Hinge pin", (0.05, 0.05, 0.14), (-1.58, 0, z0 + h), steel, None, 0.004)
    box("Latch bar", (0.34, 0.03, 0.04), (1.42, -0.06, z0 + 0.9), steel, hinge, 0.004)
    box("Latch keeper", (0.06, 0.09, 0.12), (1.62, -0.07, z0 + 0.9), steel, None, 0.004)
    # (no logo on the gate in v3)
    return hinge

def set_gate(open_deg):
    bpy.data.objects["Gate hinge"].rotation_euler.z = math.radians(-open_deg)

# ---------- usage blocks ----------
BLOCK_MATS = {}
def block_mat(kind):
    if kind in BLOCK_MATS: return BLOCK_MATS[kind]
    col = {"mint": MINT, "marigold": MARIGOLD, "mauve": MAUVE, "paper": PAPER, "alarm": ALARM, "forest": FOREST}[kind]
    m = bpy.data.materials.new("Acrylic · " + kind); n, l = nodes(m); b = n["Principled BSDF"]
    b.inputs["Base Color"].default_value = col; b.inputs["IOR"].default_value = 1.49
    b.inputs["Roughness"].default_value = 0.2 if kind != "paper" else 0.3
    b.inputs["Transmission Weight"].default_value = 0.0 if kind == "paper" else 0.92
    b.inputs["Subsurface Weight"].default_value = 0.6 if kind == "paper" else 0.0
    b.inputs["Coat Weight"].default_value = 0.4; b.inputs["Coat Roughness"].default_value = 0.08
    if kind == "alarm":
        b.inputs["Emission Color"].default_value = col; b.inputs["Emission Strength"].default_value = 0.25
    BLOCK_MATS[kind] = m; return m

def new_coll(name):
    c = bpy.data.collections.get(name)
    if c:
        for o in list(c.objects): bpy.data.objects.remove(o, do_unlink=True)
    else:
        c = bpy.data.collections.new(name); bpy.context.scene.collection.children.link(c)
    return c

def block(loc, kind="mint", s=0.14, rot=(0, 0, 0), coll=None, vel=None):
    bpy.ops.mesh.primitive_cube_add(size=s, location=loc)
    o = bpy.context.object; o.name = "Usage block · " + kind
    bv = o.modifiers.new("Bevel", "BEVEL"); bv.width = s * 0.12; bv.segments = 4
    o.rotation_euler = rot; o.data.materials.append(block_mat(kind))
    if coll:
        for c in o.users_collection: c.objects.unlink(o)
        coll.objects.link(o)
    if vel:  # two keys one frame apart so the still frame carries real motion blur
        o.keyframe_insert("location", frame=1); o.location = Vector(loc) + Vector(vel); o.keyframe_insert("location", frame=2)
    return o

def rr(): return (RNG.uniform(0, 6.28), RNG.uniform(0, 6.28), RNG.uniform(0, 6.28))

def stream(mode):
    """trickle (open gate), swarm (attack), orderly (one at a time), blocked (physics pile at the shut gate)."""
    c = new_coll("Usage stream"); kinds = ["mint", "paper", "mauve", "mint", "paper", "marigold"]
    if mode == "trickle":
        for i in range(60):
            y = -24 + i * 0.75 + RNG.uniform(-0.3, 0.3); x = RNG.uniform(-1.0, 1.0) + 0.35 * math.sin(y * 0.2)
            block((x, y, hill_z(x, y) + 0.08), RNG.choice(kinds), rot=(0, 0, RNG.uniform(0, 1.5)), coll=c)
    elif mode == "swarm":
        for i in range(700):
            y = RNG.uniform(-20, 8); spread = 1.2 + max(0, -y) * 0.1; x = RNG.gauss(0, spread * 0.5)
            z = hill_z(x, y) + 0.08 + abs(RNG.gauss(0, 0.3)) + max(0, 1.1 - abs(y) * 0.18) * RNG.random()
            k = "alarm" if RNG.random() < 0.6 else RNG.choice(["marigold", "paper", "mauve"])
            block((x, y, z), k, s=RNG.uniform(0.09, 0.15), rot=rr(), coll=c, vel=(RNG.gauss(0, 0.02), RNG.uniform(0.18, 0.32), RNG.gauss(0, 0.04)))
    elif mode == "orderly":
        for i in range(30):
            y = -15 + i * 0.62; k = "mint" if y > 0.4 else ("marigold" if i % 5 == 0 else "paper")
            block((0.0, y, hill_z(0, y) + 0.072), k, rot=(0, 0, 0), coll=c)
    elif mode == "blocked":
        pile(c)
    return c

def pile(c, n=220, frames=90):
    """Real rigid-body pile: blocks thrown at the shut gate, simulated, frozen on the last frame."""
    sc = bpy.context.scene
    if not sc.rigidbody_world: bpy.ops.rigidbody.world_add()
    rw = sc.rigidbody_world; rw.point_cache.frame_start = 1; rw.point_cache.frame_end = frames
    z0 = hill_z(0, 0); colliders = []
    bpy.ops.mesh.primitive_grid_add(x_subdivisions=28, y_subdivisions=24, size=1, location=(0, -5, 0))
    gp = bpy.context.object; gp.name = "Collider · ground"; gp.scale = (14, 12, 1); bpy.ops.object.transform_apply(scale=True, location=True)
    for v in gp.data.vertices: v.co.z = hill_z(v.co.x, v.co.y)
    colliders.append((gp, "MESH"))
    bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, z0 + 0.65)); gb = bpy.context.object; gb.name = "Collider · gate"
    gb.scale = (3.3, 0.12, 1.3); bpy.ops.object.transform_apply(scale=True); colliders.append((gb, "BOX"))
    for o, shape in colliders:
        bpy.ops.object.select_all(action="DESELECT"); bpy.context.view_layer.objects.active = o; o.select_set(True); bpy.ops.rigidbody.object_add()
        o.rigid_body.type = "PASSIVE"; o.rigid_body.collision_shape = shape; o.rigid_body.friction = 0.8
        o.hide_render = True
    for i in range(n):
        x = RNG.uniform(-1.4, 1.4); y = RNG.uniform(-6.5, -1.4); z = hill_z(x, y) + 0.25 + RNG.random() * 1.8
        o = block((x, y, z), "alarm" if RNG.random() < 0.6 else "marigold", s=RNG.uniform(0.11, 0.15), rot=rr(), coll=c)
        bpy.ops.object.select_all(action="DESELECT"); bpy.context.view_layer.objects.active = o; o.select_set(True); bpy.ops.rigidbody.object_add()
        o.rigid_body.mass = 0.3; o.rigid_body.friction = 0.6; o.rigid_body.restitution = 0.15; o.rigid_body.collision_shape = "BOX"
    for f in range(1, frames + 1): sc.frame_set(f)
    for i in range(10):
        y = 0.7 + i * 0.68; block((0, y, hill_z(0, y) + 0.072), "mint", coll=c)
    return frames

# ---------- sky ----------
def sky_cylinder():
    """900 m cylinder carrying the sky plate as 4 mirrored 90° panels; +Y looks at the middle of a panel."""
    bd = bpy.data.objects.get("Sky plate")
    if bd: return bd
    R, Z0, Z1, SEG = 900.0, -40.0, 1070.0, 128
    me = bpy.data.meshes.new("Sky plate"); bm = bmesh.new(); uv = bm.loops.layers.uv.new()
    r0, r1 = [], []
    for i in range(SEG + 1):
        a = -math.pi * 0.75 + 2 * math.pi * i / SEG
        r0.append(bm.verts.new((R * math.sin(a), R * math.cos(a), Z0))); r1.append(bm.verts.new((R * math.sin(a), R * math.cos(a), Z1)))
    q = SEG // 4
    for i in range(SEG):
        k = i // q; f0 = (i % q) / q; f1 = (i % q + 1) / q
        u0, u1 = (f0, f1) if k % 2 == 0 else (1 - f0, 1 - f1)
        f = bm.faces.new((r0[i], r0[i + 1], r1[i + 1], r1[i]))
        for loop, uvv in zip(f.loops, ((u0, 0), (u1, 0), (u1, 1), (u0, 1))): loop[uv].uv = uvv
    bm.normal_update(); bm.to_mesh(me); bm.free()
    bd = bpy.data.objects.new("Sky plate", me); bpy.context.scene.collection.objects.link(bd)
    m = bpy.data.materials.new("Sky plate"); n, l = nodes(m); n.clear()
    tex = n.new("ShaderNodeTexImage"); tex.name = "Plate"; tex.extension = "EXTEND"
    em = n.new("ShaderNodeEmission"); em.name = "Emission"; out = n.new("ShaderNodeOutputMaterial")
    l.new(tex.outputs["Color"], em.inputs["Color"]); l.new(em.outputs["Emission"], out.inputs["Surface"])
    bd.data.materials.append(m)
    bd.visible_shadow = False; bd.visible_diffuse = False
    return bd

def build_world(mood="golden"):
    STATE["mood"] = mood; set_haze(mood); sc = bpy.context.scene
    w = bpy.data.worlds.get("World") or bpy.data.worlds.new("World"); sc.world = w; w.use_nodes = True
    n, l = w.node_tree.nodes, w.node_tree.links; n.clear()
    sky = n.new("ShaderNodeTexSky"); bg = n.new("ShaderNodeBackground"); out = n.new("ShaderNodeOutputWorld")
    elev = 11 if mood == "golden" else 34; rot = 208 if mood == "golden" else 160
    sky.sun_elevation = math.radians(elev); sky.sun_rotation = math.radians(rot)
    for attr, val in (("air_density", 1.0 if mood == "golden" else 1.6), ("aerosol_density", 1.6 if mood == "golden" else 3.0)):
        if hasattr(sky, attr): setattr(sky, attr, val)
    bg.inputs["Strength"].default_value = 0.30 if mood == "golden" else 0.42
    l.new(sky.outputs["Color"], bg.inputs["Color"]); l.new(bg.outputs["Background"], out.inputs["Surface"])
    sun = bpy.data.objects.get("Sun")
    if not sun:
        sun = bpy.data.objects.new("Sun", bpy.data.lights.new("Sun", "SUN")); sc.collection.objects.link(sun)
    sun.data.angle = math.radians(2.0 if mood == "golden" else 9.0)
    sun.data.energy = 4.2 if mood == "golden" else 1.3
    sun.data.color = (1.0, 0.80, 0.58) if mood == "golden" else (0.88, 0.93, 1.0)
    sun.rotation_euler = (math.radians(90 - elev), 0, math.radians(rot))
    bd = sky_cylinder(); m = bd.data.materials[0]
    m.node_tree.nodes["Plate"].image = bpy.data.images.load(os.path.join(ASSETS, "sky-golden.png" if mood == "golden" else "sky-overcast.png"), check_existing=True)
    m.node_tree.nodes["Emission"].inputs["Strength"].default_value = 0.7 if mood == "golden" else 0.9

def setup_render(w=1280, h=720, samples=64):
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"; sc.cycles.device = "CPU"
    sc.cycles.samples = samples; sc.cycles.use_adaptive_sampling = True; sc.cycles.adaptive_threshold = 0.025
    sc.cycles.use_denoising = True
    sc.cycles.max_bounces = 8; sc.cycles.diffuse_bounces = 3; sc.cycles.glossy_bounces = 4; sc.cycles.transmission_bounces = 8
    sc.cycles.caustics_reflective = False; sc.cycles.caustics_refractive = False; sc.cycles.blur_glossy = 1.0
    sc.render.resolution_x, sc.render.resolution_y = w, h
    sc.render.use_motion_blur = False; sc.render.motion_blur_shutter = 0.5
    sc.view_settings.view_transform = "AgX"
    for look in ("AgX - Base Contrast", "AgX - Medium High Contrast", "Medium High Contrast"):
        try: sc.view_settings.look = look; break
        except Exception: pass
    sc.view_settings.exposure = 0.0
    sc.render.fps = 24

def build_all():
    clear(); setup_render(); build_hill(); build_gate(); build_world("golden")

if __name__ == "__main__":
    build_all()
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(os.path.dirname(__file__), "..", "..", "scene.blend"))
