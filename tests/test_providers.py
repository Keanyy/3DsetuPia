import pytest

import fake_server
from ayarci import providers as P
from ayarci.prompt import RESPONSE_SCHEMA, parse_response


@pytest.fixture
def server():
    srv, state, url = fake_server.start()
    yield state, url
    srv.shutdown()


def test_resolve_rules():
    with pytest.raises(P.ProviderError) as e:
        P.resolve({"provider": "openai", "api_key": ""})
    assert str(e.value) == "missing_key"
    eff = P.resolve({"provider": "ollama"})
    assert eff["base_url"] == "http://localhost:11434/v1" and eff["api_key"] == ""
    # fixed-URL providers ignore a user supplied URL
    assert P.resolve({"provider": "openai", "api_key": "k", "base_url": "http://evil"})["base_url"] \
        == "https://api.openai.com/v1"
    with pytest.raises(P.ProviderError):
        P.resolve({"provider": "custom", "base_url": "ftp://x"})


def test_meta_greys_out_fields():
    meta = {m["id"]: m for m in P.public_meta("tr")}
    assert meta["ollama"]["needs_key"] is False and meta["ollama"]["url_editable"] is True
    assert meta["anthropic"]["needs_key"] is True and meta["anthropic"]["url_editable"] is False
    assert meta["none"]["needs_key"] is False and meta["none"]["url_editable"] is False


def test_openai_compatible(server):
    state, url = server
    cfg = {"provider": "custom", "base_url": url + "/v1", "api_key": "sk-test", "model": "model-a"}
    assert P.list_models(cfg) == ["model-a", "model-b"]
    reply = P.chat_json(cfg, "sys", "user", RESPONSE_SCHEMA)
    assert parse_response(reply)["summary"] == "Test özeti"
    post = [r for r in state.requests if r[0] == "POST"][-1]
    assert post[2]["Authorization"] == "Bearer sk-test"
    assert post[3]["response_format"] == {"type": "json_object"}


def test_openai_json_mode_fallback(server):
    state, url = server
    state.reject_json_mode = True
    cfg = {"provider": "custom", "base_url": url + "/v1", "model": "model-a"}
    reply = P.chat_json(cfg, "sys", "user", RESPONSE_SCHEMA)
    assert "changes" in reply
    posts = [r for r in state.requests if r[0] == "POST"]
    assert "response_format" not in posts[-1][3]


def test_auth_error_kind(server):
    state, url = server
    state.status = 401
    cfg = {"provider": "custom", "base_url": url + "/v1", "api_key": "x", "model": "m"}
    with pytest.raises(P.ProviderError) as e:
        P.list_models(cfg)
    assert e.value.kind == "auth"


def test_network_error_kind():
    cfg = {"provider": "custom", "base_url": "http://127.0.0.1:9/v1", "model": "m"}
    with pytest.raises(P.ProviderError) as e:
        P.list_models(cfg, timeout=2)
    assert e.value.kind == "network"


def test_anthropic_sdk_path(server, monkeypatch):
    state, url = server
    monkeypatch.setitem(P.PROVIDERS["anthropic"], "base_url", url)
    cfg = {"provider": "anthropic", "api_key": "sk-ant-test", "model": ""}
    assert P.list_models(cfg) == ["claude-opus-5-5"]
    reply = P.chat_json(cfg, "sys", "user", RESPONSE_SCHEMA)
    assert parse_response(reply)["changes"][0]["key"] == "wall_loops"
    post = [r for r in state.requests if r[0] == "POST"][-1]
    headers = {k.lower(): v for k, v in post[2].items()}
    body = post[3]
    assert headers.get("x-api-key") == "sk-ant-test" or headers.get("authorization") == "Bearer sk-ant-test"
    assert "server-side-fallback-2026-07-01" in headers.get("anthropic-beta", "")
    assert body["model"] == "claude-opus-5-5"
    assert body["fallbacks"] == "default"
    assert body["output_config"]["format"]["type"] == "json_schema"
    assert body["output_config"]["effort"] == "high"


def test_anthropic_auth_error(server, monkeypatch):
    state, url = server
    state.status = 401
    monkeypatch.setitem(P.PROVIDERS["anthropic"], "base_url", url)
    with pytest.raises(P.ProviderError) as e:
        P.chat_json({"provider": "anthropic", "api_key": "bad"}, "s", "u", RESPONSE_SCHEMA)
    assert e.value.kind == "auth"
