# Ideas backlog

Every idea and owner decision that is not built yet. Status: **decided** (the owner wants it; needs a
change record), **research** (test before designing), **later** (wanted, not now), **documented**
(written down for the future, not planned), **built** (with its change record).

## Built

| Idea | Change |
|---|---|
| Variations of one world (several styles); look guide; must / never lists; pose library; object packs; whole-world runs | [0005](../changes/0005-world-variations.md) |
| Approval modes (automatic / approve the base / each step); hero casting from different readings; issue presets for "Generate again"; stronger-judge options; desktop notifications; clean-up | [0006](../changes/0006-approvals-and-options.md) |
| Prompts keep what they are for; a judge told what was asked; project files | [0004](../changes/0004-robust-generation.md) |

## Decided: next designs

**Fix the six root causes** of the v2 world ([root-causes-2026-10-03.md](root-causes-2026-10-03.md)):
the shortened outfit, object details, reference roles in compositions, who the person is in edits, views
per kind of object, the belonging's checks in actions.

**Elements: everything permanent, designed first.** Clothing, jewellery, armour, permanent marks
(scars, tattoos) become records of their own, each designed and approved before the images that use
it: kind, where it sits (right upper arm, left cheek, waist), when it shows (always, or only with an
outfit), its own small image set (hero and close-up), its own states (damaged, removed, bloodied). An
outfit becomes a set of elements instead of one long sentence. Elements travel to the model as
reference images (the armlet's close-up as image 2), not as words. The character page gets sections
for clothing, jewellery and marks next to belongings.

**States for belongings and objects.** A broken bow, an unstrung bow, a bloodied mace, Rakhsh saddled
or bare, wounded; drawn from the object's approved hero, and usable in scenes ("the broken bow").

**Places as rich datasets.** Many views (wide, reverse, each anchor, details, high and low), and
states: time of day, weather (storm, snow, fog), lighting (candles lit or out, torches), damage. Every
image tagged with view and state, so that a project-specific model can be trained later. A place page
showing all of it, like a character page. A floor plan with camera positions (decided earlier).

**Character parameters.** Measurable facts beside the prose: height, build or weight, beard length
(none / stubble / short / chin / chest), hair length and colour, skin tone, eye colour, age. Each is
marked **prompt**, **judge** or **both**. A parameter has a short token (2–4 words) and a priority per
kind of image; the judge gets all of them; some are measured (pose keypoints, face landmarks, colour).

**The prompt budget rule.** Not everything goes into the prompt: the reference image carries what is
visible, elements go as reference images, parameters as short tokens chosen per kind of image, the judge
gets everything, measured checks need no words.

**Measured checks.** Pose keypoints (rtmlib), near-duplicate views (imagehash), same object or place
(DINOv2), same face (facenet-pytorch), mark and jewellery position (face landmarks). See
[tools-and-libraries.md](tools-and-libraries.md).

**Weapon and action poses** from the mannequin library (drawing a bow, swinging a mace, riding).

**Warnings for features models cannot keep** (built for small face marks in 0005): extend to sides
(left / right), tiny jewellery, patterns.

## Research first

- **3D references:** TripoSR object views; 3D-rendered mannequins sized from the character's
  parameters; animal turnarounds.
- **Multiple references:** when do the models do better with two or three references (turnaround views
  as extra references for actions and scenes)? Needs extensive testing before planning.
- **Place views:** SEVA, depth reprojection, panorama cut-outs.
- **Pose and depth control:** Qwen-Image ControlNet Union; FLUX.2 klein depth through the reference
  slot.
- **Prompt length:** FLUX.2 klein at 100 / 150 / 200 words.
- **Story to scenes:** best practices and existing skills before any design (decided as next feature).
- **Lighting for places:** daylight instead of neutral studio light as the default (open decision).
- **Object side views:** the side-view camera wording mentions "the face, chest and both feet" and is
  also used for objects (open decision).

## Later

- **Continuity supervisor:** a per-scene ledger of what each character wears, carries and has suffered;
  each new shot compared with the previous scene of the same character.
- **Production exports:** layered PSD / Krita files, sprite sheets, Blender reference planes, character
  parts for 2D rigs; vtracer SVGs for the 2D variation.
- **Static review package:** one HTML file of a variation or scene list that a reviewer annotates
  offline; comments come back as notes and approvals.
- **Transparent cut-outs:** an option to test (not at generation time).
- **Grouping work by model** as an option, never the default (reference images first); documented in
  0006.
- **Final pass** (upscale and refine every accepted image not yet upscaled), a world-level action the
  person starts when ready; needs an upscaler in hone-models; documented in 0006.
- **A character or project model (LoRA)** trained from approved packs and place datasets: wanted; 8 GB
  is below the documented minimum for FLUX.2 klein, so a rented GPU or memory tricks.
- **Story to animatic:** shots, keyframes, short clips from start and end frames, an animatic with
  timing; not part of the current design.

## Documented only

- **A model router that learns from results:** pass rates, picks and rejection reasons per model and
  kind of image decide which model to use; with hone-taste (taste from picks) and hone-lens
  (analytics). Not to be used for now.
- **Provenance and a commercial-safe filter:** hone-models knows each model's license; each image
  records its model; a world could show what is safe for commercial use and export a provenance report
  (optionally C2PA content credentials).
