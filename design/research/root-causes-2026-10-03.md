# Root causes: the first two-variation world (2026-10-03)

The owner reviewed the overnight world "Rostam and Sohrab v2" (variations "Realistic epic" and "2D
animated"). This is the analysis of every issue they found, made from the stored prompts, references,
images and verdicts. Nothing here is fixed yet; the fixes are in [ideas-backlog.md](ideas-backlog.md).

## Six causes

**A. The shortened outfit breaks garments.** Over budget, `keep` shortens the outfit by cutting at
every comma and keeping six words a piece. Outfits with commas inside one garment were cut into
fragments: "a coat made from a whole tiger's skin, striped orange and black, worn over a knee-length
lamellar coat of small steel plates laced with red cord" became "a coat made from a whole, striped
orange and black, worn, a knee-length lamellar coat of small". The tiger skin, the lacing and
Gordafarid's face-hiding mail veil were lost. (Introduced by the 0004 fix.)

**B. An object's own details never reach the prompt.** The `subject` section reads the character fields
(appearance, build). An object's size, materials, colours and distinctive details are skipped: the
mace's hero prompt said only "Rostam's legendary ox-headed war mace", not "the head is shaped like an
ox's head with two short curved horns"; Rakhsh's "rose-coloured dappled coat, tiger-skin saddle cloth"
was never sent.

**C. The look guide pushes the reference roles out of compositions.** The look guide is required and
about 120 words; in actions the optional roles sentence ("image 1 is Rostam, image 2 is the mace") was
cut. The model no longer knew who or what it was drawing, and the planner filled the gap from the look
guide ("the warrior … carries a long straight sword and bow case"; "He" for Gordafarid).

**D. Edits never say who the person is.** View prompts say "the same face, hair and build as image 1",
never "a young woman" or "a beard reaching the chest". The model guesses from the picture: beards
change length; a woman in armour drifts to a man.

**E. One view list for every object.** Front, side, back, top and detail for a mace, a bow, a lasso and
a horse alike. A flat object looks the same from front, back and side; a horse's top view from a
side-on hero is beyond the edit model.

**F. The judge does not check the belonging in actions, and is lenient.** Actions check the character's
never list, not the belonging's ("never an axe blade" was not checked); the 7B judge passed most of
these images.

## Issue by issue

| What the owner saw | Cause |
|---|---|
| Rostam's turnaround: clothes differ, most of all from behind | A; and the hero never shows the back, so the model invents it with only the broken text |
| Outfits and expressions: beard sizes differ | D; the beard is never named, and the close-up crop changes how long it looks |
| Rostam's mace is not a bull's head (the Shahnameh's *gorz-e gāvsar*) | B: our prompt, not the image model or the planner; in 2D it became an axe (C, and F let it through) |
| Sohrab's armlet on different arms, and on the wrists | the planner shortened "on his right upper arm" to "onyx armlet"; edits flip sides when a pose turns; his armour covers the upper arm, so the model moved it to both wrists |
| Gordafarid has a moustache in poses | D (nothing says she is a woman) and A (her mail veil was cut) |
| Gordafarid's bow action shows half a bow | C (the bow was not anchored to image 2); a standing "holds and uses" pose for a bow taller than her reach, with no pose for drawing it |
| The bow's views and the 2D lasso's views are all the same | E |
| Places have only one picture | places do get three views, but the World page shows only the hero; the views made before D-040 asked for "the same face and hair"; there is no place page like a character page |
| 2D Rostam's actions: tools pass through him, a sword appears | C and B |
| 2D Rakhsh: wrong top view, red dots in the detail | B (the hero had no dapples or saddle; the detail view had the details text and added them) and E |

## Fix order agreed for the design

1. A, B, C, D (prompt code) with tests that would have caught each: every garment survives, an object's
   details reach the prompt, the reference roles are never cut, gender and beard are always stated.
2. E: views per kind of object (flat, long weapon, animal), an animal turnaround like a character's.
3. F: the belonging's checks in actions, "the same object as image 2", a stricter judge for actions.
4. Elements (clothing, jewellery, marks) and a place page with all its views.
5. Weapon poses for actions from the mannequin library (drawing a bow, swinging a mace).
