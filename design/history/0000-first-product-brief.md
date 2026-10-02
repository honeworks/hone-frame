# 0000: The first-product brief (2026-10-02)

The owner's product brief for Hone Frame, kept as given. It came with two dashboard mockups: a live run on
the Queue view, and the Library with a scene-builder panel. [0001](../changes/0001-initial-design.md)
turns it into the design, and [current.md](../current.md) is the design as it stands.

---

## hone-frame — First Product Design

Status: proposed first-product specification  
Package name: `hone-frame`  
Python import: `hone_frame`  
Product name: Hone Frame

## 1. Product purpose

Hone Frame is a project-based visual production workspace for creating characters, environments, objects, reference sheets, and scenes. It combines configurable generation pipelines with a simple dashboard that shows the work as it happens.

Users describe a project, create its reusable visual elements, select which elements belong in a scene, explore inexpensive drafts, and produce final images using their chosen models. Individual generated images remain available independently. Reference sheets are compositions of those images and can be rebuilt without another model call.

The first product includes image sequences as ordered still frames for downstream video tools. Its primary outputs are images, sheets, and reusable reference packs.

## 2. Core experience

A user creates a project called “Morning at home,” describes its visual direction, chooses a built-in style pack, and selects draft and final generation profiles. They enable automatic judging, choose three generation rounds per requested output, and leave candidate selection to the system.

Inside the project they create a woman, her kitchen, a toothbrush, breakfast objects, and a coffee cup. Each subject has its own description, references, states, and generated images. The dashboard displays progress, previews, judging results, selected candidates, and unresolved failures.

The user composes a character sheet from chosen views and expressions using a Python compositor. They compose separate environment and object sheets in the same way. Layout, labels, included images, and export dimensions remain editable without AI generation.

For a coffee scene, they select the woman, kitchen, and cup. The toothbrush and unrelated objects are absent from the reference inputs. They explore a fast draft, choose a composition, and render a final version. From that scene they can request camera coverage, an expression variation, a before/after state, or an ordered sequence of still frames.

## 3. Project workspace and objects

The project is the organising unit. “Cast design” in this product means a workspace where the user defines a project and creates its characters, environments, assets, and scenes. It does not require a separate cast-design wizard.

| Object | Contents and relationships |
|---|---|
| Project | Name, brief, visual direction, default presets, generation profiles, selection policy, characters, environments, assets, scenes, sheets, and runs |
| Character | Stable identity, appearance, proportions, distinguishing features, descriptions, references, views, outfits, expressions, poses, and states |
| Environment | Place description, spatial anchors, materials, viewpoints, lighting and condition variants, and recurring objects |
| Asset | Independently reusable prop or object, dimensions or relative scale when known, materials, colours, views, details, and states |
| Variant/state | A named change to an existing subject: outfit, expression, damage, wetness, open/closed, filled/empty, or lighting condition |
| Image | Original generated or imported file, dimensions, subject links, source references, generation metadata, and quality/selection status |
| Sheet | Saved selection and arrangement of existing image versions, labels, palette, and layout settings |
| Scene | Description, selected subject versions and states, reference roles, camera, action, pose/expression, lighting, framing, and generated results |
| Sequence | Ordered scene moments with shared subjects and explicit state changes |
| Run | Saved generation plan, effective settings, tasks, attempts, evaluations, selections, timing, usage, and progress |

Characters, environments, and assets have separate project tabs. The image library provides a combined view with filters. The term “asset” on the Assets tab means objects/props; a combined library uses “Images” to avoid ambiguity.

Saved scenes and sheets refer to specific image and subject versions. Changing a subject creates a new version; existing outputs keep their original references. A visible update indicator identifies scenes or sheets using an older version, with a user-controlled update action.

## 4. Generation profiles and strategies

Speed/quality profiles and selection strategies are independent controls.

### Quality profiles

| Profile | Intended use |
|---|---|
| Draft | Fast or inexpensive generation for composition, pose, and visual exploration |
| Standard | Normal image production with a balanced model and settings |
| Final | Stronger model and/or higher-quality settings at the target export resolution |
| Custom | User-defined planner, generator, judge, dimensions, and supported generation parameters |

Profiles use connected local or remote models through Hone's model layer. A profile describes the intended tradeoff; “Draft” is not a promise that every available model is fast. The effective model and settings remain visible.

### Selection strategies

