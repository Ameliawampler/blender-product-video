"""Film definition (example: "The Gate"): shots, cameras, and per-frame animation. One clock: seconds.
Rendering is split in two passes that share cameras:
  plates  the photoreal set (grass, gate, sky), one still per shot        -> python film.py plates
  layers  everything that moves (blocks, owl, gate swing) on transparent  -> python film.py layers
comp.py puts them together, adds camera drift, text and the 2D ending."""
import sys, os, math, random
sys.path.insert(0, os.path.dirname(__file__))
import bpy
from mathutils import Vector
import build as B, mascot as O

FPS = 24; STEP = 2            # layers are animated on twos (12 fps), like stop motion
Z0 = B.hill_z(0, 0); POST = (1.62, 0.0, Z0 + 1.425)
H = lambda x, y, h: (x, y, B.hill_z(x, y) + h)
ROOT = os.environ.get("FILM_OUT", B.ROOT)
TEST = bool(os.environ.get("TEST"))

def px_open(y): return 0.3
def px_ctrl(y):
    k = max(0.0, 1 - abs(y + 1.0) / 6.0); k = k * k * (3 - 2 * k); return 0.5 + 0.72 * k

SIDE = ((2.5, -4.4, Z0 + 1.05), (1.15, -0.3, Z0 + 0.88), 40, 4.0)
#  id: dur, mood, gate, cam, look, lens, fstop, focus
SHOTS = {
 "A": (7,  "golden",   96, H(2.6, -15, 1.5), (0.3, 0, Z0 + 1.0), 40, 8.0, (0.3, 0, Z0 + 1)),
 "B": (5,  "golden",   96, SIDE[0], SIDE[1], SIDE[2], SIDE[3], POST),
 "C": (12, "overcast", 96, H(3.5, -6.4, 0.8), (0.1, -1.2, Z0 + 0.55), 35, 5.6, (0.2, -1.5, Z0 + 0.5)),
 "E": (6,  "overcast", 96, H(0.9, -7.5, 0.32), (0.3, 0, Z0 + 0.7), 24, 2.8, H(0.3, -4.2, 0.3)),
 "F": (6,  "golden",   96, (0.3, -5.6, Z0 + 0.9), (0.5, 0, Z0 + 0.8), 32, 5.6, POST),
 "G": (10, "golden",   40, SIDE[0], SIDE[1], SIDE[2], SIDE[3], POST),
 "H": (5,  "golden",   40, H(2.0, -17, 1.7), (0.6, 0, Z0 + 1.4), 32, 8.0, (0.6, 0, Z0 + 1)),
}
ORDER = ["A", "B", "C", "E", "F", "G", "H"]
LOOP = {"A": 24, "B": 48, "H": 24}   # these shots loop: render only this many film frames

def camera(sid):
    dur, mood, gate, cf, look, lens, fs, focus = SHOTS[sid]; sc = bpy.context.scene
    cam = bpy.data.objects.get("Cam")
    if not cam:
        cam = bpy.data.objects.new("Cam", bpy.data.cameras.new("Cam")); sc.collection.objects.link(cam)
    cam.location = cf; cam.rotation_euler = (Vector(look) - Vector(cf)).to_track_quat("-Z", "Y").to_euler()
    cam.data.lens = lens; cam.data.dof.use_dof = True; cam.data.dof.aperture_fstop = fs
    cam.data.dof.focus_distance = (Vector(focus) - Vector(cf)).length; sc.camera = cam

def leaf(): return [o for o in bpy.data.objects if o.parent and o.parent.name == "Gate hinge"]
def gate_parts(): return [o for o in bpy.data.objects if o.name.startswith(("Post", "Rail", "Stile", "Hinge", "Latch"))]

# ---------- motion helpers ----------
def roll(o, x, y, s, dist, yaw=0.0):
    th = (dist / s) * (math.pi / 2); h = (s / math.sqrt(2)) * math.cos((th % (math.pi / 2)) - math.pi / 4)
    o.location = (x, y, B.hill_z(x, y) + h + 0.004); o.rotation_euler = (-th, 0, yaw)

def set_kind(o, kind):
    if o.get("kind") != kind: o.data.materials[0] = B.block_mat(kind); o["kind"] = kind

def mk(kind, s, coll):
    o = B.block((0, 0, -50), kind, s=s, coll=coll); o["kind"] = kind; o["s"] = s; return o

def gate_angle(t):
    if t < 2.0: return 96.0
    if t < 2.8: k = (t - 2.0) / 0.8; return 96.0 * (1 - k * k)
    u = t - 2.8; return -3.0 * math.exp(-u * 6) * math.cos(u * 20)

