"""3DsetuPia - desktop program (Windows; the window is the system's Edge WebView2 via pywebview).

Give it a 3MF project (Bambu Studio, QIDI Studio, OrcaSlicer...), a settings-free 3MF,
or an STL/OBJ. It measures the model, prepares settings for the chosen printer and
writes a new, improved 3MF next to the original.

The page talks to Python with window.pywebview.api.post({command: ...}); answers come back
through window.__ayarciRecv(message). Slow work runs on one worker thread, in order.
"""

import json
import os
import queue
import subprocess
import sys
import threading
import traceback
import webbrowser

from .catalog import PAGES, PAGE_ORDER  # bundle:strip
from .providers import PROVIDERS, ProviderError, public_meta, list_models, resolve  # bundle:strip
from .assist import Store, active_config, masked_settings, update_settings, provider_error_text, _plain  # bundle:strip
from .engine import Engine, default_output  # bundle:strip
from .threemf import ProjectError  # bundle:strip
from .i18n import msg  # bundle:strip

APP_VERSION = "1.1.0"
REPO_URL = "https://github.com/Keanyy/3DsetuPia"
SPONSOR_URL = "https://github.com/sponsors/Keanyy"
FILE_TYPES = ("3D (*.3mf;*.stl;*.obj)", "3MF (*.3mf)", "STL (*.stl)", "OBJ (*.obj)")


def data_dir():
    base = os.environ.get("APPDATA") or os.path.expanduser("~")
    return os.path.join(base, "3DsetuPia")


def system_lang():
    try:
        import ctypes
        lang_id = ctypes.windll.kernel32.GetUserDefaultUILanguage()
        return "tr" if (lang_id & 0x3FF) == 0x1F else "en"
    except Exception:
        import locale
        code = (locale.getlocale()[0] or "")
        return "tr" if code.lower().startswith("tr") else "en"


def resource(name):
    """File shipped next to the module (works from source and from the PyInstaller bundle)."""
    base = getattr(sys, "_MEIPASS", None)
    if base:
        cand = os.path.join(base, "ayarci", name)
        if os.path.isfile(cand):
            return cand
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), name)


