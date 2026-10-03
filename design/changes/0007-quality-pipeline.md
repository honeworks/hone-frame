# 0007: The quality pipeline (experimental)

## Status

`proposed` 2026-10-04: **experimental, on branch `exp/quality-pipeline`, never to be merged.** The
owner asked for "the best version using the libraries we found" so they can compare it with `main`
before deciding what to keep. It is built, then measured on a full world (Zahhak, realistic epic), and
reported; what survives the owner's review becomes normal change records later.

Validated 2026-10-04 by an independent review (an agent with no access to the owner's discussion,
reading only the repository). It found six blockers in the first draft (no per-output model routing;
Qwen turning views would get the default "front view" camera phrase; hone-models drops a command's
`meta`; the action check named the wrong image; required parameter checks would make passes rare; worn
elements would get "holds and uses" actions) and a scope of several days. This version takes its
proposed edits: **scope for one day: §1 (A–F), §2 reduced, §3 reduced, §5 reduced, §6 (duplicates
required, the model checks advisory), §7, §8, §9; §4 and the place page deferred.**

## Context

The first two-variation world showed six root causes (design/research/root-causes-2026-10-03.md):
A the shortened outfit breaks garments; B an object's own details never reach the prompt; C the look
guide pushes the reference roles out of compositions; D edits never say who the person is; E one view
list for every object; F the judge does not check the belonging in actions and is lenient. The owner
also decided (design/research/ideas-backlog.md): permanent elements designed first (clothing,
jewellery, marks), states for belongings and objects, places as rich datasets with views and states,
character parameters used by prompts and the judge, measured checks, weapon and action poses.

Measured on this machine before writing this (2026-10-04):

- **ViTPose** (`usyd-community/vitpose-base-simple`, Apache-2.0, through `transformers`): 17 body
  keypoints on CPU in about 0.06 s per image after loading; it reads kneeling, running and sitting
  apart (hip-to-knee and knee-to-ankle ratios differ clearly between a standing and a seated figure).
