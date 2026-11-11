"""Compositor. Plates + moving layers + 2D camera drift + text overlays + the 2D block ending.
python comp.py out.mp4 [--only-ending] [--draft]   (pipes frames to ffmpeg)"""
import sys, os, math, subprocess, json
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter
REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")); ROOT = os.environ.get("FILM_OUT", REPO); W, H, FPS = 1280, 720, 24
CFG = json.load(open(os.environ.get("FILM_CONFIG", os.path.join(REPO, "film.json")))); PAL = CFG["palette"]
SHOTS = [("A", 7), ("B", 5), ("C", 12), ("E", 6), ("F", 6), ("G", 10), ("H", 5)]
LOOP = {"A": 24, "B": 48, "H": 24}
ease = lambda p: (lambda p: p * p * (3 - 2 * p))(min(1.0, max(0.0, p)))
# 2D camera: (zoom0, zoom1, cx, cy) ; C and G punch in part-way
def move(sid, t, dur):
    p = t / dur
    if sid == "A": return 1.0 + 0.07 * p, 0.42, 0.40
    if sid == "B": return 1.10 + 0.08 * p, 0.60, 0.42
    if sid == "C": return (1.0 + 0.05 * p, 0.5, 0.5) if t < 6.5 else (1.2 + 0.08 * p, 0.38, 0.55)
    if sid == "E": return 1.0 + 0.08 * p, 0.5, 0.5
    if sid == "F": return 1.0 + 0.10 * ease(p), 0.55, 0.5
    if sid == "G": return 1.06 + 0.08 * p, 0.56, 0.5
    return 1.08 - 0.08 * ease(p), 0.5, 0.45
