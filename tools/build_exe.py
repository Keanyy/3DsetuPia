#!/usr/bin/env python3
"""Build the Windows program: dist/3DsetuPia.exe (one file, no console, no Python needed).

Usage (from the repository root, in a virtual environment with requirements-app.txt installed):
    python tools/build_exe.py [--workdir <temp folder>]

The build folder can be large; by default it goes to %LOCALAPPDATA%\\3DsetuPia-build so it stays out of
OneDrive / the repository. Only the finished .exe is written to dist/.
"""
import argparse
import hashlib
import os
import re
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src")
NAME = "3DsetuPia"

VERSION_INFO = """# UTF-8
VSVersionInfo(
  ffi=FixedFileInfo(filevers=({v0}, {v1}, {v2}, 0), prodvers=({v0}, {v1}, {v2}, 0), mask=0x3f, flags=0x0,
                    OS=0x40004, fileType=0x1, subtype=0x0, date=(0, 0)),
  kids=[
    StringFileInfo([StringTable('041F04B0', [
      StringStruct('CompanyName', '{author}'),
      StringStruct('FileDescription', '3DsetuPia - 3D baski ayari asistani / print settings assistant'),
      StringStruct('FileVersion', '{version}'),
      StringStruct('InternalName', '{name}'),
      StringStruct('LegalCopyright', 'GNU AGPL-3.0'),
      StringStruct('OriginalFilename', '{name}.exe'),
      StringStruct('ProductName', '{name}'),
      StringStruct('ProductVersion', '{version}')])]),
    VarFileInfo([VarStruct('Translation', [0x041F, 1200])])
  ]
)
"""


def _version():
    text = open(os.path.join(SRC, "ayarci", "app.py"), encoding="utf-8").read()
    return re.search(r'APP_VERSION = "([^"]+)"', text).group(1)


def _owner():
    path = os.path.join(ROOT, "tools", "owner.txt")
    out = {}
    if os.path.isfile(path):
        for line in open(path, encoding="utf-8"):
            if "=" in line:
                k, v = line.strip().split("=", 1)
                out[k] = v
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workdir", default=os.path.join(os.environ.get("LOCALAPPDATA", ROOT), "3DsetuPia-build"))
    ap.add_argument("--out", default=os.path.join(ROOT, "dist"), help="folder for the .exe (default: dist)")
    args = ap.parse_args()
    args.workdir = os.path.abspath(args.workdir)   # PyInstaller resolves paths against the spec folder
    out_dir = os.path.abspath(args.out)
    version = _version()
    parts = (re.findall(r"\d+", version) + ["0", "0", "0"])[:3]
    os.makedirs(args.workdir, exist_ok=True)
    vfile = os.path.join(args.workdir, "version_info.txt")
    with open(vfile, "w", encoding="utf-8") as fh:
        fh.write(VERSION_INFO.format(v0=parts[0], v1=parts[1], v2=parts[2], version=version, name=NAME,
                                     author=_owner().get("author", "3DsetuPia contributors")))
    icon = os.path.join(SRC, "ayarci", "ayarci.ico")
    sep = ";" if os.name == "nt" else ":"
    cmd = [sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--onefile", "--windowed",
           "--name", NAME, "--icon", icon, "--version-file", vfile,
           "--paths", SRC,
           "--add-data", "%s%sayarci" % (os.path.join(SRC, "ayarci", "app.html"), sep),
           "--add-data", "%s%sayarci" % (icon, sep),
           "--collect-data", "certifi",
           "--hidden-import", "webview.platforms.edgechromium",
           "--hidden-import", "webview.platforms.winforms",
           "--exclude-module", "tkinter", "--exclude-module", "matplotlib", "--exclude-module", "PIL",
           "--exclude-module", "pytest",
           "--workpath", os.path.join(args.workdir, "work"), "--specpath", args.workdir,
           "--distpath", out_dir,
           os.path.join(SRC, "ayarci_desktop.py")]
    print(" ".join('"%s"' % c if " " in c else c for c in cmd))
    subprocess.check_call(cmd, cwd=ROOT)
    exe = os.path.join(out_dir, NAME + ".exe")
    print("built %s (%.1f MB, version %s)" % (exe, os.path.getsize(exe) / 1e6, version))
    sums = []
    for f in (exe, os.path.join(ROOT, "dist", "ayarci.py")):
        if os.path.isfile(f):
            sums.append("%s  %s" % (hashlib.sha256(open(f, "rb").read()).hexdigest(), os.path.basename(f)))
    with open(os.path.join(out_dir, "SHA256SUMS.txt"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(sums) + "\n")
    shutil.rmtree(os.path.join(args.workdir, "work"), ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
