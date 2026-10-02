# 0004: Prompts that keep what they are for, a judge told what was asked, project files

## Status

`implemented` 2026-10-03, requested by the owner after the first full character runs: "make sure there
are no bugs in image generation we encountered and may encounter later"; "do a complete test on anything
that may actually go wrong with prompts"; "insert characters, worlds, scenes and everything using a JSON
or TOML"; a page that jumps back to a character being generated; a way to magnify an image; a side view
with a malformed foot that the judge passed; belongings made after the actions that use them.

## Context

Root cause of the poses (owner's run `20261002T211518Z-d915b7`): FLUX.2 klein's view budget is 110
words. `keep` repeated the whole outfit (about 60 words) and 0003 made the white background and empty
hands never-dropped (24 words), so the budget trimming removed the **pose** first: "Running" was asked
as "the same man from the front". The planner sometimes put it back from the item's name, so results
were inconsistent; the judge compared the image with the trimmed prompt, so "standing" passed as
"running". Expressions lost their expression the same way (Neutral, Afraid, Determined, Thinking).
A matrix test over every style pack and profile then found more of the same: FLUX text-to-image heroes
lost their full-figure framing and their style words; Qwen-Image-Edit compositions had no framing at
all; scenes' gaze was never written for FLUX or Qwen; and a planner rewrite of an over-budget draft was
always refused for its length.

The judge's `view` question carried a sentence about rear views, which the 7B judge read as the request
("the character is facing the camera, not from the back") and failed good front views. Its anatomy
question never named feet. Belongings were not in the dashboard's checklist, so actions were drawn from
words alone.

## Decision

1. **What was asked is never dropped.** The prompt sections `pose`, `expression`, `outfit`, `state`,
   `action`, `gaze` and `note` (a person's "Generate again" note) are kept whatever the budget, and so
   are `shot` and `style_lead` (framing and style). Over budget, `keep` first becomes compact ("the same
   clothes, armour and colours": the reference image shows them), then optional sections go; if it still
   does not fit it is sent longer and a `prompt_long` event says so.
2. **The planner keeps it too.** It is told what the image exists to show; a rewrite that loses most of
   those words is refused (`planner_rejected`) and the composed prompt is used. A rewrite may be as long
   as a long draft.
3. **The judge is told what was asked** from the plan (view, framing, pose, expression, clothing, state,
   action, background, empty hands), not only the prompt that was sent. `view` asks about the requested
   view only; back views get their own `faces_away` check. `anatomy` names hands and feet ("in a side
   view both feet point the same way as the face"). Side and three-quarter camera presets ask for the
   feet to turn with the body (versions 3).
4. **Belongings before actions.** An action whose belonging has no accepted image makes the belonging
   first in the same request and waits for it; the checklist shows Belongings.
5. **Objects in the hands are reported:** a plan warns when a character's features or outfit put an
   object in its hands, and the character page shows the warning.
6. **Project files** (`project_file.py`, `docs/project-files.md`): a project, its characters (states,
   belongings), places, objects and scenes in one TOML or JSON file; imported by name (new things
   created, changed ones versioned, nothing deleted) from the CLI (`hone-frame import`), the API
   (`POST /api/import`) and the dashboard; written back with `export-file` / **Download as file**.
7. **Dashboard:** each page renders into its own container, so a slow request or poll of a page the
   person left can no longer redraw it over the current one; every image has a magnifier that opens it
   full size.

## Consequences

- Prompts can be longer than a model's guide when the subject's description is long; the run says so.
- The judging presets `character-identity` (4), `interaction-plausibility` (3), `scene-fidelity` and
  `sequence-continuity` change version; the camera presets `profile` and `three-quarter` too.
- The 7B judge still misses some anatomy (a foot turned backwards in the owner's Rostam side view
  passes even with the new question, as it does with Qwen3-VL 8B; both were tried). Prevention in the
  prompt and the person's eye (the magnifier, **Use this one**, **Generate again**) remain the defence;
  a stronger vision judge is the fix when one fits the machine or a hosted one is configured.
- Tests: `tests/unit/test_prompt_matrix.py` checks every pack item, scene and note across every style
  pack and profile with realistic descriptions.

## Acceptance cases

- **AC-21** For every style pack and profile, every character pack item's prompt keeps its pose,
  expression, outfit, state or action, its framing, its style and the white background; never mixes a
  close-up with a full figure, a face with a back view or scenery with a white background; a planner
  rewrite without what was asked is refused.
- **AC-22** The judge prompt states what was asked; back views have `faces_away`; other views carry no
  back-view wording.
- **AC-23** Actions wait for their belongings, made first in the same request when they have no image.
- **AC-24** A project file creates a project with its characters, belongings, world and scenes; imported
  again after an edit it versions only what changed; bad files are refused with the place of the error.
