"""3DsetuPia - AI providers.

* "none": no AI, local rules only (always works, offline).
* "anthropic": Claude through the official `anthropic` SDK.
* everything else: any OpenAI-compatible endpoint (OpenAI, Google Gemini, OpenRouter,
  DeepSeek, Groq, Mistral, local Ollama / LM Studio, or a custom URL).

UI rules (see ui.html): `needs_key` decides whether the key box is enabled or greyed
out, `url_editable` decides whether the address box is editable or greyed out.
"""

import json
import re
import ssl
import urllib.error
import urllib.request

PROVIDERS = {
    "none": {"label": {"tr": "Yapay zekâ yok (yerel kurallar)", "en": "No AI (local rules)"},
             "kind": "none", "base_url": "", "needs_key": False, "url_editable": False,
             "default_model": "", "key_page": "",
             "help": {"tr": "İnternet ve anahtar gerekmez. Ayarlar yerleşik kurallarla hazırlanır.",
                      "en": "No internet or key needed. Settings come from built-in rules."}},
    "anthropic": {"label": {"tr": "Anthropic Claude", "en": "Anthropic Claude"},
                  "kind": "anthropic", "base_url": "https://api.anthropic.com", "needs_key": True,
                  "url_editable": False, "default_model": "claude-opus-5-5",
                  "key_page": "https://platform.claude.com",
                  "help": {"tr": "Anahtarı Claude Console'da 'API Keys' bölümünden oluşturun.",
                           "en": "Create a key under 'API Keys' in the Claude Console."}},
    "openai": {"label": {"tr": "OpenAI", "en": "OpenAI"}, "kind": "openai",
               "base_url": "https://api.openai.com/v1", "needs_key": True, "url_editable": False,
               "default_model": "", "key_page": "https://platform.openai.com/api-keys",
               "help": {"tr": "platform.openai.com → API keys.", "en": "platform.openai.com → API keys."}},
    "gemini": {"label": {"tr": "Google Gemini", "en": "Google Gemini"}, "kind": "openai",
               "base_url": "https://generativelanguage.googleapis.com/v1beta/openai",
               "needs_key": True, "url_editable": False, "default_model": "",
               "key_page": "https://aistudio.google.com/apikey",
               "help": {"tr": "Google AI Studio → Get API key.", "en": "Google AI Studio → Get API key."}},
    "openrouter": {"label": {"tr": "OpenRouter (çok sayıda model)", "en": "OpenRouter (many models)"},
                   "kind": "openai", "base_url": "https://openrouter.ai/api/v1", "needs_key": True,
                   "url_editable": False, "default_model": "", "key_page": "https://openrouter.ai/keys",
                   "help": {"tr": "Tek anahtarla birçok sağlayıcının modeli.",
                            "en": "One key for models from many providers."}},
    "deepseek": {"label": {"tr": "DeepSeek", "en": "DeepSeek"}, "kind": "openai",
                 "base_url": "https://api.deepseek.com", "needs_key": True, "url_editable": False,
                 "default_model": "", "key_page": "https://platform.deepseek.com/api_keys",
                 "help": {"tr": "platform.deepseek.com → API keys.", "en": "platform.deepseek.com → API keys."}},
    "groq": {"label": {"tr": "Groq", "en": "Groq"}, "kind": "openai",
             "base_url": "https://api.groq.com/openai/v1", "needs_key": True, "url_editable": False,
             "default_model": "", "key_page": "https://console.groq.com/keys",
             "help": {"tr": "console.groq.com → API Keys.", "en": "console.groq.com → API Keys."}},
    "mistral": {"label": {"tr": "Mistral", "en": "Mistral"}, "kind": "openai",
                "base_url": "https://api.mistral.ai/v1", "needs_key": True, "url_editable": False,
                "default_model": "", "key_page": "https://console.mistral.ai/api-keys",
                "help": {"tr": "console.mistral.ai → API Keys.", "en": "console.mistral.ai → API Keys."}},
    "ollama": {"label": {"tr": "Ollama (bilgisayarında, ücretsiz)", "en": "Ollama (on your PC, free)"},
               "kind": "openai", "base_url": "http://localhost:11434/v1", "needs_key": False,
               "url_editable": True, "default_model": "", "key_page": "https://ollama.com/download",
               "help": {"tr": "Anahtar gerekmez. Ollama'yı kurup bir model indirin (ör. 'ollama pull qwen3').",
                        "en": "No key needed. Install Ollama and pull a model (e.g. 'ollama pull qwen3')."}},
    "lmstudio": {"label": {"tr": "LM Studio (bilgisayarında, ücretsiz)", "en": "LM Studio (on your PC, free)"},
                 "kind": "openai", "base_url": "http://localhost:1234/v1", "needs_key": False,
                 "url_editable": True, "default_model": "", "key_page": "https://lmstudio.ai",
                 "help": {"tr": "Anahtar gerekmez. LM Studio'da 'Local Server'ı başlatın.",
                          "en": "No key needed. Start the 'Local Server' in LM Studio."}},
    "custom": {"label": {"tr": "Özel (OpenAI uyumlu adres)", "en": "Custom (OpenAI-compatible URL)"},
               "kind": "openai", "base_url": "", "needs_key": False, "key_optional": True,
               "url_editable": True, "default_model": "", "key_page": "",
               "help": {"tr": "OpenAI uyumlu herhangi bir servis. Anahtar isteğe bağlı.",
                        "en": "Any OpenAI-compatible service. Key optional."}},
}
PROVIDER_ORDER = ["none", "anthropic", "openai", "gemini", "openrouter", "deepseek", "groq",
                  "mistral", "ollama", "lmstudio", "custom"]