| Strategy | Behaviour |
|---|---|
| Generate candidates, then pick | Generate the configured candidates for one requested output, evaluate them, and select the best eligible result |
| Generate, judge, then continue | Generate one candidate, judge it, and use findings to guide the next candidate; complete this output before moving to the next |

An output is one requested view, expression, interaction image, scene, or sequence frame. A sheet may contain many outputs.

### Precise controls

- **Rounds per output:** number of generation-and-evaluation rounds for each output. Default: 3, including the first round.
- **Candidates per round:** default 1; greater values support batch exploration.
- **Automatic judge:** on/off and the selected judge profile.
- **Automatic pick:** on/off. Automatic picking requires evaluation evidence; the UI exposes the judge dependency.
- **Stopping rule:** “Run all rounds” by default; optional “Stop when a candidate passes.”
- **Failure policy:** after the budget is exhausted, keep all images and mark the output “Needs review” if none qualifies.
- **Technical retry limit:** separate bounded handling for model/service failures. Technical retries are visible and do not silently add creative rounds.

With 3 rounds and 1 candidate per round, one output produces 3 candidate images when all calls succeed and early stopping is disabled. Twelve outputs produce 36 candidates. With 3 rounds and 2 candidates, twelve outputs produce 72 candidates. Evaluations and technical retries are shown separately from image counts.

The best acceptable candidate across completed rounds is selected; a later candidate does not automatically replace a better earlier one. A sequential strategy may use earlier feedback, but the stable identity references remain authoritative.

Project defaults apply to new generation requests. A request may override them, and its effective configuration is saved. Changes to project defaults do not mutate a running job.

## 5. Automatic judging and picking

Automatic evaluation is available for character, environment, asset, and scene outputs. It runs unattended when enabled. Manual review is an optional selection mode or a response to unresolved failure, not a mandatory gate between every step.

Evaluation combines required checks with preference ranking:

- Character: identity, requested view/pose/expression, outfit/state, framing, visible anatomy, and style.
- Environment: requested viewpoint, visible spatial anchors, recurring object positions, materials, lighting, and style.
- Asset: shape, distinctive details, material, requested view/state, scale cues, and style.
- Scene: subject presence, action, requested reference roles, composition, camera, continuity, and style.
- Sequence: per-frame quality plus consistent subjects and the intended state progression.

Checks apply only where meaningful: an isolated cup has no face or limb-anatomy requirement. A hand holding a cup has both interaction and anatomy checks. The judge can return “uncertain” or “not assessable”; model scores are comparative signals, not calibrated probabilities of correctness.

Every evaluation records a verdict and concise, specific findings. Required failures cannot be hidden by a high aesthetic score. No passing candidate means “Needs review,” with the best available draft retained but not presented as accepted. Dependent tasks wait when they require an accepted reference; unrelated work can continue.

Users can inspect candidates, choose a different one, and record a manual override. Selection and quality verdict are separate: manually selecting a failed candidate does not erase its findings.

## 6. Separate images and Python-composed sheets

Generation produces independently stored images. Character, environment, and object outputs do not become inseparable parts of a single generated collage.

The sheet composer arranges selected existing images using Python. It provides character turnarounds, expression grids, pose grids, environment boards, object views, details, comparison boards, and custom grids.

Controls include image selection, ordering, crop/fit, columns, page size, background, spacing, labels, heading, palette, and optional notes. Character-only, environment-only, asset-only, and scene-specific mixed sheets are available. Labels, metadata, and palette swatches are typeset deterministically.

Saving a sheet preserves its layout recipe and exact source image versions. Recomposition never regenerates the source images. Increasing the sheet canvas resolution does not invent additional image detail; an upscale or refinement operation is separate.

Downloads include the composed PNG and optionally the original individual images plus machine-readable descriptions and metadata. A scene reference pack includes only the selected subjects and views for that scene.

## 7. Scene generation and reference roles

A scene begins with a description and explicit selections from the project's characters, environments, and assets. The interface shows the exact input references before generation. Unselected project objects are never added merely because they exist in the project.

Each reference has a purpose: identity, outfit, environment, object, pose, expression, composition, lighting, or style. For example, a user can supply one character's face, a separate outfit image, a pose reference, and a lighting reference without implying that every reference should contribute another subject.

Conflicting references have visible precedence. Explicit scene overrides take precedence over project defaults; identity and state are separate constraints. Unsupported role controls are shown honestly. Some backends support dedicated conditioning, while others can only receive images and role instructions with weaker control.

