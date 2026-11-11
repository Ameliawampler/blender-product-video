---
name: blender-product-video
description: Make a silent, text-led product film where a photoreal Blender set carries a visual metaphor and a 2D block-grid ending spells out the headline and call to action. Use when someone wants a launch video, product explainer or short brand film rendered from code with Blender (bpy), Python and ffmpeg, especially on a machine with no GPU.
---

# Blender product video

A method and a working example for a 45 to 75 second product film that reads with the sound off.
A photoreal set (grass, a wooden gate, a real sky) carries one visual metaphor. Short text overlays
say what the pictures can't. The film ends by turning into a flat grid of colored blocks that flip
to spell the headline and call to action.

Everything is code: the set, the animation, the compositing. Nothing is opened in a GUI.

## What's in this folder

| Path | What it is |
| --- | --- |
| `film.json` | Palette, overlay text with timings, ending lines. Edit this first. |
| `scripts/blender/build.py` | The set: hill with hair-particle grass, gate, frosted blocks, sky, haze, render settings. |
| `scripts/blender/mascot.py` | Example character: a voxel owl small enough to sit on a fencepost. |
| `scripts/blender/film.py` | Shots, cameras, per-frame animation. Renders `plates` and `layers`. |
| `scripts/post/comp.py` | Compositor: plates + layers, 2D camera moves, text, grade, the 2D block ending, ffmpeg encode. |
| `assets/` | Two sky plates (golden, overcast). Replace with your own. |
| `examples/` | Frames from a film made with this pipeline. |

The example film is "The Gate": identical blocks roll through an open gate at a steady pace, then
arrive in every size, then swarm. The gate shuts, and after that blocks are let through, counted or
stopped. Treat it as a reference for structure, then replace the metaphor with one that fits the
product.

## Workflow

Do these in order. Get sign-off at each numbered step before spending render time on the next.

1. **Brief.** One sentence each: who it's for, the problem, the turn, the promise, the call to
   action. Decide length (45 to 75 s), aspect and where it will play. Assume muted playback.
2. **Metaphor.** Pick one physical picture for the problem and one change to that picture for the
   product. One place, one main prop, one kind of moving object. If it needs explaining, pick again.
3. **Beat sheet.** 6 to 8 shots. For each: duration, what moves, the overlay line (under 8 words,
   one idea), camera position and lens. Problem act in cool overcast light, product act in warm
   light. Show it as a table and get approval.
4. **Character (optional).** A small protagonist gives the eye somewhere to rest. Offer 3 or 4
   options as flat sketches before modeling anything. Size it against the set: it should fit on the
   main prop. Build it from simple primitives (the owl is 1 cm cubes).
5. **Set in code.** Adapt `build.py`. Keep units in metres with the main prop at the origin.
   Render one still per shot at low samples and look at every one before animating.
6. **Animation.** In `film.py`, each shot has `setup_X` (create objects once) and `update_X(t)`
   (place everything for film second `t`). Pure functions of time, no keyframes, so any frame can be
   rendered alone and a crashed render resumes where it stopped.
7. **Two-pass render.** `python scripts/blender/film.py plates`, then `... layers`. See below.
8. **Composite.** `python scripts/post/comp.py out.mp4 --draft` for a fast check (every 6th
   frame), then without `--draft`. Use `--only-ending` while tuning the ending.
9. **Watch it.** Pull stills at each overlay's midpoint and check: is the text readable, is the
   thing the text names visible in frame, does anything pop between shots. Fix and re-render only
   the affected shot (delete its files in `layers/`).

## The two-pass render

Photoreal grass is slow. Moving objects are cheap. So they are rendered apart.

- **Plates.** One still per shot of the full set (grass, prop, sky), 1280x720 at 36 samples in the
  example. A shot that changes light gets two plates that the compositor cross-fades.
- **Layers.** Only what moves, on a transparent background, at lower resolution and samples. The
  ground is a shadow catcher so objects still cast shadows. Static props are holdouts so objects
  pass behind them correctly. The sky stays in for lighting but is hidden from camera.
- **Compositor.** Lays the layer over the plate, then fakes camera movement with a slow 2D push or
  drift per shot. A locked 3D camera is what makes the plate reusable.

Three things keep the cost down:

- **Loops.** If a shot is a steady stream, make the motion periodic (spacing 0.84 m at 0.84 m/s
  repeats every second) and render one period. `LOOP` in `film.py` and `comp.py` lists these shots.
