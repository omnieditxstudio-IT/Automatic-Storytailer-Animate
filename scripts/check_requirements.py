#!/usr/bin/env python3
"""Prerequisite check that runs at the very start of every skill invocation.

- Python 3.8+
- numpy, skia-python, Pillow, faster-whisper — pip-installed automatically if missing
- ffmpeg / ffprobe — auto-installed via winget (Windows), brew (macOS) or apt (Linux) if missing
- cinematic-film scripts next to the skill (or via CINEMATIC_SCRIPTS)

If all available tools are present, prints one line and proceeds straight into production.
Anything missing is auto-installed; only cinematic-film is not auto-downloadable.
"""
import importlib
import pathlib
import platform
import shutil
import subprocess
import sys

MIN_PY = (3, 8)
NEED = [
    ("numpy", "numpy"),
    ("skia", "skia-python"),
    ("PIL", "Pillow"),
    ("faster_whisper", "faster-whisper"),
]
CINEMATIC_SCRIPTS = [
    "prep_assets.py", "fetch_commons.py", "render.py", "engine.py",
    "captions.py", "build_sfx.py", "mix_soundtrack.py",
]


def _check_python():
    if sys.version_info[:2] < MIN_PY:
        print(f"python >= {'.'.join(map(str, MIN_PY))} needed (have {sys.version.split()[0]})")
        return False
    return True


def _check_packages():
    missing = [pkg for mod, pkg in NEED if not _import(mod)]
    if not missing:
        return True
    print(f"missing Python packages: {', '.join(missing)} - installing...")
    subprocess.check_call(
        [sys.executable, "-m", "pip", "install", *missing], capture_output=True
    )
    still = [pkg for mod, pkg in NEED if not _import(mod)]
    if still:
        print(f"could not install: {', '.join(still)}")
        print(f"run:  {sys.executable} -m pip install {' '.join(still)}")
        return False
    return True


def _import(name):
    try:
        importlib.import_module(name)
        return True
    except Exception:
        return False


def _check_ffmpeg():
    if shutil.which("ffmpeg") and shutil.which("ffprobe"):
        return True
    print("ffmpeg / ffprobe missing - attempting automatic install...")
    sysname = platform.system()
    cmds = []
    if sysname == "Windows":
        cmds = [
            ["winget", "install", "-e", "--id", "Gyan.FFmpeg", "--silent",
             "--accept-source-agreements", "--accept-package-agreements"],
            ["winget", "install", "-e", "--id", "BtbN.FFmpeg", "--silent",
             "--accept-source-agreements", "--accept-package-agreements"],
        ]
    elif sysname == "Darwin":
        cmds = [["brew", "install", "ffmpeg"]]
    elif shutil.which("apt-get"):
        cmds = [["sudo", "-n", "apt-get", "update"],
                ["sudo", "-n", "apt-get", "install", "-y", "ffmpeg"]]
    for cmd in cmds:
        try:
            subprocess.run(cmd, capture_output=True, check=True)
        except Exception:
            continue
        if shutil.which("ffmpeg") and shutil.which("ffprobe"):
            print("ffmpeg installed.")
            return True
    print("could not install ffmpeg automatically.")
    print("  Windows: winget install Gyan.FFmpeg")
    print("  macOS:   brew install ffmpeg")
    print("  Linux:   sudo apt install ffmpeg")
    return False


def _check_cinematic_film():
    import os
    env = os.environ.get("CINEMATIC_SCRIPTS", "")
    if env:
        base = pathlib.Path(env)
    else:
        base = pathlib.Path(__file__).resolve().parents[2] / "cinematic-film" / "scripts"
    ok = all((base / f).exists() for f in CINEMATIC_SCRIPTS)
    if ok:
        return True
    print(f"cinematic-film scripts not found in {base}")
    print("install the cinematic-film skill next to this one, or set:")
    print("  CINEMATIC_SCRIPTS=<path-to-cinematic-film-scripts>")
    return False


def main():
    checks = [
        ("python", _check_python),
        ("packages", _check_packages),
        ("ffmpeg", _check_ffmpeg),
        ("cinematic-film", _check_cinematic_film),
    ]
    failed = [name for name, fn in checks if not fn()]
    if failed:
        print(f"\nmissing: {', '.join(failed)} - fix the above, then re-run.")
        sys.exit(2)
    print("requirements: ok")


if __name__ == "__main__":
    main()
