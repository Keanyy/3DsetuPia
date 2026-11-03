"""3DsetuPia - loads the panel HTML (the bundler inlines it as a string)."""

import os

with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "ui.html"), "r", encoding="utf-8") as _fh:
    UI_HTML = _fh.read()