Reference count and image-size limits are checked before submission. The user sees the selected order and any required reduction. A composed sheet is an optional reference format, not an automatic substitute for all individual images. There is no hidden attachment of every project sheet.

## 8. Camera, pose, interaction, and state features

### Camera coverage

An existing scene setup can produce an establishing shot, wide shot, medium shot, close-up, detail shot, front view, profile, rear view, three-quarter view, overhead view, low angle, reverse angle, or character point of view.

Coverage shares subject identity and state while describing each camera change explicitly. Requested views are individual outputs with their own candidates and quality results. Camera coverage is still-image generation; it does not imply exact reconstruction of hidden geometry.

### Pose and expression controls

Built-in pose and expression presets, text descriptions, and reference images are supported. Scene controls include gaze direction, head orientation, body orientation, and hand/action intent. Pose/skeleton conditioning is exposed when the connected backend supports it; a skeleton editor is not required for the first product.

### Character–object interactions

An interaction combines a selected character, selected object, action, and optional pose reference. Examples include holding a cup, gripping a sword, wearing a backpack, sitting in a chair, opening a door, or using an appliance.

The resulting images remain linked to both subjects and can be reused as scene references or included in sheets. Evaluation checks the visible contact, hand placement, object orientation, scale, and identity as appropriate.

### Before/after states

Named states describe intended changes while retaining a shared base identity: dry/wet clothing, intact/damaged sword, open/closed door, empty/full cup, tidy/disordered room, or daylight/night lighting.

A paired before/after request shares framing when requested and records what should change. Intentional state changes are not treated as continuity errors. State definitions remain available independently of a single generated pair.

## 9. Sequence generation

Sequences produce ordered still images with a shared visual context and explicit moment descriptions. Example: reach for cup → touch handle → grip cup → lift cup.

Each frame records its starting state, intended action or change, resulting state, selected references, and accepted output. Stable character/environment/object references remain available throughout. A previous frame may provide continuity guidance, but it does not become the only identity reference, which could accumulate drift.

Users can inspect or retry one frame. Changes flag affected later frames when those frames depend on the changed result. Sequence export contains numbered images, frame order, descriptions, and reference metadata. The first product does not promise smooth animation between these stills.

## 10. Draft exploration and final production

Draft and final profiles can use different model families, providers, dimensions, and generation settings. A user can explore a scene or batch cheaply and promote only selected results.

Promotion has three explicit meanings:

| Operation | Meaning |
|---|---|
| Upscale | Increase an existing image's resolution through a supported enlargement backend |
| Refine from draft | Give the selected draft and its original subject references to a final model to preserve composition while improving detail |
| Regenerate as final | Use the saved scene definition and original references to generate a new final image |

Model changes can alter identity or composition. Drafts remain preserved, final images retain their parent links, and the dashboard supports draft/final comparison. Judging checks both subject consistency and the properties requested for preservation. Failed final refinement never silently replaces a successful draft.

## 11. Batch variation grids

Users select variation axes such as outfit, expression, camera, lighting, object state, or style. A batch expands the selected combinations into individually traceable outputs.

Before launch, the batch summary shows combinations, candidates per output, total planned image calls, judging work, and available time/cost estimates. Three outfits × four expressions × two lighting setups means 24 outputs; three rounds with one candidate each means 72 planned images.

Results appear in a labelled comparison grid. Each cell exposes its candidates and selected result. Users can promote chosen cells, retry failed cells, or compose a comparison sheet. Local GPU tasks may be scheduled serially even when the logical batch contains many independent outputs.

## 12. Built-in presets available before project creation

The installation includes a useful, populated preset catalogue. Users do not need to upload mood boards, write style instructions, or create presets to start a project.

Project style packs combine defaults across several independent preset categories. Each category can also be chosen separately, so choosing a camera preset does not replace a character's identity or change the project's art style.

### Initial catalogue