# Claude models that accept the server-side refusal fallback ("default" form).
_FALLBACK_MODELS = ("claude-opus-5-5", "claude-opus-5", "claude-fable-5-1", "claude-sonnet-5-5")
_EFFORT_MODELS = re.compile(r"^claude-(opus|sonnet|fable|haiku)-5|^claude-opus-4-[5-8]")


class ProviderError(Exception):
    def __init__(self, message, kind="error"):
        super().__init__(message)
        self.kind = kind   # "permission", "auth", "network", "model", "error"


def public_meta(lang="tr"):
    out = []
    for pid in PROVIDER_ORDER:
        p = PROVIDERS[pid]
        out.append({"id": pid, "label": p["label"].get(lang, p["label"]["en"]),
                    "base_url": p["base_url"], "needs_key": p["needs_key"],
                    "key_optional": p.get("key_optional", False),
                    "url_editable": p["url_editable"], "default_model": p["default_model"],
                    "key_page": p["key_page"], "help": p["help"].get(lang, p["help"]["en"])})
    return out


def resolve(cfg):
    """cfg: {"provider", "base_url", "api_key", "model"} -> effective settings or ProviderError."""
    pid = cfg.get("provider") or "none"
    if pid not in PROVIDERS:
        raise ProviderError("Unknown provider: %s" % pid)
    p = PROVIDERS[pid]
    base = (cfg.get("base_url") or "").strip() if p["url_editable"] else p["base_url"]
    base = base or p["base_url"]
    key = (cfg.get("api_key") or "").strip()
    model = (cfg.get("model") or "").strip() or p["default_model"]
    if p["kind"] != "none":
        if not base:
            raise ProviderError("missing_url", "config")
        if not re.match(r"^https?://", base):
            raise ProviderError("bad_url", "config")
        if p["needs_key"] and not key:
            raise ProviderError("missing_key", "config")
    return {"id": pid, "kind": p["kind"], "base_url": base.rstrip("/"), "api_key": key, "model": model}


def _is_permission_error(exc):
    s = ("%s %s" % (type(exc).__name__, exc)).lower()
    return isinstance(exc, PermissionError) or "permission" in s or "audit" in s or "not allowed" in s