TEXT = [tuple(o) for o in CFG["overlays"]]  # (start, end, text[, x fraction]) in film seconds
def _font():
    for p in (CFG.get("font"), "/usr/share/fonts/opentype/inter/Inter-SemiBold.otf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "/System/Library/Fonts/Helvetica.ttc", "C:/Windows/Fonts/arialbd.ttf"):
        if p and os.path.exists(p): return ImageFont.truetype(p, 54)
    raise SystemExit('Set "font" in film.json to a .ttf or .otf file for the text overlays')
FONT = _font()
_tc = {}
def text_img(s, xf=0.5):
    if s in _tc: return _tc[s]
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    d.multiline_text((W * xf, 150), s, font=FONT, fill=(0, 0, 0, 150), anchor="mm", align="center", spacing=14)
    im = im.filter(ImageFilter.GaussianBlur(9)); d = ImageDraw.Draw(im)
    d.multiline_text((W * xf, 148), s, font=FONT, fill=(255, 255, 255, 255), anchor="mm", align="center", spacing=14)
    _tc[s] = np.asarray(im).astype(np.float32) / 255; return _tc[s]
def grade(a):  # tame the orange sky, keep it warm
    w = np.clip((a[..., 0] - a[..., 2] - 0.18) / 0.4, 0, 1)[..., None]; lum = (a @ np.array([0.2126, 0.7152, 0.0722], np.float32))[..., None]
    a = lum + (a - lum) * (1 - 0.38 * w); return a * (1 - 0.06 * w) + np.array([0.0, 0.012, 0.03], np.float32) * w
_pl, _ly = {}, {}
def plate(name):
    if name not in _pl: _pl[name] = grade(np.asarray(Image.open(os.path.join(ROOT, "plates", name + ".png")).convert("RGB").resize((W, H), Image.LANCZOS)).astype(np.float32) / 255)
    return _pl[name]
def layer(sid, f):
    key = (sid, f)
    if key not in _ly:
        fp = os.path.join(ROOT, "layers", f"{sid}_{f:04d}.png")
        if len(_ly) > 60: _ly.clear()
        _ly[key] = np.asarray(Image.open(fp).convert("RGBA").resize((W, H), Image.BICUBIC)).astype(np.float32) / 255 if os.path.exists(fp) else None
    return _ly[key]
yy, xx = np.mgrid[0:H, 0:W]; VIG = (1 - 0.2 * np.clip(np.sqrt(((xx - W / 2) / (W / 2)) ** 2 + ((yy - H / 2) / (H / 2)) ** 2) - 0.4, 0, 1) ** 1.6)[..., None].astype(np.float32)
RNG = np.random.default_rng(5)
def finish(a, T):
    for s, e, txt, *xf in TEXT:
        if s <= T <= e:
            k = min(1, (T - s) / 0.35, (e - T) / 0.35); ti = text_img(txt, *xf); al = ti[..., 3:] * k; a = a * (1 - al) + ti[..., :3] * al
    a = a * VIG + RNG.normal(0, 0.011, (H, W, 1)).astype(np.float32)
    if T < 0.6: a = a * (T / 0.6)
    return a
def film_frame(n):
    T = n / FPS; t0 = 0
    for sid, dur in SHOTS:
        if T < t0 + dur: break
        t0 += dur
    t = T - t0; f = int(round(t * FPS))
    lf = (f % LOOP[sid]) // 2 * 2 if sid in LOOP else f // 2 * 2
    bg = plate(sid)
    if sid == "F":
        k = ease((t - 2.8) / 1.6); bg = plate("F_overcast") * (1 - k) + bg * k
    L = layer(sid, lf); a = bg
    if L is not None:
        rgb = grade(L[..., :3]); 
        if sid == "F": k2 = ease((t - 2.8) / 1.6); rgb = rgb * (np.array([0.80, 0.86, 0.95], np.float32) * (1 - k2) + k2)
        a = bg * (1 - L[..., 3:]) + rgb * L[..., 3:]
    z, cx, cy = move(sid, t, dur); cw, ch = W / z, H / z; x0 = min(max(cx * W - cw / 2, 0), W - cw); y0 = min(max(cy * H - ch / 2, 0), H - ch)
    im = Image.fromarray((np.clip(a, 0, 1) * 255).astype(np.uint8)).resize((W, H), Image.BICUBIC, box=(x0, y0, x0 + cw, y0 + ch))
    return finish(np.asarray(im).astype(np.float32) / 255, T), im

# ---------------- ending: 2D blocks ----------------
PALH = [PAL[k] for k in ("primary", "accent", "paper", "warm", "soft", "primary", "accent", "deep", "paper", "primary")]
hx = lambda h: tuple(int(h[i:i + 2], 16) for i in (1, 3, 5)); PAPER = hx(PAL["paper"])
def rnd(i, j): x = math.sin(i * 127.1 + j * 311.7) * 43758.5453; return x - math.floor(x)
FNT = {"C": "011100100100011", "H": "101101111101101", "J": "001001001101010", "N": "110101101101101", "Q": "010101101110011", "W": "101101111111101", "X": "101101010101101", "Z": "111001010100111", "0": "111101101101111", "1": "010110010010111", "2": "110001010100111", "3": "110001010001110", "4": "101101111001001", "5": "111100110001110", "6": "011100111101111", "7": "111001010010010", "8": "111101111101111", "9": "111101111001110", "-": "000000111000000", "/": "001001010100100", "!": "010010010000010", "A": "010101111101101", "B": "110101110101110", "D": "110101101101110", "E": "111100110100111", "F": "111100110100100", "G": "011100101101011", "I": "111010010010111", "K": "101101110101101", "L": "100100100100111", "M": "101111111101101", "O": "111101101101111", "P": "110101110100100", "R": "110101110101101", "S": "011100010001110", "T": "111010010010010", "U": "101101101101111", "V": "101101101101010", "Y": "101101010010010", ".": "000000000000010", " ": "0" * 15}
COLS, ROWS = 64, 36; TXT = {}
for s, r0, col in ((e["text"].upper(), e["row"], PAL.get(e["color"], e["color"])) for e in CFG["ending"]):
    assert len(s) <= 12 and all(ch in FNT for ch in s), f"ending line {s!r}: max 12 characters from {sorted(FNT)}"
    c0 = (COLS - (len(s) * 4 - 1)) // 2
    for i, ch in enumerate(s):
        for y in range(5):
            for x in range(3):
                if FNT[ch][y * 3 + x] == "1": TXT[(c0 + i * 4 + x, r0 + y)] = hx(col)
orig = lambda c, r: hx(PALH[int(rnd(c + 7, r + 3) * len(PALH))])
fin = lambda c, r: TXT.get((c, r)) or (PAPER if (8 <= c <= 55 and 2 <= r <= 33) else orig(c, r))
S0 = W / 6.0; S1 = W / 64.0; SS = 2
def ending_frame(te, last):
    Wb, Hb = W * SS, H * SS
    if te < 2.1: S = S0
    else: S = S0 * (S1 / S0) ** ease((te - 2.1) / 3.0)
    bgk = ease((te - 0.7) / 0.8)
    im = Image.blend(last, Image.new("RGB", (W, H), PAPER), bgk).resize((Wb, Hb), Image.BILINEAR); d = ImageDraw.Draw(im)
    c0 = max(0, int(32 - W / 2 / S) - 1); c1 = min(COLS, int(32 + W / 2 / S) + 2); r0 = max(0, int(18 - H / 2 / S) - 1); r1 = min(ROWS, int(18 + H / 2 / S) + 2)
    g = S * 0.06; rad = S * 0.11
    for r in range(r0, r1):
        for c in range(c0, c1):
            col = orig(c, r); x = W / 2 + (c - 32) * S; y = H / 2 + (r - 18) * S; hs = 1.0
            if te >= 5.1:
                p = (te - 5.1 - (c + r % 3) * 0.038) / 0.32; f = fin(c, r)
                if f != col:
                    if p >= 1: col = f
                    elif p > 0: hs = abs(math.cos(math.pi * p)); col = f if p > 0.5 else col
            if col == PAPER: continue
            if te < 1.7:   # fly in from the gate, tumbling
                st = rnd(c, r) * 0.85; p = ease((te - st) / 0.75)
                if p <= 0: continue
                if p < 1:
                    sx, sy = W * 0.5 + (rnd(r, c) - 0.5) * 80, H * 0.42; cxp = sx + (x + S / 2 - sx) * p; cyp = sy + (y + S / 2 - sy) * p - math.sin(p * math.pi) * 60
                    hsz = (S / 2 - g) * (0.04 + 0.96 * p * p); ang = (1 - p) * (rnd(c + 3, r) - 0.5) * 3.0
                    pts = [((cxp + (dx * math.cos(ang) - dy * math.sin(ang)) * hsz) * SS, (cyp + (dx * math.sin(ang) + dy * math.cos(ang)) * hsz) * SS) for dx, dy in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
                    sh = [(px + 10 * SS * p, py + 14 * SS * p) for px, py in pts]
                    d.polygon(sh, fill=tuple(int(v * 0.55) for v in PAPER) if bgk > 0.5 else (20, 30, 24)); d.polygon(pts, fill=col); continue
            hh = (S - 2 * g) * hs
            d.rounded_rectangle(((x + g) * SS, (y + S / 2 - hh / 2) * SS, (x + S - g) * SS, (y + S / 2 + hh / 2) * SS), radius=min(rad, hh / 2) * SS, fill=col)
    return np.asarray(im.resize((W, H), Image.LANCZOS)).astype(np.float32) / 255
END_DUR = 12.5

if __name__ == "__main__":
    out = sys.argv[1]; only_end = "--only-ending" in sys.argv; draft = "--draft" in sys.argv
    ff = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p", "-movflags", "+faststart", out], stdin=subprocess.PIPE)
    nfilm = sum(d for _, d in SHOTS) * FPS; last = None; step = 6 if draft else 1
    if not only_end:
        for n in range(0, nfilm, step):
            a, last = film_frame(n); ff.stdin.write((np.clip(a, 0, 1) * 255).astype(np.uint8).tobytes())
    else: _, last = film_frame(nfilm - 1)
    for k in range(0, int(END_DUR * FPS), step):
        a = ending_frame(k / FPS, last); ff.stdin.write((np.clip(a, 0, 1) * 255).astype(np.uint8).tobytes())
    ff.stdin.close(); ff.wait(); print("wrote", out)