| Category | Included choices |
|---|---|
| Project style packs | Cinematic realism, illustrated storybook, clean 2D animation, cel-shaded animation, inked comic, painterly fantasy, stylised 3D, miniature stop-motion look, historical epic, product studio |
| Character presentations | Neutral full body, portrait/detail, turnaround, expression study, pose study, outfit comparison |
| Environment presentations | Interior coverage, exterior coverage, establishing/detail board, day/night comparison, material/landmark board |
| Asset presentations | Front/side/back/three-quarter, top/detail, isolated studio object, scale comparison, state comparison, interaction study |
| Camera/framing | Establishing, wide, medium, close-up, extreme close-up, detail, front, profile, rear, three-quarter, overhead, low angle, reverse, POV |
| Lighting | Neutral studio, soft daylight, overcast, dawn, golden hour, moonlight, candlelight, practical interior, dramatic side light |
| Expressions | Neutral, happy, sad, angry, afraid, surprised, tired, focused, doubtful, determined |
| Poses/actions | Neutral standing, seated, walking, reaching, pointing, looking back, holding, carrying, gripping, pushing, pulling |
| Interaction templates | Hold cup, grip weapon/tool, wear backpack, sit on chair, open door, operate appliance; selected objects supply the actual design |
| State templates | Clean/dirty, dry/wet, intact/damaged, open/closed, empty/full, on/off, day/night, tidy/disordered |
| Sheet layouts | Four-view turnaround, expression grid, pose grid, object detail board, environment board, before/after, sequence strip, custom contact grid |
| Generation profiles | Draft, Standard, Final, Custom |
| Selection recipes | Batch then judge, sequential judge/refine, all rounds, stop on pass, manual pick |
| Judging profiles | Character identity, environment continuity, object fidelity, interaction plausibility, scene fidelity, sequence continuity |

Presets contain structured intent, useful defaults, relevant constraints, supported subject types, and compatible capability requirements. Unsupported combinations are explained or disabled. No preset silently forces a particular paid provider.

The default project pack is Cinematic realism, with neutral reference lighting and a four-view character layout; other styles are available immediately. Image previews are optional enhancements, not a prerequisite for using the catalogue. The preset browser remains useful through text descriptions and available examples before a project exists.

Preset versions are recorded with each run. Updates to the catalogue do not silently change existing project settings. User customisation and saving a new pack are optional additions to the built-in experience.

## 13. Reusable production recipes and agent-facing capabilities

Hone Frame's reusable production recipes describe the inputs, planning rules, generation strategy, relevant checks, bounded refinement, and output types for a task. Initial recipes cover character references, environment references, asset references, sheet composition, scenes, camera coverage, interaction studies, state pairs, sequences, and variation grids.

Agent-facing skills describe these same product capabilities for a local coding/automation agent. Dashboard actions and Python operations refer to the same saved project objects and runs; there is no separate hidden workflow with different defaults.

Within the Hone ecosystem, model access belongs to `hone-models`, run execution to `hone-flow`, and selection to `hone-select`. Hone Frame owns visual project definitions, presets, recipe intent, reference relationships, domain-specific evaluation, deterministic sheet composition, and the dashboard. These are responsibility boundaries, not assumptions about currently available APIs in those packages.

## 14. Dashboard information architecture

The dashboard is flat, restrained, and centred on current projects and visible outputs. Core actions are reachable without deep navigation or nested card stacks.

The left sidebar contains a project selector and: Overview, Create, Library, Scenes, Sheets, Queue, Presets, Models, and Settings. Library has flat tabs for Characters, Environments, Assets, and Images. A selected item opens its detail view or a side panel with description, references, states, results, and history.

| View | Main contents |
|---|---|
| Projects | Project list, search, create action, recent work |
| Overview | Four useful metrics, current activity, live queue, and recent images; real usage trends when enough history exists |
| Create | Task type, description, selected subjects/references, preset choices, generation profile, automatic judge/pick, rounds, and result preview |
| Library | Filterable project entities and images; image/subject type, name, state, model, and date filters |
| Scenes | Scene list, scene definition, selected references and roles, camera/pose/state controls, drafts and finals |
| Sheets | Deterministic composition editor and saved sheets, with source selection and layout preview |
| Queue | Task/run progress, stage, candidate/round counts, timing, usage, findings, and control actions |
| Presets | Built-in style packs and category presets available before project creation; optional custom packs |
| Models | Connected planner, image, judge, and upscaler capabilities, availability, model identity, and observed latency |
| Settings | Project defaults, generation policies, connections, appearance, and usage details |

Create uses a settings column and a larger results area. Essential settings are visible; technical sampling parameters and raw prompts live in an Advanced disclosure. Capability-specific fields, such as negative prompts or steps, appear only when supported.

