# 0006: Choices when generation starts: approvals, casting, a stronger judge; issue presets; clean-up

## Status

`implemented` 2026-10-03, decided by the owner the same day (decisions 4, 5, 8, 10, 11, 13, 14, 16, 17 of
the owner's list).

## Context

Everything a character needs is made from its hero, yet the hero was accepted by the judge alone and the
rest followed at once. Hero candidates came out as near-copies: a distilled model changes little with the
seed. "Generate again" took only free text, and the owner asked for standard issues to tick that really
change the next attempt. The 7B judge misses things that matter most on base images. Disk fills with
candidates nobody chose and with variations that were dropped.

## Decision

1. **When to check** (`approval` on every request): `auto` (as before), `base` (the run waits after the
   outputs others are made from: the hero, belongings' heroes and the pose mannequins, which are planned
   first), or `each` (also after every pack). The plan lists its `checkpoints`; after one, the run stops
   with "Waiting for your approval: …"; **Approve and continue** resumes it. The person can choose another
   candidate before approving. The character and project pages show waiting runs.
2. **Hero casting** (`CharacterPacks.casting`, 2 to 8): the planner writes that many distinct readings of
   the description (each keeps what is stated and varies what is left open: face shape, hair and beard,
   age within the range, build details, how clothes are worn, colour accents), and candidate *n* is drawn
   from reading *n*. Without a planner or when it fails, candidates differ by seed only.
3. **Standard issues** (`data/issues.toml`, 20 issues in groups: body, identity, anatomy, clothing, look,
   framing, face, objects): each has a `fix` added to the new attempt's prompt and a `check` added to its
   required judge checks. "Generate again" shows them as checkboxes with free text.
4. **Judge options** (`judge_mode`): the default judge, a stronger judge for base images, or for
   everything. The stronger judge is a workspace setting (`strong_judge`); without one the plan says so.
   On this machine no local vision model is clearly stronger (D-029), so the setting starts empty.
5. **Desktop notifications** when a run waits for approval, needs a choice, or is done.
6. **Clean-up**, the person's action: delete candidates of finished outputs that were not chosen (one in
   use is kept), or a whole variation (not the active or only one; refused while any of its images is
   in use, naming the uses).

Found on the real models and fixed here:

- An object's hero came out as a warrior holding the spear in a palace courtyard: the look guide (which
  describes warriors) pulled a person into the picture. Object images now carry the required prompt
  piece "The object alone: no person, no hands, nobody holding, wearing or riding it" and the judge check
  `object_alone` (object-fidelity version 3); the spear then came out alone on white.
- Casting readings appended at the end changed little; they now open the prompt, where the model weighs
  words most. The four Sohrab candidates then differed in build, sleeves, coat length and colouring;
  faces stay close (the description fixes most of the face).

Documented, not built now:

- **Grouping work by model** (all planning, then all images, then all judging) as an option. Outputs that
  others are made from must still be made and judged first; with approvals that is the base group.
- **The final pass** (upscale every accepted image not yet upscaled, a world-level action): no upscaler is
  installed (hone-models lists SeedVR2 3B, 3.9 GB; the disk has ~15 GB free). It needs an upscaler
  workflow in the frame registry first.

## Consequences

- With `base`, the hero, belonging heroes and mannequins run before anything else, in one group.
- Casting heroes take one planner call more and as many candidates as readings.
- A rerun's prompt and judging change with the issues ticked; the issue ids stay on the output.

## Acceptance cases

- **AC-30** `base` waits after the base group and continues after approval; `each` also after each pack;
  `auto` never.
- **AC-31** A casting hero's candidates come from distinct readings; a failing planner leaves seeds only.
- **AC-32** Ticked issues add their fixes to the prompt and their checks to judging; unknown issues are
  refused.
- **AC-33** The stronger judge judges the base images (or everything) when asked; without one set the
  plan says so.
- **AC-34** Clean-up deletes unchosen candidates or a variation's images, keeps images in use, and
  refuses the active variation.