# Load CA certificates and the Anthropic SDK while the plugin is being loaded: OrcaSlicer
# can show its permission dialog synchronously only at load time, so file reads done
# here never hit the "denied on first try" path of the background worker.
try:
    import certifi as _certifi
    with open(_certifi.where(), "r", encoding="ascii") as _fh:
        _CA_DATA = _fh.read()
except Exception:
    _CA_DATA = None
try:
    import anthropic as _anthropic
    _ANTHROPIC_HTTP = _anthropic.DefaultHttpxClient()
except Exception:
    _anthropic = None
    _ANTHROPIC_HTTP = None


def _ssl_context():
    if _CA_DATA:
        try:
            return ssl.create_default_context(cadata=_CA_DATA)
        except Exception:
            pass
    return ssl.create_default_context()


def _http_json(method, url, headers, body=None, timeout=120):
    data = None if body is None else json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    req.add_header("User-Agent", "3DsetuPia")
    for k, v in headers.items():
        req.add_header(k, v)
    ctx = _ssl_context() if url.startswith("https://") else None
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
            raw = resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        detail = ""
        try:
            detail = exc.read().decode("utf-8", "replace")[:400]
        except Exception:
            pass
        kind = "auth" if exc.code in (401, 403) else ("model" if exc.code == 404 else "error")
        raise ProviderError("HTTP %s: %s" % (exc.code, detail or exc.reason), kind)
    except urllib.error.URLError as exc:
        if _is_permission_error(exc.reason if hasattr(exc, "reason") else exc):
            raise ProviderError(str(exc), "permission")
        raise ProviderError("network: %s" % exc.reason, "network")
    except Exception as exc:  # audit hook denials surface here
        if _is_permission_error(exc):
            raise ProviderError(str(exc), "permission")
        raise ProviderError("network: %s" % exc, "network")
    try:
        return json.loads(raw)
    except ValueError:
        raise ProviderError("invalid JSON from server: %s" % raw[:200])


def _oa_headers(eff):
    h = {}
    if eff["api_key"]:
        h["Authorization"] = "Bearer " + eff["api_key"]
    if eff["id"] == "openrouter":
        h["HTTP-Referer"] = "https://github.com/ayarci"
        h["X-Title"] = "3DsetuPia"
    return h


# ---------------------------------------------------------------- Anthropic (SDK)

def _anthropic_client(eff, timeout):
    if _anthropic is None:
        raise ProviderError("anthropic package missing", "error")
    kwargs = dict(api_key=eff["api_key"], base_url=eff["base_url"], timeout=timeout, max_retries=1)
    if _ANTHROPIC_HTTP is not None:
        kwargs["http_client"] = _ANTHROPIC_HTTP
    return _anthropic, _anthropic.Anthropic(**kwargs)


def _anthropic_error(anthropic, exc):
    if isinstance(exc, anthropic.AuthenticationError):
        return ProviderError("auth: %s" % getattr(exc, "message", exc), "auth")
    if isinstance(exc, anthropic.PermissionDeniedError):
        return ProviderError("auth: %s" % getattr(exc, "message", exc), "auth")
    if isinstance(exc, anthropic.NotFoundError):
        return ProviderError("model: %s" % getattr(exc, "message", exc), "model")
    if isinstance(exc, anthropic.RateLimitError):
        return ProviderError("rate limit: %s" % getattr(exc, "message", exc), "error")
    if isinstance(exc, anthropic.APIStatusError):
        return ProviderError("HTTP %s: %s" % (exc.status_code, getattr(exc, "message", exc)), "error")
    if isinstance(exc, anthropic.APIConnectionError):
        cause = exc.__cause__ or exc
        if _is_permission_error(cause):
            return ProviderError(str(cause), "permission")
        return ProviderError("network: %s" % cause, "network")
    if _is_permission_error(exc):
        return ProviderError(str(exc), "permission")
    return ProviderError(str(exc))


