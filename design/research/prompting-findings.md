# Prompting findings

Experiments on the machine the owner uses (8 GB laptop GPU): z-image-turbo (text to image), FLUX.2
klein 4B (text to image and reference editing), Qwen-Image-Edit 2511 (reference editing), gemma4-12b
(planner), qwen2.5vl-7b (judge). Images are in `~/hone-frame-lab/`; the folder for each experiment is
named below.

## Plain sentences, not tags; concrete descriptions, not labels (2026-10-03)

Question: how should culture, period and style be passed to the image model: a label, a description,
tags? Test: Sohrab's hero on z-image-turbo, two seeds per variant (`culture/`).

| Variant | What the prompt said about culture | Result |
|---|---|---|
| A, nothing | (a generic "steel mail shirt, red cloak") | Roman / European: plate armour, red cape |
| B, a label | "ancient Sasanian Persia, 4th century, Iranian warrior" | almost no change; still the Roman cape |
| C, concrete | lamellar coat laced with red cord, kaftan with a roundel pattern, conical helmet with a mail curtain, trousers gathered at the ankle | a large change: Persian / Central Asian armour |
| D, label and concrete | both | like C, slightly richer |
| E, tags | "Sasanian, Persian warrior, lamellar armor, conical helmet, …" | worse than A: a Roman crested helmet appeared |

Conclusions, which agree with the published guidance:

- **Write sentences, not tags.** FLUX.2 and Z-Image were trained on natural-language captions; tag
  lists work against them ([LTX FLUX.2 guide](https://ltx.io/blog/flux-prompting-guide),
  [FLUX.2 klein: what works](https://deapi.ai/blog/prompting-flux-2-klein-what-works-what-doesnt-and-why),
  [Z-Image guide](https://gist.github.com/illuminatianon/c42f8e57f1e3ebf037dd58043da9de32)).
- **Describe what is visible; a name barely helps.** Models fall back to Western defaults for
  non-Western costume unless the visible details are spelled out
  ([Bias by Default](https://dl.acm.org/doi/10.1145/3613905.3644053),
  [Cultural representativeness](https://dl.acm.org/doi/10.1145/3613904.3642877)); expanding a prompt with
  explicit cultural details is what fixed it in [KAHANI](https://arxiv.org/abs/2410.19419) and
  [CulturalFrames](https://arxiv.org/pdf/2506.08835).
- **Put it first** for FLUX: the model weighs the first words most.
- **Expand once, not on every prompt.** An LLM rewriting each prompt can add stereotypes and drift
  ([Prompt revision as a source of cultural bias](https://arxiv.org/html/2609.11532)). Write the look
  guide once, let the person edit it, store it.

This is why the world has a **look guide** (change 0005): culture, period, costume and materials in
concrete sentences, shared by every variation; the variation carries only how things are drawn.

## A long look guide is dangerous in compositions (2026-10-03)

The look guide (about 120 words) was made un-droppable. In actions and scenes it then pushed out the
sentence that tells the model which reference image is whom ("image 1 is Rostam, image 2 is the
mace"), and the planner filled the gap from the look guide's generic wording ("the warrior … carries a
long straight sword and bow case"): a sword appeared that nobody asked for, and Gordafarid became "he".
See [root-causes-2026-10-03.md](root-causes-2026-10-03.md), cause C. Lesson: the reference roles must
never be cut, and a look guide must be short where the references already carry the look.

## The prompt budget (2026-10-02 / 03)

- FLUX.2 klein's guidance is 40–120 words ("prompts exceeding 100 words create confusion"); we use 110
  for edits and 120 for text to image. Z-Image: 80–250. Qwen-Image-Edit: keep / change instructions.
  The 120 is quality guidance, not a hard limit: the text encoder takes far more. **Open test:** the same
  edit at 100, 150 and 200 words, to know what we can afford.
- Trimming to the budget silently removed the **pose** (most poses came out standing) and expressions;
  what an image is for must never be cut (change 0004).
- Shortening the outfit by cutting at commas destroyed garments whose description has commas inside
  ("a coat made from a whole tiger's skin, striped orange and black, worn over …" became "a coat made
  from a whole, striped orange and black, worn"). Structured clothing (one record per garment) avoids
  shortening prose at all; see the backlog.
- **The rule we settled on:** the reference image carries what is already visible; elements (an armlet,
  a helmet) travel as reference images, not words; parameters have a 2–4 word token and a priority per
  kind of image (a close-up takes beard, eyes, face marks; a back view takes hair length and cloak);
  the judge gets everything; measured checks need no words at all.

## Edit models keep the pose they are shown; mannequins fix it (2026-10-03)

FLUX.2 klein, editing the hero into a pose with text only, kept drifting back to the hero's standing
pose ("running" became a hop, "seated" a crouch, "kneeling" half-standing, worst in 2D). Leading the
prompt with the pose helped a little. Giving a second reference image, **a plain wooden artist's
mannequin in the pose** ("in exactly the body pose of the wooden mannequin in image 2"), fixed kneeling,
running, seated and fighting stance in both the realistic and the 2D style (`poses/`). Side effects
seen: in 2D the figure became slightly slimmer and a little more 3D-looking. This is the pose library
(change 0005). Next step: render the mannequins from a 3D body, sized to the character (tools file).

## Hero casting needs different readings, not seeds (2026-10-03)

z-image-turbo is distilled: new seeds give near-identical images. Candidates differ only when the
prompt differs. Four "readings" of the description (each varies what the description leaves open: face
shape, beard, build, how the armour is worn) differed in build, sleeves, coat length and colouring only
once each reading **opened** the prompt; faces stay close because the description fixes most of the
face (change 0006).

## The judge (qwen2.5vl-7b)

- **Field order matters.** With `verdict` before `finding`, the judge wrote "not kneeling" and still
  answered pass. With the finding first it stays consistent (change 0004).
- **It must be told what was asked** from the plan, not from the prompt that was sent (the prompt may
  have been rewritten or trimmed).
- **It cannot see some things at all.** A foot turned backwards in a side view passed with a general
  question, a feet-only question and a crop of the feet. Qwen3-VL 8B also missed it and sometimes
  answered only with "thinking" text. Gemma 4 and Qwen 3.6 builds installed here take no images.
  Measured checks (pose keypoints) are the way forward; see the tools file.
- **It is lenient on viewpoint for objects and strict on lighting for interiors** (neutral studio light
  is checked against outdoor or night places). Lighting for places is an open decision.
- **Wording leaks.** A sentence about rear views inside the general `view` question made it fail good
  front views ("not from the back"); back views now have their own check.

## Small things models cannot keep

- **Tiny marks on the face** (a beauty mark, a mole, a small scar) move between images: cheek, chin,
  lip, forehead in four expressions of Tahmineh. The plan now warns; an exact position and size plus a
  must-list entry helps but does not guarantee it. Measured checks (face landmarks) could verify it.
- **Left and right** flip when a pose turns: Sohrab's armlet moved between arms and to the wrists (his
  armour also covered the upper arm the description put it on).
- **Beard and hair length** drift in edits unless named: "the same face and hair" is not enough.
- **Flat objects** (a bow, a coiled lasso) look the same from front, back and side; an edit model
  returns near-copies.
- **A side-on reference does not give a top view** of a horse.

## Places

- The look guide (which describes warriors) pulled crowds into every place; places are now drawn empty
  (change 0006 era, D-039).
- A view of a place once asked to keep "the same face, hair, clothes" (person wording) and drew a
  man's portrait (D-040).
- Neutral studio lighting fails outdoor places; daylight is the suggested default (open decision).
