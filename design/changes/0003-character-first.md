# 0003: Character first: complete character packs, world assets, and a dashboard that follows the work

## Status

`accepted` 2026-10-02, requested by the owner after making the first real character (Rostam). Their
words, condensed: the expression issue (a new hero is drawn for every pack); poses and expressions get
backgrounds and must be on white; "the dashboard flow is not clear"; generating a character means
generating **everything** (expressions, poses, clothing...) at once, with only the option to leave
parts out, then regenerate or add one part later, all on the character's page; "generate assets" on
the project page and on the character page, where world assets and character assets are different;
expressions are close-ups of the face; scenes belong to the project and an LLM decides which of a
character's own assets a scene uses; the first sheet shows the hero with no object, and a character
holding or using an object is a character reference, not a scene; "make it user friendly".

## Context

0001 made a character's references one request among many in a generic Create form: a
`SubjectReferences` request with one presentation at a time (turnaround, or expression study, or pose
study...). Each request drew a **new hero** first, so packs made at different times came from different
heroes. Reference images took the style pack's lighting until D-021 made it neutral grey, and nothing
stopped a pose from adding a room. Objects a character carries were described in the character's text
("the mace always with him"), so every reference showed them. The dashboard grouped work by tool
(Create, Library, Scenes, Sheets, Queue) instead of by what a person makes (a project, its characters,
its world, its scenes).

## Decision

### 1. Concepts

- **Project**: the brief, the style pack and defaults (0001), its characters, its **world assets** and
  its scenes.
- **Character**: as 0001 (description, appearance, build, distinguishing features, default outfit,
  states), plus its **packs** and its **character assets**.
- **World assets**: environments and objects that belong to the project and anyone may use (the White
  Fortress, a battlefield, Rakhsh). They are 0001's environments and assets without an owner.
- **Character assets**: objects that belong to one character (Rostam's mace, Sohrab's onyx armlet).
  An asset gets `owner` = the character's id. They are generated like world assets (their own views) and
  appear on the character's page.
- **Pack**: one part of a character's references. Each pack has **items**: the images it is made of.

### 2. Character packs (`data/character_packs.toml`)

| Pack | Items (defaults) | Look |
|---|---|---|
| `hero` | Hero | full figure, front, neutral standing pose, **empty hands, no props** |
| `turnaround` | Front, 3/4, Side, Back | full figure, neutral pose, empty hands |
| `expressions` | Neutral, Happy, Sad, Angry, Surprised, Afraid, Determined, Thinking | **close-up of the face**, front, head and shoulders |
| `poses` | Standing, Walking, Running, Seated, Kneeling, Fighting stance | full figure, empty hands |
| `outfits` | one per outfit state of the character | full figure, front, neutral pose |
| `states` | one per other state (condition, lighting...) | full figure, front |
| `actions` | one per character asset, "holding X" | full figure, the character using its own asset (the asset is an object reference) |
| `assets` | the character's assets themselves | each asset's own four views (0001 asset references) |

Every item of every pack is drawn on a **plain pure white background** and, except `actions`, with
**empty hands and no props**. The judge checks both (`clean_background`, `no_props`) as required checks
for these outputs.

### 3. Generating a character

- **Generate assets** on the character's page makes a `CharacterPacks` request: every pack by default,
  with checkboxes to leave packs out, and per pack optional **custom items** written by the person
  ("in party clothing", "drawing a bow", "exertion") added to the defaults.
- **The hero is drawn once.** If the character has an accepted hero, every other item uses it as the
  identity reference; otherwise the request starts with the hero and the rest wait for it (0001 §8.7).
  Regenerating the hero is its own action on the hero pack.
- **Regenerate a pack**: the same request with one pack (its items again). **Add to a pack**: one custom
  item. **Generate again** on one item: 0001's rerun with a note (D-019).
- **Choose a candidate** is available on every item, not only those that need review: a person can
  overrule the judge's pick at any time (0001 §8.5 `pick`).
- Images record `pack` and `item`; the character's page shows, per pack and item, the accepted image
  (latest accepted wins), its candidates and their verdicts.

### 4. The character model sheet

A Python layout (`character-model-sheet`, no model call) composed from the accepted pack images: the
name and description, the turnaround in a row, the expressions in a row, and a text panel with
appearance, build, distinguishing features and outfit. It is composed again whenever the person asks,
and kept as a sheet with versions (0001 §11).

### 5. Project page: generate assets

**Generate assets** on the project page makes the references of the project's world assets
(environments and objects without an owner) that have no accepted hero yet, with checkboxes per asset.

### 6. Scenes belong to the project

A scene selects characters and world assets (0001 roles). When a scene is saved from the dashboard, the
planner model reads the scene's description and each selected character's assets and decides which of
them appear ("Rostam raises his mace": the mace); those become `object` references marked `suggested`,
shown in the scene panel where the person can remove or add them. Without a planner, or when it fails,
no asset is suggested and the panel says so.

### 7. The dashboard follows the work

- **Sidebar:** Project, Characters, World, Scenes, Queue; then Presets, Models, Settings. The generic
  Create page and the Library leave the main path; an "All images" view remains under the project.
- **Project page:** the brief and style, **Generate assets**, the characters (hero thumbnails and pack
  progress), the world assets, the scenes, current activity.
- **Character page:** the hero beside the details (edit), **Generate assets** (with the pack
  checklist and custom items), then one section per pack: item tiles with their accepted image or
  state (not made yet, queued, generating, needs review), and **Regenerate** / **Add** per pack; a tile
  opens a panel with the candidates and their findings, **Use this one**, and **Generate again**. Then
  the character's assets (add, generate) and the model sheet (compose, export).
- **World page:** environments and objects without an owner, add and generate.
- Plain words everywhere ("Not made yet", "Waiting for the hero", "Needs your choice").

## Consequences

- One request makes a whole character; the hero is never redrawn by accident, so all packs share one
  identity reference.
- `SubjectReferences` (0001) stays for scripts and assets; characters use `CharacterPacks` in the
  dashboard.
- A character description should name only what the body and clothes show; carried objects become
  character assets. Existing projects keep working; their carried objects simply stay in the text.
- New judge checks and lighting text change the `judging` and `lighting` presets' versions.

## Acceptance cases

- **AC-15** A `CharacterPacks` request with every pack makes the hero first and every other item from
  it; a second request with the hero accepted draws no hero; leaving a pack out leaves it out; custom
  items are added to their pack; every item records its pack and item.
- **AC-16** Reference items are written with a white background and empty hands (actions excepted),
  expressions as face close-ups, and judged with `clean_background` and `no_props`.
- **AC-17** Character assets have an owner, are listed with their character, and become `actions`
  items; world assets are the ones without an owner; the project's generate-assets request covers those
  without an accepted hero.
- **AC-18** Saving a scene through the dashboard asks the planner which of the selected characters'
  assets appear and stores them as suggested object references; a failing planner suggests none.
- **AC-19** The character model sheet is composed from the accepted pack images without a model call.
- **AC-20** The dashboard API serves the project page, the character page (packs, items, accepted
  images, candidates) and the actions (generate assets, regenerate a pack, add an item, choose a
  candidate on an accepted item).

## Migration and compatibility

Stored data keeps `format_version: "1"`: the new fields (`owner` on subjects, `pack` / `item` on images
and planned outputs, `suggested` on scene references) are optional with defaults.