class App:
    def __init__(self, first_file=None):
        self.folder = data_dir()
        os.makedirs(self.folder, exist_ok=True)
        self.store = Store(self.folder)
        self.settings = self.store.load()
        if not self.settings.get("lang"):
            self.settings["lang"] = system_lang()
        self.window = None
        self.engine = None
        self.job = None
        self.first_file = first_file
        self.jobs = queue.Queue()
        self.printers_all = False
        threading.Thread(target=self._worker, daemon=True).start()

    # ------------------------------------------------------------ plumbing
    def lang(self):
        return self.settings.get("lang") or "tr"

    def send(self, data):
        if self.window is None:
            return
        try:
            payload = json.dumps(_plain(data), ensure_ascii=False)
            self.window.evaluate_js("window.__ayarciRecv(%s)" % payload)
        except Exception:
            pass

    def post(self, message):
        """Called by the page (pywebview js_api)."""
        message = dict(message) if isinstance(message, dict) else {}
        cmd = message.get("command")
        try:
            if cmd == "init":
                self.send(self._init_state())
                self.jobs.put({"command": "warm_up"})
                if self.first_file:
                    self.jobs.put({"command": "open_path", "path": self.first_file})
                    self.first_file = None
            elif cmd == "set_lang":
                self.settings["lang"] = "tr" if message.get("lang") == "tr" else "en"
                self.store.save(self.settings)
            elif cmd == "save_settings":
                update_settings(self.settings, message)
                ok = self.store.save(self.settings)
                self.send({"command": "settings_saved", "ok": ok, "settings": masked_settings(self.settings)})
            elif cmd == "open_url":
                url = str(message.get("url") or "")
                if url.startswith("https://") or url.startswith("http://localhost"):
                    webbrowser.open(url)
            elif cmd == "show_folder":
                path = str(message.get("path") or "")
                if os.path.isfile(path):
                    subprocess.Popen(["explorer", "/select,", os.path.normpath(path)])
            elif cmd == "open_in_slicer":
                self._open_in_slicer(str(message.get("path") or ""))
            elif cmd == "open_dialog":
                threading.Thread(target=self._open_dialog, daemon=True).start()
            elif cmd in ("open_path", "analyze", "save", "test", "filaments", "printers"):
                self.jobs.put(message)
        except Exception as exc:
            self.send({"command": "error", "text": "%s: %s" % (type(exc).__name__, exc)})
        return True

    def _worker(self):
        while True:
            item = self.jobs.get()
            cmd = item.get("command")
            try:
                if cmd == "warm_up":
                    self._warm_up()
                elif cmd == "open_path":
                    self._open(item.get("path"))
                elif cmd == "analyze":
                    self._analyze(item)
                elif cmd == "save":
                    self._save_dialog(item)
                elif cmd == "test":
                    self._test()
                elif cmd == "filaments":
                    self._filaments(item.get("printer_id", ""))
                elif cmd == "printers":
                    self.printers_all = bool(item.get("all"))
                    self.send({"command": "printers", "list": self.engine.printers(not self.printers_all),
                               "ready": True})
            except ProjectError as exc:
                self.send({"command": "proposals" if cmd == "analyze" else "error", "ok": False,
                           "text": self._project_error(exc)})
            except Exception as exc:
                trace = traceback.format_exc()
                self._log_error(trace)
                self.send({"command": "proposals" if cmd == "analyze" else "error", "ok": False,
                           "text": "%s: %s" % (type(exc).__name__, exc)})

    def _log_error(self, text):
        try:
            with open(os.path.join(self.folder, "ayarci_error.log"), "a", encoding="utf-8") as fh:
                fh.write(text + "\n")
        except OSError:
            pass

    def _project_error(self, exc):
        lang = self.lang()
        code = exc.code
        known = {"unsupported", "bad_mesh", "bad_settings", "need_target", "profile_missing", "no_model"}
        if code == "multi_nozzle_target":
            return msg(lang, "multi_nozzle_target", name=exc.detail)
        if code == "no_model":
            return msg(lang, "no_model")
        if code in known:
            return msg(lang, code, detail=exc.detail)
        return msg(lang, "open_failed", detail=str(exc))

    # ------------------------------------------------------------ state
    def _init_state(self):
        lang = self.lang()
        slicers = []
        try:
            from .profiles import discover  # bundle:strip
            slicers = [{"id": s["id"], "label": s["label"], "version": s["version"], "exe": bool(s["exe"])}
                       for s in discover()]
        except Exception:
            pass
        return {"command": "init", "version": APP_VERSION, "lang": lang, "providers": public_meta(lang),
                "settings": masked_settings(self.settings), "pages": {k: v.get(lang, v["en"]) for k, v in PAGES.items()},
                "page_order": PAGE_ORDER, "repo": REPO_URL, "sponsor": SPONSOR_URL, "data_dir": self.folder,
                "slicers": slicers,
                "last_target": self.settings.get("last_target", "")}

    def _warm_up(self):
        if self.engine is None:
            self.engine = Engine(os.path.join(self.folder, "cache"))
        self.send({"command": "printers", "list": self.engine.printers(True), "ready": False})
        self.engine.warm_up()
        self.send({"command": "printers", "list": self.engine.printers(not self.printers_all), "ready": True})

    # ------------------------------------------------------------ files
    def _open_dialog(self):
        import webview
        kind = getattr(getattr(webview, "FileDialog", None), "OPEN", None) or webview.OPEN_DIALOG
        start = self.settings.get("last_dir") or os.path.join(os.path.expanduser("~"), "Desktop")
        try:
            result = self.window.create_file_dialog(kind, directory=start, allow_multiple=False,
                                                    file_types=FILE_TYPES)
        except Exception:
            result = self.window.create_file_dialog(kind, allow_multiple=False)
        if result:
            path = result[0] if isinstance(result, (list, tuple)) else result
            self.jobs.put({"command": "open_path", "path": path})

    def open_dropped(self, path):
        self.jobs.put({"command": "open_path", "path": path})

    def _open(self, path):
        if not path or not os.path.isfile(path):
            return
        if self.engine is None:
            self.engine = Engine(os.path.join(self.folder, "cache"))
        self.settings["last_dir"] = os.path.dirname(path)
        self.store.save(self.settings)
        lang = self.lang()
        self.send({"command": "progress", "text": msg(lang, "measuring")})
        self.job = self.engine.open(path)
        info = self.engine.describe(self.job, lang)
        text = msg(lang, "no_settings") if not info.get("has_settings") else ""
        self.send({"command": "file", "info": info, "text": text})

    def _filaments(self, printer_id):
        if not printer_id or "|" not in printer_id or self.engine is None:
            return
        self.send({"command": "filaments", "printer_id": printer_id,
                   "list": self.engine.filament_choices(printer_id)})

    # ------------------------------------------------------------ assistant
    def _analyze(self, item):
        lang = self.lang()
        if self.job is None:
            self.send({"command": "proposals", "ok": False, "text": msg(lang, "no_model")})
            return
        target = item.get("target") or ""
        if not target:
            self.send({"command": "proposals", "ok": False, "text": msg(lang, "need_target")})
            return
        if target != "same":
            self.settings["last_target"] = target
            self.store.save(self.settings)
        cfg = active_config(self.settings)
        result = self.engine.prepare(self.job, target, slot=item.get("slot") or None,
                                     filament=item.get("filament") or None,
                                     intent=item.get("intent", "balanced"), note=str(item.get("note", ""))[:500],
                                     lang=lang, provider_cfg=cfg, use_ai=bool(item.get("use_ai", True)),
                                     progress=lambda text: self.send({"command": "progress", "text": text}))
        log = result.pop("log", {})
        self.store.write_last_run(dict(log, file=self.job.path, target=target, changes=result["changes"],
                                       warnings=result["warnings"], provider=cfg["provider"], model=cfg["model"]))
        self.send(dict(result, command="proposals"))

    def _save_dialog(self, item):
        lang = self.lang()
        if self.job is None or not self.job.plan:
            self.send({"command": "saved", "ok": False, "text": msg(lang, "nothing")})
            return
        import webview
        kind = getattr(getattr(webview, "FileDialog", None), "SAVE", None) or webview.SAVE_DIALOG
        suggested = default_output(self.job.path)
        try:
            result = self.window.create_file_dialog(kind, directory=os.path.dirname(suggested),
                                                    save_filename=os.path.basename(suggested),
                                                    file_types=("3MF (*.3mf)",))
        except Exception:
            result = self.window.create_file_dialog(kind, save_filename=os.path.basename(suggested))
        if not result:
            self.send({"command": "saved", "ok": False, "text": ""})
            return
        path = result[0] if isinstance(result, (list, tuple)) else result
        if not path.lower().endswith(".3mf"):
            path += ".3mf"
        try:
            out = self.engine.save(self.job, item.get("ids", []), path)
        except ProjectError as exc:
            detail = msg(lang, "same_file") if exc.code == "same_file" else str(exc)
            self.send({"command": "saved", "ok": False, "text": msg(lang, "save_failed", detail=detail)})
            return
        except OSError as exc:
            self.send({"command": "saved", "ok": False, "text": msg(lang, "save_failed", detail=str(exc))})
            return
        self.send({"command": "saved", "ok": True, "path": out["path"], "open_with": self._slicer_for_output(),
                   "text": msg(lang, "saved_to", path=out["path"])})

    def _slicer_for_output(self):
        plan = self.job.plan if self.job else None
        if not plan or self.engine is None:
            return None
        app = plan.get("app")
        if app:
            name = app.split("-")[0]
            s = next((x for x in self.engine.slicers if x["app"] == name), None)
        else:
            flavor = plan["base"].flavor
            s = next((x for x in self.engine.slicers if x["id"] == flavor), None)
        if s and s.get("exe"):
            return {"id": s["id"], "label": s["label"]}
        return None

    def _open_in_slicer(self, path):
        info = self._slicer_for_output()
        s = next((x for x in (self.engine.slicers if self.engine else []) if info and x["id"] == info["id"]), None)
        if not s or not s.get("exe") or not os.path.isfile(path):
            self.send({"command": "notice", "text": msg(self.lang(), "slicer_missing")})
            return
        subprocess.Popen([s["exe"], path], close_fds=True)

    def _test(self):
        lang = self.lang()
        cfg = active_config(self.settings)
        try:
            if cfg["provider"] == "none":
                self.send({"command": "test_result", "ok": True, "models": [], "text": msg(lang, "test_none")})
                return
            resolve(cfg)
            models = list_models(cfg)
            per = self.settings.setdefault("providers", {}).setdefault(cfg["provider"], {})
            per["tested"] = True
            if not per.get("model") and models:
                default = PROVIDERS[cfg["provider"]]["default_model"]
                per["model"] = default if default in models else ""
            self.store.save(self.settings)
            self.send({"command": "test_result", "ok": True, "models": models[:300],
                       "settings": masked_settings(self.settings), "text": msg(lang, "test_ok", n=len(models))})
        except ProviderError as exc:
            self.send({"command": "test_result", "ok": False, "text": provider_error_text(lang, exc, cfg),
                       "kind": exc.kind})


