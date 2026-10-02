"""The judge's answer schema and the verdict rules (design §8.3, decisions D-020)."""

from hone_frame.judging import answer_schema, verdicts

CHECKS = [{"name": "schema", "required": True}, {"name": "two words", "required": True},
          {"name": "style", "required": False}]  # fmt: skip


def test_any_check_name_is_a_key() -> None:
    schema = answer_schema(CHECKS)
    keys = schema.model_json_schema()["$defs"]["Checks"]["properties"]
    assert set(keys) == {"schema", "two words", "style"}
    answer = schema.model_validate({"description": "d", "overall": 0.6, "checks": {
        "schema": {"verdict": "pass", "score": 0.9}, "two words": {"verdict": "fail", "finding": "no"},
        "style": {"verdict": "uncertain"}}})  # fmt: skip
    ev = verdicts(answer, CHECKS, "judge")
    assert [(c.name, c.verdict) for c in ev.checks] == [
        ("schema", "pass"),
        ("two words", "fail"),
        ("style", "uncertain"),
    ]
    assert not ev.passed and not ev.uncertain


def test_a_check_without_an_answer_is_uncertain() -> None:
    answer = answer_schema(CHECKS[:1]).model_validate(
        {"description": "d", "overall": 0.5, "checks": {"schema": {"verdict": "pass"}}}
    )
    ev = verdicts(answer, CHECKS[:2], "judge")
    assert (
        ev.checks[1].verdict == "uncertain" and ev.checks[1].finding == "the judge did not answer this check"
    )
    assert ev.uncertain and not ev.passed