- **DINOv2 small** (Apache-2.0, already downloaded): image embeddings on CPU in well under a second.
- **Qwen-Image-Edit 2511** with the Multiple-Angles LoRA (the `final` profile's editor) turns an
  object for real (a true side profile of the ox-head mace) where FLUX.2 klein returned near-copies; about
  2 minutes per image against FLUX's 30 s. A top view from a three-quarter hero did not work either way.
- **Not available:** the PyPI file host is unreachable from this machine today, so packages that are not
  already installed (TripoSR's dependencies, rtmlib, onnxruntime, opencv, facenet-pytorch, imagehash)
  cannot be installed. The design uses only what is present: ComfyUI's Python environment (torch,
  transformers, numpy, scipy, Pillow) and hone-frame's own. TripoSR and face identity stay in the
  research notes.

## Decision

### 1. The root-cause fixes

**A. Garments instead of comma-split prose.** A character's outfit may be given as a list of garments,
each `{name, details}` ("tiger-skin coat" / "a coat made from a whole tiger's skin, striped orange and
black, worn over the lamellar coat"). Prompts that must be short list the garment **names**; long ones
use the details. In `view` mode `keep` lists garment **names**; in `generate` mode `outfit` uses the
details. Without garments, `keep` always carries the outfit text whole (compact mode no longer changes
it). `short_outfit` is removed; a prompt over budget is sent long with a `prompt_long` event. The file
key is `garments = [{name, details}]` on a character; `outfit` stays as the fallback.

**B. Objects described by their own fields.** The subject section of an object (`asset`) uses its
description, then `details`, `materials`, `colours` and `scale`, in that order of importance; a place
uses `anchors` and `materials`. Each field is a short phrase in the files the owner writes.

**C. Reference roles are never cut.** `roles` moves from `DROP_FIRST` to `REQUIRED`. In `compose` mode the look
guide is left out when every subject in the picture has a reference image (the references carry the
look); it stays for subjects drawn from words only.

**D. Who the person is, in every edit.** A short identity line ("a young woman of about twenty, long
dark-brown hair"; "a man in his fifties, a thick dark beard reaching the chest") is built from the
character's parameters (section 2). It is a new required section `identity`, placed after `view` in
`view` mode, after `subject` in `generate` mode, and once per character after `roles` in `compose` mode
(the Gordafarid "he" drift happened in an action), in every shipped dialect.

**E. Views by kind of object.** An object has a `shape`: `figure` (an animal: front, three-quarter,
side, back, like a character's turnaround, no top view), `long` (a weapon or staff: full length from
the side, head-on, a close-up of the head, a close-up of the grip), `flat` (a bow, a shield, a banner:
face-on, edge-on, a close-up of the distinctive detail), `soft` (a lasso, a cloth: laid out, hanging, a
close-up), `round` (a vessel, a helmet: front, side, from above, a close-up). The view lists are data
(`data/object_packs.toml`, as `[shapes.<shape>]` with the same item format as `packs.views`; an object
without `shape` keeps today's list). Each item may carry `azimuth`, `elevation` and `distance` in the
Multiple-Angles vocabulary (azimuths: front, front-right quarter, right side, back-right quarter, back,
back-left quarter, left side, front-left quarter; elevations: low-angle, eye-level, elevated,
high-angle; distances: close-up, medium, wide), which fill `camera_values` (so the Qwen camera phrase
is never the default "front view"), and `editor = "turn"` for views that need the object to turn. There
is no top view: "from above" is `high-angle shot`. Turning items of one subject run together.

**F. Actions check the belonging.** The existing `object` check of `interaction-plausibility` asks "Is
the object the one in image 3, the object reference: the same shape, head and colours?" (in the judge
prompt the candidate is image 1 and the character image 2); the belonging's `must` and `never` become
required checks (the action's subjects include the belonging). Actions and scenes skip the planner (the
composed draft is used), because its rewrites dropped the reference roles.

### 2. Character parameters

A character gets `parameters` beside the prose (the prose key `build` stays free text; the enum is
`body`): `sex`, `age`, `body` (`slight` / `lean` / `average` / `athletic` / `heavy` / `massive`),
`hair_length`, `hair_colour`, `beard` (`none` / `stubble` / `short` / `chin` / `chest`), and `marks`, a
list of `{what, where, size}` for permanent marks (two serpents growing from the shoulders, a scar on
the left cheek). Tokens are templates in `data/parameters.toml` (`beard.chest = "a full beard reaching
the chest"`; free values are used as written). The token choice by kind of image: close-up
(`camera_values.distance == "close-up"`): sex, age, hair, beard, face marks; full figure
(`full_body`): sex, age, body, hair, beard, marks; back (`faces_away`): sex, age, body, hair, marks on
the back and shoulders. The judge gets the **same view-filtered list** as one required check
`parameters`, where a parameter the view cannot show counts as a pass (`not_assessable` allowed);
marks visible in the view are one more required check `marks`.

### 3. Elements: worn things are objects too (reduced)

A worn element (an armlet, a crown) is an owned object with `worn = true` and `worn_on` ("his head",
"his right upper arm"). It gets its object hero and one close-up like a belonging, is **excluded from
the actions and from scene suggestions**, and appears in the owner's images as a text line "wearing
Zahhak's crown on his head". It is passed as a reference image only in full-figure views that are not
poses, when the model has a free slot (`len(references) + len(depends_on) < max_references`), and in
close-ups only when `worn_on` is the head or neck. The judge checks its presence (required) and its side
(not required: edits flip sides). Garments stay in the outfit (section 1A); permanent body marks are
parameters (section 2).

### 4. States for objects

Deferred (one image per object state made from the hero, used by scenes through `SceneRef.state`).

### 5. Places as rich datasets (reduced)

Places keep `SubjectReferences`; a new environment presentation `quality-coverage` has, after the hero
(the establishing view, empty), Reverse, Left, Right and High views (Qwen-Image-Edit, `editor = "turn"`,
with camera values) and one image per place state (`states` on a place in the project file; a FLUX.2
klein edit of the hero that changes only the light and the weather). Images are tagged
`tags = ["view:<item>", "state:<name>"]` so a place can later become training data. Place reference
lighting defaults to `soft-daylight` (neutral studio light stays for characters and objects on white).
Anchor close-ups (they need `anchors` as a list) and the place page are deferred.

### 6. Measured checks

Before the vision judge, measured checks run on a candidate; each becomes a `CheckResult` (`required`,
`score`, `finding`) merged into the evaluation **before** `passed` is computed:

- **Duplicate views** (no model, Pillow only): a 64-bit difference hash of the candidate against the
  subject's hero and its views already made in this pack; under 6 bits apart fails `distinct_view`
  (required), except for `round` objects. A required measured failure skips the vision judge; its
  finding ("Side looks the same as Hero: turn the object to show its side") goes into the next round.
- **Same subject** (DINOv2 small): advisory (`required = false`), the cosine similarity to the hero
  logged for calibration after the run.
- **Pose kind** (ViTPose): advisory `pose_kind` for poses that sit, kneel or run (a `kind` on the pose
  item): the hip, knee and ankle heights against the mannequin's. Tested before writing: ViTPose finds
  the joints of the wooden mannequins (scores 0.94–0.96). Limb-direction similarity is deferred.

The model checks run through hone-models' `command` provider: entries `frame-image-embedding` and
`frame-pose-keypoints` (`kind = "image"`, `capabilities.vram_gb = 0.1`, `env = {CUDA_VISIBLE_DEVICES =
"", HF_HUB_OFFLINE = "1"}`), command `["$HONE_FRAME_TOOLS_PYTHON", "$HONE_FRAME_TOOLS_DIR/frame_vision.py",
"{request}"]`; hone-frame sets `HONE_FRAME_TOOLS_DIR` itself. hone-models does not return a command's
`meta`, so the adapter writes its numbers into the output PNG's text chunk `hone-frame` (JSON), read
back with Pillow. One call per candidate with the candidate and its reference as `references`. If
`HONE_FRAME_TOOLS_PYTHON` is unset or not a file, a `measured_skipped` event is written and nothing is
called; a failing tool call is logged and the check skipped, never failed.

### 7. Action poses

An action item names how the belonging is used (`use_pose` on the object, e.g. "drawing the bow, the
string pulled back to the cheek", "raising the mace overhead with both hands"); without one, a default
per shape (`long`: raised overhead; `flat` bow: drawing). The pose library draws the mannequin in that
pose with empty hands; the action is made by Qwen-Image-Edit (three references: the character, the
belonging, the mannequin).

Actions get a `pose` reference like pose images; the action text is "<name>, <use_pose>, with
<belonging>"; the mannequin prompt adds "empty hands, holding nothing". Default `use_pose` by shape:
`long`: "raising it overhead with both hands"; a `flat` bow: "drawing the bow, the string pulled back to
the cheek"; otherwise none (no mannequin).

### 8. Mannequins by build

The pose library's mannequins are keyed by pose **and** build class (`slight`, `average`, `heavy`), and
the mannequin prompt says the build ("a broad, heavy-set mannequin"), so a massive character is not
posed from a slender figure. Classes: slight ← slight, lean; average ← average, athletic; heavy ←
heavy, massive. The mannequin key is `<pose>|<class>`.

### 9. The run profile and model routing

A profile gains `turn_editor` and `compose_editor` (`ResolvedProfile` fields): outputs whose item has
`editor = "turn"` use the turn editor; actions and scenes (kind `interaction` and `scene`) use the compose
editor; other edits use `editor`. Profile `quality`: generator z-image-turbo; editor flux.2-klein-4b;
turn_editor and compose_editor qwen-image-edit-2511; planner gemma4-12b (think off); judge
qwen2.5vl-7b; 2 rounds, 1 candidate, `stop_on_pass`; approvals `auto`. hone-frame's registry declares
`max_references = 3` for qwen-image-edit-2511 so scenes reduce extra references to words.

## Consequences

- Prompts grow by a short identity line and element lines; over-budget prompts are sent long, never cut.
- A Zahhak world (2 characters, 3 places, 2 objects and a worn crown, 2 scenes) is about 110 outputs,
  about 27 of them on Qwen-Image-Edit: about 3 h per round, about 5–5.5 h expected with second rounds and
  model swaps; the 9-hour window leaves room for one restart.
- Baseline: about 20 named outputs (heroes, turnarounds, poses, the mace, a place, a scene) are made on
  `main` with its usual profile, for a side-by-side comparison. The report gives pass rates per pack and
  model, the measured-check scores, time per model, and the side-by-side images.
- Existing records keep working: parameters, garments, `shape`, `worn`, place states and the profile
  fields are optional; without them the old behaviour applies.

## Acceptance cases (experimental, AC-35 to AC-43)

- **AC-35** A character with garments: a view's `keep` names every garment; nothing is cut mid-phrase;
  without garments the outfit text is whole even in compact mode.
- **AC-36** An object's hero prompt carries its details, materials and colours; a place's its anchors.
- **AC-37** An action's prompt always keeps the reference roles; the planner is skipped for actions; the
  judge's object check names image 3; the belonging's never list is checked.
- **AC-38** Every character edit carries the identity section from the parameters, chosen by kind of
  image; the judge's `parameters` check is view-filtered and allows `not_assessable`.
- **AC-39** An object's views follow its shape; a turning view's Qwen camera phrase comes from the item's
  values, never the default front view.
- **AC-40** Worn elements get a hero and a close-up, are excluded from actions, appear in the owner's
  images by name, and are never a reference in pose images.
- **AC-41** A place gets the quality-coverage views and its states, tagged `view:` and `state:`.
- **AC-42** Identical views fail `distinct_view` and skip the judge; without the tools environment the
  model checks are skipped with an event.
- **AC-43** Per-output routing picks the turn editor for turning items and the compose editor for
  actions and scenes.