def _anthropic_models(eff, timeout):
    anthropic, client = _anthropic_client(eff, timeout)
    try:
        return [m.id for m in client.models.list(limit=100)]
    except Exception as exc:
        raise _anthropic_error(anthropic, exc)


def _anthropic_chat(eff, system, user, schema, timeout):
    anthropic, client = _anthropic_client(eff, timeout)
    model = eff["model"] or PROVIDERS["anthropic"]["default_model"]
    output_config = {"format": {"type": "json_schema", "schema": schema}}
    if _EFFORT_MODELS.match(model):
        output_config["effort"] = "high"
    kwargs = dict(model=model, max_tokens=16000, system=system,
                  messages=[{"role": "user", "content": user}], output_config=output_config)
    attempts = []
    if model in _FALLBACK_MODELS:
        attempts.append("fallback")
    attempts += ["plain", "no_config"]
    last = None
    for mode in attempts:
        try:
            if mode == "fallback":
                resp = client.beta.messages.create(betas=["server-side-fallback-2026-07-01"],
                                                   fallbacks="default", **kwargs)
            elif mode == "plain":
                resp = client.messages.create(**kwargs)
            else:
                plain = dict(kwargs)
                plain.pop("output_config", None)
                resp = client.messages.create(**plain)
        except anthropic.BadRequestError as exc:   # e.g. older model without these options
            last = exc
            continue
        except Exception as exc:
            raise _anthropic_error(anthropic, exc)
        if resp.stop_reason == "refusal":
            raise ProviderError("refusal", "error")
        texts = [b.text for b in resp.content if getattr(b, "type", "") == "text"]
        if not texts:
            raise ProviderError("empty response")
        return "".join(texts)
    raise _anthropic_error(anthropic, last)


# ---------------------------------------------------------------- OpenAI-compatible

def _oa_models(eff, timeout):
    data = _http_json("GET", eff["base_url"] + "/models", _oa_headers(eff), timeout=timeout)
    items = data.get("data") if isinstance(data, dict) else data
    ids = []
    for m in items or []:
        mid = m.get("id") if isinstance(m, dict) else m
        if mid:
            ids.append(str(mid).replace("models/", "", 1) if eff["id"] == "gemini" else str(mid))
    return sorted(set(ids))


def _oa_chat(eff, system, user, timeout):
    if not eff["model"]:
        raise ProviderError("missing_model", "config")
    body = {"model": eff["model"],
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "response_format": {"type": "json_object"}}
    try:
        data = _http_json("POST", eff["base_url"] + "/chat/completions", _oa_headers(eff), body, timeout)
    except ProviderError as exc:
        if exc.kind == "error" and "HTTP 4" in str(exc):
            body.pop("response_format", None)   # some servers do not support JSON mode
            data = _http_json("POST", eff["base_url"] + "/chat/completions", _oa_headers(eff), body, timeout)
        else:
            raise
    try:
        msg = data["choices"][0]["message"]
        content = msg.get("content")
        if isinstance(content, list):
            content = "".join(part.get("text", "") for part in content if isinstance(part, dict))
        return content or ""
    except (KeyError, IndexError, TypeError):
        raise ProviderError("unexpected response: %s" % json.dumps(data)[:300])


# ---------------------------------------------------------------- public API

def list_models(cfg, timeout=20):
    eff = resolve(cfg)
    if eff["kind"] == "none":
        return []
    if eff["kind"] == "anthropic":
        return _anthropic_models(eff, timeout)
    return _oa_models(eff, timeout)


def chat_json(cfg, system, user, schema, timeout=240):
    eff = resolve(cfg)
    if eff["kind"] == "none":
        raise ProviderError("no provider", "config")
    if eff["kind"] == "anthropic":
        return _anthropic_chat(eff, system, user, schema, timeout)
    return _oa_chat(eff, system, user, timeout)


def permission_url(cfg):
    """The URL whose host OrcaSlicer's permission prompt will name."""
    try:
        return resolve(cfg)["base_url"]
    except ProviderError:
        return ""