def _hook_drop(app, window):
    """Accept files dropped on the window (pywebview DOM events give the full path)."""
    try:
        from webview.dom import DOMEventHandler
    except Exception:
        return

    def on_drop(event):
        files = ((event or {}).get("dataTransfer") or {}).get("files") or []
        for f in files:
            path = f.get("pywebviewFullPath")
            if path:
                app.open_dropped(path)
                break

    try:
        window.dom.document.events.dragover += DOMEventHandler(lambda e: None, True, True)
        window.dom.document.events.drop += DOMEventHandler(on_drop, True, True)
    except Exception:
        pass


def self_test(src, out_dir, target="same"):
    """--selftest: run the whole pipeline without a window and write a JSON report (checks a built .exe)."""
    os.makedirs(out_dir, exist_ok=True)
    report = {"version": APP_VERSION, "file": src, "target": target}
    try:
        engine = Engine(os.path.join(data_dir(), "cache"))
        report["slicers"] = [s["id"] for s in engine.slicers]
        report["printers"] = len(engine.printers())
        job = engine.open(src)
        report["describe"] = engine.describe(job, "tr")
        result = engine.prepare(job, target, lang="tr")
        result.pop("log", None)
        report["changes"] = [(c["key"], c["old"], c["new"]) for c in result["changes"]]
        report["notes"], report["warnings"] = result["notes"], result["warnings"]
        out = os.path.join(out_dir, "selftest_" + os.path.basename(default_output(src)))
        engine.save(job, [c["id"] for c in result["changes"]], out)
        report["output"] = out
        report["ok"] = True
    except Exception:
        report["ok"] = False
        report["error"] = traceback.format_exc()
    with open(os.path.join(out_dir, "selftest.json"), "w", encoding="utf-8") as fh:
        json.dump(_plain(report), fh, ensure_ascii=False, indent=1)
    return 0 if report["ok"] else 1


