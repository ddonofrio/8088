#!/usr/bin/env python3
"""Check FAT boot images against the locally compiled kernel and shell."""

import hashlib
import json
from pathlib import Path
import sys

from fat import Reader


def main():
    build = Path(__file__).resolve().parent.parent / "build"
    try:
        metadata = json.loads((build / "build.json").read_text())
        for name, expected in metadata["sha256"].items():
            if hashlib.sha256((build / name).read_bytes()).hexdigest() != expected:
                raise ValueError(f"{name}: SHA256 differs from the successful build")
        boot = (build / "boot.bin").read_bytes()
        if len(boot) != 512 or boot[510:] != b"\x55\xAA":
            raise ValueError("Invalid compiled boot sector")
        for name, size in [("freedos.img", 1440 * 1024), ("freedos-360k.img", 360 * 1024)]:
            path = build / name
            image = path.read_bytes()
            if len(image) != size or image[:3] != boot[:3] or image[62:512] != boot[62:512]:
                raise ValueError(f"{name}: incorrect size, signature, or boot code")
            disk = Reader(path)
            if disk.bits != 12:
                raise ValueError(f"{name}: expected a FAT12 filesystem")
            if image[disk.fat_start:disk.fat_start + disk.spf * 512] != image[disk.fat_start + disk.spf * 512:disk.fat_start + disk.spf * 1024]:
                raise ValueError(f"{name}: FAT copies differ")
            files = disk.files()
            for binary in ("KERNEL.SYS", "COMMAND.COM"):
                if files[binary] != (build / binary).read_bytes():
                    raise ValueError(f"{name}: {binary} differs from compiled output")
            if set(files) != {"KERNEL.SYS", "COMMAND.COM", "FDCONFIG.SYS", "AUTOEXEC.BAT"}:
                raise ValueError(f"{name}: unexpected runtime files")
            print(f"PASS: {name}: {size} bytes, FAT12, matching compiled kernel and shell")
    except (OSError, KeyError, ValueError) as error:
        print(f"FAIL: {error}", file=sys.stderr)
        return 1
    print("Checks passed. QEMU does not prove exact 8088 hardware compatibility.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