The project selection sets the visible scope. Cross-project queue or library views have an explicit “All projects” scope. Presets and model connections may be global; saved project choices remain project-specific.

## 15. Progress and operational behaviour

A run displays its overall status and a readable sequence of stages: planning, generating, judging, selecting, refining, composing, exporting. Only applicable stages appear.

The task detail shows the current subject/output, round, candidate, model, elapsed time, queued work, completed work, latest preview, judge findings, and what comes next. A user can see “Generating kitchen profile, round 2 of 3” rather than only a spinner.

Statuses distinguish Queued, Running, Pausing, Paused, Done, Needs review, Failed, and Canceled. Finishing model calls is not the same as passing quality checks. A partially successful run shows accepted outputs and unresolved outputs separately.

Progress uses actual backend step progress when available. Otherwise it reports completed tasks and an indeterminate current generation. Planned optional refinement and early stopping can change the remaining work; the UI reflects that change instead of pretending the original percentage is exact.

Estimated remaining time is a range based on observed durations for comparable model/profile/resolution work, current queue position, configured rounds, and resource constraints. New configurations show “Estimating” until there is useful evidence. The UI never counts down invented precision.

Actions include cancel, pause after the current safe boundary, resume, retry failed tasks, and rerun a selected output. In-flight cancellation depends on the backend; when it cannot stop immediately, the UI says it will stop after the current call. Completed images and decisions survive refreshes and restarts.

Interrupted remote operations retain their job identity where available. An unknown outcome is reconciled before a replacement generation is submitted, to reduce duplicate work and charges. Local GPU work is resource-aware, with image generation and judging scheduled around available memory.

Usage displays observed render seconds, GPU time when available, and provider-reported or explicitly estimated cost. Local work does not receive a fabricated dollar price. Credit balances appear only when a connected provider exposes them. The dashboard contains no invented KPI counts, deltas, or usage charts.

## 16. Dashboard visual design — Studio Minimal

Light theme is primary; dark theme is available. The visual language comes from the supplied Studio Minimal guide: pale cool-grey canvas, flat white surfaces, thin borders, one restrained blue accent, generous spacing, and almost no shadow.

### Colour tokens

| Token | Light | Dark |
|---|---|---|
| canvas | #F4F6F9 | #0F1218 |
| surface | #FFFFFF | #171B23 |
| surface-sunken | #EEF1F5 | #1E232D |
| line | #E3E7EE | #2A303B |
| line-control | #7D8697 | #646D7E |
| ink | #141821 | #EEF1F6 |
| ink-muted | #5D6676 | #9AA3B2 |
| accent | #1F4FE0 | #7EA2FF |
| accent-soft | #E8EEFF | #1C2647 |
| on-accent | #FFFFFF | #0F1218 |
| success | #147A3D | #4FC47E |
| success-soft | #E6F4EC | #11291B |
| warning | #9A5800 | #F0B44C |
| warning-soft | #FDF1DE | #2E220D |
| danger | #C23A12 | #FF8A65 |
| danger-soft | #FDEBE5 | #33170F |

Semantic colours label state; every state also has a word. Actual rendered text/background pairs meet AA contrast for their size, and controls have visible boundaries and keyboard focus. The faint `line` token is for structural dividers, not a replacement for control borders.

### Typography and layout

- UI/headings: Plus Jakarta Sans; system sans-serif fallback. IDs, seeds, technical prompts, and model versions: JetBrains Mono; system monospace fallback. Numbers use tabular numerals. Fonts have a usable local/system fallback when offline.
- Display numbers: 32/40px, weight 700. Page heading: 22/30px, weight 700. Section title: 16/24px, weight 600. Body: 14/22px. Caption: 12/16px. Overline: 11/16px, weight 600. Mono: 13/20px.
- Fixed 240px sidebar with a subtle right border; 64px top bar. Main content uses a 12-column grid, maximum width 1440px, and 24px gutters. Desktop page padding is 32px; mobile padding is 16px.
- Spacing scale: 4, 8, 12, 16, 24, 32, 48px. Surface padding: 24px. Controls: 6px radius; bounded panels and modals: 12px; thumbnails: 8px; status pills: fully rounded.
- Surfaces have 1px borders and no shadows. Only floating menus/modals use `0 8px 24px rgba(20,24,33,0.08)`. Focus is a 2px accent outline with 2px offset.
- Below 1024px the sidebar becomes a 72px icon rail with accessible labels. Below 640px primary navigation becomes a bottom bar with a More entry for remaining destinations; content stacks and wide tables scroll horizontally.