def _ui_test(app, window, report_path, target):
    """--uitest: drive the real page through the bridge (no screen access needed) and write what it shows."""
    import time
    report = {"steps": []}

    def js(code):
        return window.evaluate_js(code)

    def wait(code, timeout=90):
        end = time.time() + timeout
        while time.time() < end:
            try:
                if js(code):
                    return True
            except Exception:
                pass
            time.sleep(0.3)
        return False

    def snapshot(name):
        report["steps"].append({"step": name, "page": js(
            "({fname:document.getElementById('fname').textContent,"
            "file:document.getElementById('fileKv').innerText,"
            "targets:Array.prototype.map.call(document.getElementById('target').options,function(o){return o.value}),"
            "progress:document.getElementById('progress').hidden?'':document.getElementById('progress').innerText,"
            "summary:document.getElementById('summary').innerText,notes:document.getElementById('notes').innerText,"
            "warnings:document.getElementById('warnings').innerText,pages:document.getElementById('pages').innerText,"
            "checked:Array.prototype.filter.call(document.querySelectorAll('#pages input[type=checkbox]'),"
            "function(x){return x.checked}).length,mode:document.getElementById('modeText').textContent})")})

    try:
        report["init"] = wait("document.getElementById('provider').options.length>0")
        report["file"] = wait("document.getElementById('fname').textContent.length>0")
        report["printers"] = wait("!Array.prototype.some.call(document.getElementById('target').options,"
                                  "function(o){return o.disabled&&o.value===''})", 300)
        snapshot("opened")
        for tgt in ("same", target):
            if not tgt:
                continue
            js("var s=document.getElementById('target');s.value=%s;s.dispatchEvent(new Event('change'))" % json.dumps(tgt))
            time.sleep(1.5)
            js("document.getElementById('result').hidden=true;document.getElementById('go').click()")
            ok = wait("!document.getElementById('result').hidden||document.getElementById('progress').className"
                      ".indexOf('bad')>=0", 300)
            snapshot("prepared:%s:%s" % (tgt, ok))
            if app.job and app.job.plan:
                ids = js("Array.prototype.filter.call(document.querySelectorAll('#pages input[type=checkbox]'),"
                         "function(x){return x.checked}).map(function(x){return Number(x.getAttribute('data-id'))})")
                out = os.path.splitext(report_path)[0] + "_%s.3mf" % tgt.replace("|", "_").replace(" ", "_")
                app.engine.save(app.job, ids or [], out)
                report["steps"][-1]["saved"] = out
        report["ok"] = True
    except Exception:
        report["ok"] = False
        report["error"] = traceback.format_exc()
    with open(report_path, "w", encoding="utf-8") as fh:
        json.dump(_plain(report), fh, ensure_ascii=False, indent=1)
    window.destroy()


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if argv[:1] == ["--selftest"] and len(argv) >= 3:
        return self_test(argv[1], argv[2], argv[3] if len(argv) > 3 else "same")
    import webview
    ui_test = None
    if argv[:1] == ["--uitest"] and len(argv) >= 3:
        ui_test = (argv[2], argv[3] if len(argv) > 3 else "")
        argv = [argv[1]]
    first = next((a for a in argv if os.path.isfile(a)), None)
    app = App(first)
    with open(resource("app.html"), "r", encoding="utf-8") as fh:
        html = fh.read()
    window = webview.create_window("3DsetuPia – baskı ayarı asistanı / print settings assistant", html=html,
                                   js_api=_Api(app), width=1180, height=820, min_size=(760, 560))
    app.window = window

    def on_loaded(*_):
        _hook_drop(app, window)
        if ui_test:
            threading.Thread(target=_ui_test, args=(app, window) + ui_test, daemon=True).start()

    def on_closed(*_):
        # never leave a window-less process behind (WebView2 helpers can keep the loop alive)
        threading.Timer(1.0, lambda: os._exit(0)).start()

    window.events.loaded += on_loaded
    window.events.closed += on_closed
    icon = resource("ayarci.ico")
    try:
        webview.start(gui="edgechromium", icon=icon if os.path.isfile(icon) else None,
                      storage_path=_webview_folder(), private_mode=True)
    except TypeError:
        webview.start(gui="edgechromium")
    os._exit(0)


def _pid_alive(pid):
    try:
        import ctypes
        handle = ctypes.windll.kernel32.OpenProcess(0x1000, False, int(pid))   # QUERY_LIMITED_INFORMATION
        if handle:
            ctypes.windll.kernel32.CloseHandle(handle)
            return True
        return False
    except Exception:
        return True


def _webview_folder():
    """A WebView2 data folder of our own per running copy.

    Two copies sharing one folder share one browser process, and closing one of them took the
    other copy's page down with it. Folders of copies that are no longer running are removed.
    """
    import shutil
    import tempfile
    base = os.path.join(tempfile.gettempdir(), "3DsetuPia-webview")
    try:
        for name in os.listdir(base):
            if name.isdigit() and int(name) != os.getpid() and not _pid_alive(name):
                shutil.rmtree(os.path.join(base, name), ignore_errors=True)
    except OSError:
        pass
    shutil.rmtree(os.path.join(data_dir(), "webview"), ignore_errors=True)   # shared folder of 1.1.0 test builds
    return os.path.join(base, str(os.getpid()))


class _Api:
    """Only this one method is visible to the page."""

    def __init__(self, app):
        self._app = app

    def post(self, message):
        return self._app.post(message)


if __name__ == "__main__":
    main()
