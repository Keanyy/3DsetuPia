"""3DsetuPia - pieces shared by the OrcaSlicer plugin and the desktop program.

Settings storage (API keys never leave this PC and are never sent to the page),
and the "measure -> rules -> AI -> safety filter" pipeline that turns model
measurements and current settings into reviewed suggestions.
"""

import json
import os

import numpy as np

from .rules import propose, INTENTS  # bundle:strip
from .safety import validate  # bundle:strip
from .prompt import build_messages, parse_response, RESPONSE_SCHEMA  # bundle:strip
from .providers import PROVIDERS, ProviderError, chat_json, permission_url  # bundle:strip
from .i18n import msg  # bundle:strip

SETTINGS_FILE = "ayarci_settings.json"
LAST_RUN_FILE = "ayarci_last_run.json"


def _plain(obj):
    """Convert numpy scalars/arrays and tuples to JSON-safe Python values."""
    if isinstance(obj, dict):
        return {str(k): _plain(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_plain(v) for v in obj]
    if isinstance(obj, np.generic):
        return obj.item()
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    return obj


class Store:
    """Settings + last-run log in a private folder (Orca's plugin storage or %APPDATA%\\3DsetuPia)."""

    def __init__(self, folder):
        self.folder = folder
        self.path = os.path.join(folder, SETTINGS_FILE) if folder else None

    def load(self):
        data = {"provider": "none", "providers": {}, "lang": ""}
        if self.path and os.path.isfile(self.path):
            try:
                with open(self.path, "r", encoding="utf-8") as fh:
                    loaded = json.load(fh)
                if isinstance(loaded, dict):
                    data.update(loaded)
            except Exception:
                pass
        return data

    def save(self, data):
        if not self.path:
            return False
        os.makedirs(self.folder, exist_ok=True)
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False, indent=1)
        os.replace(tmp, self.path)
        return True

    def write_last_run(self, data):
        if not self.folder:
            return
        try:
            with open(os.path.join(self.folder, LAST_RUN_FILE), "w", encoding="utf-8") as fh:
                json.dump(_plain(data), fh, ensure_ascii=False, indent=1)
        except Exception:
            pass


def active_config(settings):
    pid = settings.get("provider") or "none"
    per = (settings.get("providers") or {}).get(pid, {})
    return {"provider": pid, "base_url": per.get("base_url", ""), "api_key": per.get("api_key", ""),
            "model": per.get("model", "")}


def masked_settings(settings):
    """What the page may see: never the API key itself."""
    out = {"provider": settings.get("provider") or "none", "lang": settings.get("lang", ""),
           "providers": {}}
    for pid, per in (settings.get("providers") or {}).items():
        key = per.get("api_key", "")
        out["providers"][pid] = {"base_url": per.get("base_url", ""), "model": per.get("model", ""),
                                 "has_key": bool(key), "key_hint": ("…" + key[-4:]) if len(key) >= 8 else "",
                                 "tested": per.get("tested", False)}
    return out


def update_settings(settings, message):
    """Apply a 'save_settings' message from the page to the stored settings dict."""
    pid = message.get("provider") or "none"
    if pid not in PROVIDERS:
        pid = "none"
    per_all = settings.setdefault("providers", {})
    per = per_all.setdefault(pid, {})
    if "base_url" in message:
        per["base_url"] = str(message.get("base_url") or "").strip()
    if "model" in message:
        per["model"] = str(message.get("model") or "").strip()
    new_key = message.get("api_key")
    if isinstance(new_key, str) and new_key.strip():
        per["api_key"] = new_key.strip()
        per["tested"] = False
    if message.get("clear_key"):
        per["api_key"] = ""
        per["tested"] = False
    settings["provider"] = pid
    return settings


def provider_error_text(lang, exc, cfg):
    host = permission_url(cfg)
    if exc.kind == "permission":
        return msg(lang, "err_permission", host=host)
    if exc.kind == "auth":
        return msg(lang, "err_auth")
    if exc.kind == "network":
        return msg(lang, "err_network", host=host, detail=str(exc))
    if exc.kind == "model":
        return msg(lang, "err_model", detail=str(exc))
    if exc.kind == "config":
        return msg(lang, "err_" + str(exc)) if str(exc) in ("missing_key", "missing_url", "bad_url",
                                                             "missing_model") else str(exc)
    if str(exc) == "refusal":
        return msg(lang, "err_refusal")
    return msg(lang, "err_generic", detail=str(exc))


def suggest(analysis, ctx, cfg, use_ai=True, progress=None):
    """Rules (+ AI when configured) -> safety filter.

    Returns dict(source, summary, changes, rejected, baseline, proposals, warnings).
    """
    lang = ctx.get("lang", "tr")
    if ctx.get("intent") not in INTENTS:
        ctx["intent"] = "balanced"
    baseline = propose(analysis, ctx)
    warnings = []
    source = "rules"
    summary = msg(lang, "rules_summary")
    proposals = baseline
    if use_ai and cfg["provider"] != "none":
        if progress:
            progress(msg(lang, "asking_ai", name=PROVIDERS[cfg["provider"]]["label"][lang]))
        system, user = build_messages(analysis, ctx, baseline)
        try:
            reply = chat_json(cfg, system, user, RESPONSE_SCHEMA)
            parsed = parse_response(reply)
            proposals = [dict(c, source="ai") for c in parsed["changes"]]
            summary = parsed["summary"] or summary
            source = "ai"
        except (ProviderError, ValueError) as exc:
            text = provider_error_text(lang, exc, cfg) if isinstance(exc, ProviderError) \
                else msg(lang, "err_parse", detail=str(exc))
            warnings.append(text + " " + msg(lang, "fallback_rules"))
    changes, rejected = validate(proposals, ctx, source)
    if source == "ai" and rejected:
        warnings.append(msg(lang, "rejected", n=len(rejected)))
    return {"source": source, "summary": summary, "changes": changes, "rejected": rejected,
            "baseline": baseline, "proposals": proposals, "warnings": warnings}