class Shot:
    def __init__(self, sid):
        self.sid = sid; self.r = random.Random(11); self.c = B.new_coll("Usage stream"); self.owl_state = None
        getattr(self, "setup_" + sid)()
    def owl(self, pose, rot):
        if self.owl_state != (pose, rot): O.build_owl(POST, rot, pose); self.owl_state = (pose, rot)
    def look(self, t, base=-25): return base + (-18, 0, 14, -6)[int(t / 1.3) % 4]
    def update(self, t): getattr(self, "update_" + self.sid)(t)
    # --- uniform line (A, B)
    def setup_A(self): self.bl = [mk("paper", 0.14, self.c) for _ in range(42)]
    def update_A(self, t):
        for i, o in enumerate(self.bl):
            d = i * 0.84 + 0.84 * t; y = -26 + (d % 35.28); roll(o, 0.3, y, 0.14, d)
        self.owl("perch", -25 + (-16 if int(t) % 2 == 0 else 10))
    setup_B = setup_A
    update_B = update_A
    # --- variable (C)
    def setup_C(self):
        r = self.r; self.items = []; kinds = ["mint", "paper", "mauve", "marigold", "paper", "mint"]
        for x, v in ((-1.25, 1.1), (-0.8, 0.7), (1.05, 1.4), (1.4, 0.85)):
            y = -30.0
            while y < 6:
                n = r.choice([1, 1, 1, 3, 6]); 
                for _ in range(n):
                    s = min(0.42, max(0.045, r.lognormvariate(-2.1, 0.7))); y += s * 0.6 + 0.03
                    self.items.append((mk(r.choice(kinds), s, self.c), x + r.uniform(-0.05, 0.05), y, v, s)); y += s * 0.6
                y += r.choice([0.3, 1.0, 2.4, 4.0])
        for y0, s, k in ((-8.6, 1.1, "mauve"), (-12.5, 0.55, "marigold"), (-4.0, 0.3, "mint"), (-16, 0.7, "mint"), (-20, 0.2, "paper")):
            self.items.append((mk(k, s, self.c), 0.15, y0, 0.45, s))
    def update_C(self, t):
        for o, x, y0, v, s in self.items:
            d = y0 + 30 + v * t; roll(o, x, -30 + (d % 38), s, d, 0.0)
        self.owl("perch", self.look(t, -40))
    # --- swarm (E)
    def setup_E(self):
        r = self.r; self.items = []
        for i in range(60 if TEST else 300):
            k = "alarm" if r.random() < 0.62 else r.choice(["marigold", "paper", "mauve"]); s = r.uniform(0.09, 0.16)
            self.items.append((mk(k, s, self.c), r.gauss(0, 0.9), r.uniform(0, 36), r.uniform(3.0, 5.2), s, r.uniform(0, 6.28), r.uniform(4, 9), r.uniform(0.05, 0.45), [r.uniform(-4, 4) for _ in range(3)]))
    def update_E(self, t):
        for o, x0, y0, v, s, ph, f, amp, w in self.items:
            y = -24 + ((y0 + v * t) % 36); x = 0.2 + max(-1.3, min(1.1, x0)) * min(1.6, 0.55 + abs(y) / 7)
            o.location = (x, y, B.hill_z(x, y) + s / 2 + abs(math.sin(t * f + ph)) * amp); o.rotation_euler = (w[0] * t, w[1] * t, w[2] * t)
        self.owl("perch", self.look(t, -30))
    # --- gate shuts, pile (F)
    def setup_F(self):
        r = self.r; self.early = [(mk("alarm" if i % 3 else "marigold", r.uniform(0.1, 0.15), self.c), r.uniform(-0.9, 1.1), i, [r.uniform(-4, 4) for _ in range(3)], r.uniform(0, 6)) for i in range(30)]
        slots = [(-1.25 + c * 0.165 + r.uniform(-0.02, 0.02), -0.32 - k * 0.165, 0) for k in range(7) for c in range(17)]
        slots += [(-1.1 + c * 0.17, -0.36 - k * 0.17, 1) for k in range(3) for c in range(15)]
        slots.sort(key=lambda s: (s[2], -s[1] + r.uniform(0, 0.2)))
        n = 30 if TEST else len(slots)
        self.pile = [(mk("alarm" if r.random() < 0.65 else "marigold", 0.145, self.c), sx, sy, lay, 3.05 + i * 0.011 + lay * 0.3, r.uniform(0, 6), r.uniform(-0.25, 0.25)) for i, (sx, sy, lay) in enumerate(slots[:n])]
    def update_F(self, t):
        B.set_gate(gate_angle(t))
        for o, x, i, w, ph in self.early:
            y = -0.5 - i * 0.3 + 5 * t; s = o["s"]
            o.location = (x, y, B.hill_z(x, y) + s / 2 + abs(math.sin(t * 7 + ph)) * 0.3); o.rotation_euler = (w[0] * t, w[1] * t, w[2] * t)
        for o, sx, sy, lay, ta, ph, yaw in self.pile:
            if t >= ta: o.location = (sx, sy, B.hill_z(sx, sy) + 0.075 + lay * 0.147); o.rotation_euler = (0, 0, yaw)
            else:
                y = sy - 6.0 * (ta - t); x = sx + (ta - t) * 0.15 * math.sin(ph)
                o.location = (x, y, B.hill_z(x, y) + 0.08 + lay * 0.147 + abs(math.sin(t * 8 + ph)) * 0.35); o.rotation_euler = (t * 5 + ph, t * 3, ph)
        self.owl("spread" if t >= 1.3 else "perch", -20 if t >= 1.3 else self.look(t, -30))
    # --- controlled (G)
    def setup_G(self):
        self.line = [(mk("paper", 0.14, self.c), j, 0.14) for j in (0, 1, 3)] + [(mk("marigold", 0.38, self.c), 2, 0.38)]
        self.ahead = [(mk("mint", 0.14, self.c), j) for j in range(1, 9)]
        self.red = [(mk("alarm", 0.14, self.c), k, self.r.uniform(-0.25, 0.25), self.r.uniform(0, 6)) for k in range(12)]
    def update_G(self, t):
        for o, j, s in self.line:
            y = -1.5 - j * 1.15 + 0.8 * t; d = 0.8 * t + j * 0.3
            roll(o, px_ctrl(y), y, s, d)
            if s < 0.2: set_kind(o, "mint" if y > -0.25 else "paper")
        for o, j in self.ahead:
            y = -1.5 + j * 1.15 + 0.8 * t; roll(o, px_ctrl(y), y, 0.14, 0.8 * t)
        for o, k, yaw, ph in self.red:
            stop = -0.45 - (k // 3) * 0.18; x = 0.95 + (k % 3) * 0.18 - (k // 3) * 0.04; ta = 7.2 + k * 0.05
            if t >= ta: o.location = (x, stop, B.hill_z(x, stop) + 0.075); o.rotation_euler = (0, 0, yaw)
            else:
                y = stop - 3.2 * (ta - t); o.location = (x, y, B.hill_z(x, y) + 0.08 + abs(math.sin(t * 8 + ph)) * 0.25); o.rotation_euler = (t * 5, t * 3 + ph, 0)
        self.owl("spread" if t >= 6.6 else "perch", -55 if t >= 6.6 else self.look(t, -45))
    # --- orderly wide (H)
    def setup_H(self): self.bl = [mk("paper", 0.14, self.c) for _ in range(42)]
    def update_H(self, t):
        for i, o in enumerate(self.bl):
            d = i * 0.84 + 0.84 * t; y = -26 + (d % 35.28); roll(o, px_ctrl(y), y, 0.14, d); set_kind(o, "mint" if y > -0.25 else "paper")
        self.owl("perch", -20)

def base_scene(w, h, samples):
    B.clear(); B.setup_render(w, h, samples); B.build_hill(); B.build_gate()

def plates():
    out = os.path.join(ROOT, "plates"); os.makedirs(out, exist_ok=True)
    base_scene(*((480, 270, 8) if TEST else (1280, 720, 36)))
    jobs = [(s, SHOTS[s][1], "") for s in ORDER] + [("F", "overcast", "_overcast")]
    for sid, mood, suf in jobs:
        fp = os.path.join(out, f"{sid}{suf}.png")
        if os.path.exists(fp): continue
        B.build_world(mood); B.set_gate(SHOTS[sid][2]); camera(sid)
        for o in leaf(): o.hide_render = (sid == "F")
        bpy.context.scene.render.filepath = fp; bpy.ops.render.render(write_still=True); print("plate", sid, suf, flush=True)

def layers():
    out = os.path.join(ROOT, "layers"); os.makedirs(out, exist_ok=True)
    os.environ["GRASS_NEAR"] = "10"; os.environ["GRASS_MID"] = "10"
    base_scene(*((480, 270, 6) if TEST else (768, 432, 7)))
    sc = bpy.context.scene; sc.render.film_transparent = True; sc.render.image_settings.color_mode = "RGBA"
    hill = bpy.data.objects["Hill"]; hill.is_shadow_catcher = True
    for m in hill.modifiers: m.show_render = False
    bpy.data.objects["Far landscape"].hide_render = True
    for sid in ORDER:
        dur, mood = SHOTS[sid][0], SHOTS[sid][1]
        B.build_world(mood); bpy.data.objects["Sky plate"].visible_camera = False
        B.set_gate(SHOTS[sid][2]); camera(sid)
        lf = set(leaf())
        for o in gate_parts(): o.is_holdout = not (sid == "F" and o in lf)
        sh = Shot(sid)
        frames = [int(dur * FPS * 0.62) // STEP * STEP] if TEST else range(0, LOOP.get(sid, dur * FPS), STEP)
        for f in frames:
            fp = os.path.join(out, f"{sid}_{f:04d}.png")
            if os.path.exists(fp): continue
            sh.update(f / FPS); sc.render.filepath = fp; bpy.ops.render.render(write_still=True)
        print("layers", sid, flush=True)

if __name__ == "__main__":
    {"plates": plates, "layers": layers}[sys.argv[-1]]()