### Components and voice

- One primary action per view, e.g. Generate, Compose sheet, or Export pack. Primary buttons are 36px high with 16px horizontal padding. Secondary buttons use a surface fill and control border.
- Inputs are 40px high; prompt textareas are at least 96px. Plain-language descriptions remain readable, with technical prompt details in monospace.
- Table rows are 52px high with hairline separators, subtle hover, right-aligned numeric columns, and no zebra striping. Queue columns include output/job, model/profile, resolution, round, status, progress, elapsed/estimated time, and actions; less-used fields live in details.
- Status pills are 22px high, labelled with a 6px dot. Running uses accent; queued/needs-review uses warning; done uses success; failed uses danger; paused/canceled uses muted text. Motion respects reduced-motion preferences.
- Progress bars are 6px high. Unknown progress uses an indeterminate state rather than a fabricated percentage.
- Asset tiles show the generated image, name, dimensions, and concise state. Keyboard/touch access exposes actions without requiring hover. Selecting multiple items reveals Export, Tag, and Delete actions; deletion of referenced work exposes the affected uses first.
- Monochrome 20px line icons with approximately 1.5px strokes. No emoji, decorative illustrations, gradients, glass effects, neon, coloured card stripes, or heavy shadows. Generated/imported project images and preset examples provide the imagery.
- Overview may show images generated today, queued tasks, average render time, and GPU time or known provider balance. It has a live queue and recent images. Charts appear only where useful and use real character/environment/asset/scene work; unsupported 3D/video/texture product categories do not appear as working features.
- Chart lines are 2px, fills approximately 12%, and gridlines are faint and horizontal. Secondary series use restrained neutral tones with clear labels. Trend charts are not inserted into creation/editing views where they distract from the task.
- Copy is short, calm, and in sentence case. Errors name the problem and a useful action: “Generation failed: GPU memory is full. Choose a smaller image size or retry when the other job finishes.”
- Empty states explain the next useful action. The dashboard does not imply a hosted billing/account system: usage and provider balances replace a fictional subscription meter. Secrets are masked and excluded from exports.

## 17. Saved outputs and reuse

Every successful image remains independently accessible, including candidates not picked. A selected result points to an existing image rather than overwriting it. Project exports preserve descriptions, accepted references, individual images, composed sheets, scene definitions, sequences, preset versions, and relevant run metadata.

Existing images can be imported as subject references. Users can select a small subset for a scene or export pack. Draft, final, rejected, manually selected, and uncertain outputs remain distinguishable.

Run metadata records the input description, effective prompts, model identifier, supported parameters, seed when available, reference versions and order, timestamps, evaluations, and selections. A saved seed enables traceability but does not promise identical pixels across model or runtime changes.

## 18. First-product boundaries and observable outcomes

The first product includes projects, reusable character/environment/object images, deterministic sheets, scene generation, role-based references, camera coverage, pose/expression presets and image guidance, interaction studies, before/after states, ordered still sequences, variation grids, built-in preset packs, automatic judging/picking, draft/final profiles, and a live dashboard.

Full video generation, audio, rigging, a full 3D scene editor, arbitrary layer extraction, model training, a visual drag-and-drop scene canvas, multi-user collaboration, and a hosted subscription system are separate extensions. Pose or geometry conditioning can be used through existing backend capabilities without making those extensions prerequisites.

The first product is successful when these observable behaviours work together:

1. A fresh installation offers useful presets before the first project exists.
2. One project contains separately reusable characters, environments, assets, and scenes.
3. Three-round automatic generation runs without a manual gate for every output, preserves all candidates, and explains its selections.
4. A scene consumes only its selected references, with visible roles, versions, and ordering.
5. A user can compose and revise multiple sheets from saved images without another model call.
6. A selected fast draft can produce a traceable final result through an explicitly chosen upscale, refinement, or regeneration operation.
7. Coverage, interactions, state pairs, sequences, and variation grids reuse the same project subjects and expose per-output results.
8. The dashboard shows real progress, estimates honestly, survives refresh/restart, and supports bounded retry/resume without discarding accepted work.
9. Unresolved quality failures remain visible; a completed run never disguises failed references as accepted ones.
10. A user can export original images and a focused reference pack for another image or video tool.