- **On twos.** Layers are rendered every second frame (`STEP = 2`) and held. It reads as stop
  motion, which suits small blocky objects.
- **Resume.** Every frame is skipped if its file exists.

For scale: the example film (51 s of 3D plus a 12.5 s ending) is 8 plates and 456 layer frames. It
rendered on CPU only.

## The 2D ending

`comp.py` draws it directly, no Blender. A 64x36 grid of rounded squares in the palette flies in
over the last 3D frame at 6 columns wide, the camera pulls back until all 64 columns show, then a
diagonal wave flips each block (a vertical squash to zero and back, with the color swap at the
midpoint) to its final color. Final colors come from a 3x5 pixel font, so the blocks become the
text.

Limits to plan copy around: up to four lines, 12 characters each (11 looks better), capitals,
digits and `. - / !`. Set them in `film.json` under `ending` with a grid row and a palette key.

## Editing `film.json`

- `palette`: seven hex colors. `primary`, `accent`, `warm`, `soft`, `deep`, `paper` (background of
  the ending and the default block), `alarm` (the "something is wrong" color).
- `overlays`: `[start, end, "text", x]` in film seconds. `x` is optional, a 0 to 1 horizontal
  position for when the subject sits where centered text would cover it. Use `\n` for two lines.
- `ending`: the lines the blocks spell.
- `font`: path to a .ttf or .otf for overlays. Falls back to Inter, DejaVu, Helvetica or Arial.

Shot durations live in `SHOTS` at the top of both `film.py` and `comp.py`. Keep them equal.

## Setup

```
python -m venv venv && . venv/bin/activate
pip install bpy==5.3.0 numpy pillow     # bpy is the Blender wheel; needs the matching Python
# ffmpeg must be on PATH

TEST=1 python scripts/blender/film.py plates    # 480x270, one frame per shot, a few minutes
TEST=1 python scripts/blender/film.py layers
python scripts/post/comp.py draft.mp4 --draft
```

`FILM_OUT=/some/dir` writes `plates/` and `layers/` there instead of into this folder. `FILM_CONFIG`
points at a different `film.json`. `GRASS_NEAR` and `GRASS_MID` (percent) thin the grass.
With desktop Blender instead of the wheel: `blender -b -P scripts/blender/film.py -- plates`.

## Pitfalls that cost real time

- **Grass length.** Setting a hair particle system's `normal_factor` resets `hair_length`. Set
  `hair_length` last or every strand is metres long and the field looks motion-blurred.
- **Parenting.** Parenting moves the child unless you set `matrix_parent_inverse`. Hinged parts
  will jump off the prop.
- **Sky.** A sky image on a UV cylinder stretches. Use mirrored panels on a large cylinder, or a
  flat plane if the camera never pans. Keep a physical sun for the actual light.
- **Text over the subject.** Check every overlay against the frame under it. Move the text with
  `x` before moving the camera.
- **Punch-ins hide things.** If an overlay names something ("Blocked."), confirm the 2D crop still
  contains it.
- **Color washout.** Painted surfaces under AgX need darker base colors than the brand hex. Screens
  and anything that must read as an exact color should be emission.
- **No GPU.** Budget by frame: time one layer frame, multiply, then cut resolution, samples or shot
  length until it fits. Don't start a render you haven't timed.
- **Container restarts.** Long renders get interrupted. The skip-if-exists check is what saves you.

## What this pipeline doesn't do

Be straight with the person about these before they expect them.

- Moving 3D cameras. Shots are locked off with 2D moves on top. Real parallax means rendering the
  set every frame, which needs a GPU.
- Motion blur and 24 fps motion on layers. Raise samples, set `STEP = 1` and turn on
  `render.use_motion_blur` when hardware allows.
- Objects sit on top of the grass, not in it, because the grass is in the plate.
- Sound. The film is built to work silent. Add music and effects afterwards if wanted.
- Screens, UI or logos in the 3D world. Deliberately left out: product UI in a photoreal field
  reads as fake. Put product visuals in the 2D ending or a separate cut.

## For a final-quality pass

1920x1080 or higher for both passes, 128+ samples with denoising, GPU rendering (OptiX or Metal),
`STEP = 1`, motion blur on, and `W, H` in `comp.py` raised to match. Split frames across machines
by frame number; every frame is independent.
