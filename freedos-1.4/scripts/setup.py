#!/usr/bin/env python3
"""Fetch pinned build dependencies locally; no system installation or policy changes."""

import hashlib
import json
from pathlib import Path
import urllib.request
import zipfile


PROJECT = Path(__file__).resolve().parent.parent
CACHE = PROJECT.parent / ".tmp"
TOOLS = CACHE / "tools"
SOURCES = json.loads((PROJECT / "upstream/sources.json").read_text())


def obtain(url, filename, expected, destination):
    filename.parent.mkdir(parents=True, exist_ok=True)
    if not filename.exists() or hashlib.sha256(filename.read_bytes()).hexdigest() != expected:
        print(f"Downloading {url}", flush=True)
        with urllib.request.urlopen(url) as response, filename.open("wb") as output:
            while chunk := response.read(1024 * 1024):
                output.write(chunk)
    if hashlib.sha256(filename.read_bytes()).hexdigest() != expected:
        raise ValueError(f"Checksum mismatch: {filename}")
    destination.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(filename) as archive:
        for entry in archive.infolist():
            target = (destination / entry.filename).resolve()
            if not target.is_relative_to(destination.resolve()):
                raise ValueError(f"Unsafe archive entry: {entry.filename}")
        archive.extractall(destination)
    print(f"Verified and extracted {filename.name}")


def main():
    for component in ("kernel", "freecom"):
        entry = SOURCES[component]
        obtain(entry["package_url"], CACHE / f"{component}14.zip", entry["package_sha256"], CACHE / f"{component}14-package")
    obtain(
        "https://www.ibiblio.org/pub/micro/pc-stuff/freedos/files/repositories/1.4/devel/nasm.zip",
        CACHE / "nasm-dos.zip", "f3497ec94f76b508a74904926a479cf33d75f6da332c432dfa72d5aaa2903cbe",
        CACHE / "nasm-dos-package",
    )
    obtain(
        "https://www.ibiblio.org/pub/micro/pc-stuff/freedos/files/repositories/1.4/base/himemx.zip",
        CACHE / "himemx.zip", "99b44e5bbb878105486e172675a460f645cdfb5a86cc1cf1e0e549fa31f29ce6",
        CACHE / "himemx-package",
    )
    obtain(
        "https://github.com/open-watcom/open-watcom-v2/releases/download/2026-10-01-Build/open-watcom-2_0-c-win-x64.exe",
        TOOLS / "watcom-setup.exe", "3d2d2b56c890e4ac6661cee7b85c9aa33369677c0a8ff1ed70f1a711942094f0",
        TOOLS / "watcom",
    )
    obtain(
        "https://www.nasm.us/pub/nasm/releasebuilds/3.02/win64/nasm-3.02-win64.zip",
        TOOLS / "nasm.zip", "161d0bfaff53c2f9e9f3e69fd0672323ebabafd1268976a5cec11be92a19aee7",
        TOOLS / "nasm",
    )
    print("Build dependencies are ready. Install QEMU separately if it is not already available.")


if __name__ == "__main__":
    main()
