import json

import pytest

import meshes as M
from ayarci import geometry as g, rules, prompt
from fixtures import ctx


def test_prompt_contains_only_allowed_keys_and_no_mesh():
    c = ctx(intent="looks", note="hediye figür")
    an = g.analyze_plate([M.part("x", M.sphere(20))])
    system, user = prompt.build_messages(an, c, rules.propose(an, c))
    payload = json.loads(user.split("\n\n", 1)[1])
    keys = set(payload["settings_you_may_change"])
    assert "layer_height" in keys and "enable_support" in keys
    assert "hot_plate_temp" not in keys          # inactive plate
    assert "machine_start_gcode" not in keys
    assert "vertices" not in user and "triangles\": [" not in user
    assert payload["answer_language"] == "Turkish"
    assert "JSON" in system


def test_parse_response_variants():
    good = {"summary": "ok", "changes": [{"key": "wall_loops", "value": "3", "reason": "r"}]}
    assert prompt.parse_response(json.dumps(good))["changes"][0]["key"] == "wall_loops"
    fenced = "```json\n" + json.dumps(good) + "\n```"
    assert prompt.parse_response(fenced)["summary"] == "ok"
    chatty = "Sure! Here you go:\n" + json.dumps(good) + "\nHope it helps."
    assert len(prompt.parse_response(chatty)["changes"]) == 1
    with pytest.raises(ValueError):
        prompt.parse_response("no json here")
