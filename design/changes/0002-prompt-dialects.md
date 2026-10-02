# 0002: Prompts written for the model, the task and the style

## Status

`implemented` 2026-10-02 (requested and accepted by the owner the same day: "Let's make our prompt be generated smart. For example
based on model. Even based on style... Let's create a design doc for it, and implement it.").
Tested on the real models with Rostam's Back view (see the pull request).

## Context

On the owner's first real character (Rostam), every Back view drawn by flux.2-klein-4b from the hero
image failed: the figure faced the camera, or stood in a columned hall. The prompt was one template for
every model and every task (design §8.2 of 0001). For the Back view it was about 230 words:

- it opened with the style pack's "Historical epic film still, period-accurate costume and
  architecture", so the view instruction came second and the background became architecture;
- it re-described the whole character, face included ("weathered mature face… thick dark beard… dark
  deep-set eyes"), then said "keep the **face**… exactly as in image 1" in a view that cannot show it;
- it never stated the edit itself: the same man, turned around.

The models' own guidance says different things for each model:

| Model | What it wants |
|---|---|
| z-image-turbo (text to image) | long, structured prompts, 80 to 250 words: shot and composition, subject, clothing and colours, background, lighting, style; no negative prompt, so every constraint is a positive sentence |
| FLUX.2 klein (text to image and reference editing) | 40 to 120 words, "prompts exceeding 100 words create confusion"; the subject first ("the model pays more attention to what appears first"); with references, describe the change, not everything again |
| Qwen-Image-Edit 2511 (reference editing) | instructions in the "keep X, change Y" pattern, naming what must not change; references called "image 1", "image 2"; with the Multiple-Angles LoRA, a camera phrase `<sks> [azimuth] [elevation] [distance]`, where "wide shot" fits a full figure and "medium shot" crops it |

A style matters too. On z-image-turbo a flat 2D look only holds when the prompt opens **and** closes with
the 2D wording (seen in an earlier project); a short prompt cannot carry a style pack's long prefix.

## Problem

One template cannot serve a long-prompt text model, a short-prompt editor and an instruction editor at
once, nor a reference view and a scene, nor a photographic and a flat 2D style. The prompt must be
written for **the model** (its dialect), **the task** (a new image, the same subject from another view,
a composed scene) and **the style**.

## Options

1. **Let the planner LLM do it all.** It already receives the model's guide line. A 12B planner kept
   the template almost unchanged on the Rostam run; rules it can ignore are not a design.
2. **One template per model in code.** Every new model or style means code.
3. **Prompt dialects as data, sections as code.** The pieces of a prompt (shot, subject, outfit, what to
   keep, the view instruction, roles, lighting, style...) are small functions. A dialect, in a data file,
   says for each task which pieces go in what order and the word budget. Style packs carry a short form
   and per-dialect wording. The planner gets the dialect's rules and its answer is checked against them.

## Decision

Option 3.

### Tasks (modes)

The composer picks the mode from what the model actually receives:

- `generate`: no reference images go to the model (a hero, or a model without reference input);
- `view`: the same subject again from its own reference (a character's other views, expressions,
  poses, states; an asset's or a place's other views);
- `compose`: references of several subjects or roles combined into a new picture (scenes, interactions,
  sequence frames);
- promotions (`refine`, `upscale`) keep their own fixed wording (0001).

### Dialects (`src/hone_frame/data/prompting.toml`)

Each dialect names the models it serves (ids, or `*` patterns) and, per mode, the ordered `sections`,
`max_words`, and the style form (`full`, the pack's prefix and suffix, or `short`). A dialect can set a
`camera_phrase` template (Qwen-Image-Edit's LoRA phrase) and `planner_rules` (one paragraph for the
planner). Shipped: `z-image` (long, structured), `flux-klein` (short, subject first; edits as a
change), `qwen-edit` (camera phrase first, keep / change), `generic` (the fallback, close to 0001's
template). A workspace may add or override dialects in `<home>/prompting.toml`.

### Sections (code, `prompt_sections.py`)

Small functions from the output's inputs to one sentence or nothing: `camera_phrase`, `shot`, `view`
(the instruction "Show the man from image 1 from directly behind…"), `subject`, `outfit`, `features`,
`keep` ("Keep exactly the same: …" from build, outfit and features), `scene`, `roles`, `action`,
`expression`, `pose`, `state`, `background`, `lighting`, `style_lead`, `style_close`, `text_refs`,
`note`, `fixes`. Rules they follow:

- a view whose camera **faces away** (camera presets mark it: `faces_away = true`) leaves the face out
  everywhere and says the face is not visible;
- full-figure outputs say so in the shot and use the camera's `wide shot` distance in the camera phrase;
- `view` and `keep` name the reference by number; `roles` keeps 0001's role sentences for `compose`.

When a prompt exceeds `max_words`, optional sections are dropped from the end of the order until it
fits; `view`, `keep`, `subject`, `scene`, `camera_phrase` and `fixes` are never dropped.

### Camera presets and style packs gain data

- Camera presets get `view` (the instruction phrase, e.g. rear: "from directly behind: the back of the
  head and body"), `faces_away`, and the Multiple-Angles parts `azimuth`, `elevation`, `distance`.
- Style packs get `short` (a few words that carry the style in a short prompt, e.g. clean 2D: "flat 2D
  vector animation style, not 3D") and optional `[values.dialects.<dialect>]` with their own `prefix`
  and `suffix` for one dialect.

### The planner and its check

The planner gets the dialect's rules, the mode, the word budget and the composed draft. Its answer is
used only if it stays within 125% of `max_words` and keeps the camera phrase when the dialect has one;
otherwise the composed draft is used and a `planner_rejected` event says why.

### What the run records

The `planned` event and the image's generation record keep the prompt as before, plus the `dialect` and
`mode`, so a person can see which way a prompt was written.

## Consequences

- Side and back views from Qwen-Image-Edit get the LoRA camera phrase and a short keep/change
  instruction; FLUX.2 klein views are 60 to 120 words; z-image heroes stay long and structured.
- New models or styles are data changes (a dialect, a pack's `short` or per-dialect wording).
- `camera_angle` is no longer sent as a separate input when the dialect writes the camera phrase.
- Changing a dialect changes future prompts only; the preset versions recorded in runs do not cover
  dialects, so the `planned` events and image records carry the dialect name.

## Migration and compatibility

None for stored data. Prompts written after this change differ from before for the same request.
