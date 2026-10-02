"""A character with a belonging, shared by the change-0003 acceptance cases."""

import hone_frame as hf

ONE = hf.Selection(rounds=1)


def rostam(ws: hf.Workspace) -> hf.ProjectStore:
    p = ws.create_project("Rostam and Sohrab", style_pack="historical-epic")
    p.add_subject(
        "character",
        "Rostam",
        description="Rostam, the champion of Iran",
        fields={"appearance": "weathered face, thick dark beard", "outfits": "tiger-hide coat"},
        states=[{"name": "Feast", "kind": "outfit", "description": "a silk robe"}],
    )
    p.add_subject("asset", "Mace", description="a bull-headed mace", owner="char_001")
    p.add_subject("environment", "White Fortress", description="a white stone fortress")
    return p
