# 0005: One world, several variations; a look guide; poses from mannequins; objects with packs; the whole world in one go

## Status

`implemented` 2026-10-03, decided by the owner in a design session the same day (decisions 1–3, 6, 7,
14, 26 of the owner's list; approvals, casting, issue presets and judge options follow in 0006).

## Context

- The style was a project setting, so trying another style meant a new project and typing everything
  again. The owner: "World → World variation → everything else"; "I have not fully decided what style
  I want".
- Sohrab came out as a Roman officer. The project's "visual direction" (Sasanian-era) never reached a
  prompt, and the outfit text named no culture. A test on z-image-turbo (two seeds, five wordings) showed
  that a period label alone barely changes the picture, tags are worse (a Roman crest appeared), and a
  concrete description of what is worn works (`~/hone-frame-lab/culture`). The literature agrees: models
  default to Western costume unless the visible details are written out.
- Poses: an edit model keeps the pose of the image it is shown. With a plain wooden mannequin in the pose
  as a second reference, FLUX.2 klein drew kneeling, running and sitting correctly in both a realistic and
  a 2D style, where the text-only edit did not (`~/hone-frame-lab/poses`).
- Belongings were one front image inside the character's run; the owner never saw the spear before the
  action that used it, and world objects (Rakhsh) had no views.
- A beauty mark invented for Tahmineh moved from cheek to chin to forehead between images: small marks
  are not stable across edits.

## Decision

1. **Variations.** A project (the world) has `variations` (`id`, `name`, `style_pack`, `direction`) and an
   active one. Everything generated belongs to a variation (`ImageRecord.variation`, `Plan.variation`;
   a request may name one, else the active). Heroes, accepted images, references, character pages, model
   sheets and world assets are looked up per variation. A project made before this change has one
   variation, `main`, from its style pack; its images belong to it. `Project.add_variation`,
   `edit_variation`, `use_variation`.
2. **The look guide** (`Project.look`, shared by every variation): what things in this world look like,
   in concrete sentences. A required prompt section placed early (FLUX weighs the first words most), in
   every prompt that draws something new: heroes, objects, outfits and states (`context = "full"` per
   pack), scenes. Edits of the same subject leave it out: the reference shows it. A project made before
   this change uses its visual direction as its look guide. The variation's `direction` (a few words on
   how it is drawn) follows the style words.
3. **Must and never lists** per subject: `must` is a required prompt section ("Always visible: …") and a
   required judge check; `never` is a required judge check and goes into the negative prompt of models
   that take one (never into the positive prompt: "no X" tends to draw X).
4. **The pose library.** Every pose item except standing takes a mannequin in its pose as its `pose`
   reference ("in exactly the body pose of the wooden mannequin in image 2"). Mannequins are drawn once per
   project (fixed wording, judged by the `pose-reference` profile), belong to no variation, and are reused
   by every character.
5. **Object packs** (`data/object_packs.toml`): a belonging or world object gets a hero (three-quarter,
   from slightly above) and views (front, side, back, top, a close-up of its distinctive detail), made
   from its hero. A character's request makes each belonging without an accepted hero first (hero, then
   views), then the actions, which take the belonging's hero as their object reference. On the character
   page each belonging is a section like a pack; on the World page each object too.
6. **Whole-world runs.** `world_plan` (what would be made, with an estimate from measured seconds per
   image) and `generate_world` (one run per place, object and character, queued in order; the scenes are
   queued by the last run when it finishes, as `then` follow-up requests, since they need accepted
   heroes). Dashboard: **Generate everything**.
7. **Small-mark warnings:** a plan warns when a character's appearance or features name a small mark
   (beauty mark, mole, freckles, tattoo, scar…): give its exact place and size and an Always-shown entry,
   or remove it.

## Consequences

- Prompts for heroes get longer by the look guide; FLUX.2 klein's text-to-image budget is 150 words.
- The planner check counts only words of what was asked that the rest of the draft does not contain.
- `judging` gains `pose-reference`; `character-identity` and others gain `must_shown` / `never_shown`
  checks when a subject has the lists (built per output, not in the presets).
- Disk: every variation has its own images; clean-up comes with 0006.

## Acceptance cases

- **AC-25** Variations keep their own heroes and images; a new variation draws a new hero in its style;
  switching back plans no new hero.
- **AC-26** The look guide is in heroes and outfits and not in expressions; must and never lists reach
  prompts, judge and negatives; small marks are warned about.
- **AC-27** Pose images depend on a mannequin drawn first; another character reuses it.
- **AC-28** Objects get a hero and five views; belongings come before actions and appear as sections of
  the character page.
- **AC-29** Generate everything: an estimate, one run per subject, scenes after the last character.

## Migration and compatibility

`format_version` stays "1": every new field is optional. Old images belong to the first variation.
