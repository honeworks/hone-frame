"""AC-23: actions wait for their belongings, which are made first in the same request (change 0004)."""

import hone_frame as hf


def test_belongings_are_made_before_their_actions(rostam_project: hf.ProjectStore) -> None:
    rostam = rostam_project.subjects("character")[0]
    plan = rostam_project.plan(hf.CharacterPacks(subject_id=rostam.id, packs=["actions"]))
    order = [o.id for o in plan.outputs]
    for out in plan.outputs:
        for dep in out.depends_on:
            assert order.index(dep.output) < order.index(out.id), f"{out.item} waits for a later output"
    actions = [
        o
        for o in plan.outputs
        if o.pack == "actions" and o.prompt_inputs.get("action", "").startswith("Rostam holds")
    ]
    assets = {o.id: o.item for o in plan.outputs if o.pack == "assets"}
    assert actions and set(assets.values()) == {"Rostam's mace", "Rostam's lasso"}
    assert all(any(d.output in assets and d.role == "object" for d in a.depends_on) for a in actions)
