#!/usr/bin/env python3
"""Fill in the GitHub user name and author everywhere, then rebuild dist/ayarci.py.

Usage: python tools/set_owner.py --github KULLANICI --author "Adın Soyadın"
"""
import argparse
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEXT_EXT = {".md", ".py", ".yml", ".yaml", ".html", ".txt", ".json"}
SKIP_DIRS = {".git", "dist", "__pycache__", ".pytest_cache", "node_modules"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--github", required=True, help="GitHub user or organisation name")
    ap.add_argument("--author", required=True, help="Name shown as plugin author")
    a = ap.parse_args()
    if not re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})", a.github):
        sys.exit("invalid GitHub name: %s" % a.github)
    changed = []
    for d, dirs, files in os.walk(ROOT):
        dirs[:] = [x for x in dirs if x not in SKIP_DIRS]
        for f in files:
            if os.path.splitext(f)[1] not in TEXT_EXT or f == "set_owner.py":
                continue
            p = os.path.join(d, f)
            s = open(p, encoding="utf-8").read()
            n = s.replace("GITHUB_KULLANICI", a.github)
            if n != s:
                open(p, "w", encoding="utf-8", newline="\n").write(n)
                changed.append(os.path.relpath(p, ROOT))
    cfg = os.path.join(ROOT, "tools", "owner.txt")
    open(cfg, "w", encoding="utf-8").write("github=%s\nauthor=%s\n" % (a.github, a.author))
    print("updated:", ", ".join(changed) or "nothing")
    subprocess.check_call([sys.executable, os.path.join(ROOT, "tools", "build_plugin.py"),
                           "--author", a.author, "--repo", "https://github.com/%s/3DsetuPia" % a.github])


if __name__ == "__main__":
    main()
