#!/usr/bin/env python3
"""Validate boot media structure; this is not an 8088 opcode validator."""

import argparse
from pathlib import Path
import sys


SECTOR_SIZE = 512
MESSAGE = b"Hello, world!\x00"


def check_image(path: Path, expected_size: int, boot: bytes) -> None:
    size = path.stat().st_size
    if size != expected_size:
        raise ValueError(f"{path}: expected {expected_size} bytes, got {size}")
    with path.open("rb") as image:
        if image.read(SECTOR_SIZE) != boot:
            raise ValueError(f"{path}: first sector differs from boot.bin")
    print(f"OK: {path.name}: {size} bytes, matching boot sector")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--build-dir",
        type=Path,
        default=Path(__file__).resolve().parent.parent / "build",
        help="directory containing boot.bin, os.img, and optional xt.img",
    )
    build = parser.parse_args().build_dir
    try:
        boot = (build / "boot.bin").read_bytes()
        if len(boot) != SECTOR_SIZE:
            raise ValueError(f"boot.bin: expected 512 bytes, got {len(boot)}")
        if boot[510:512] != b"\x55\xAA":
            raise ValueError("boot.bin: missing 55 AA signature at offsets 510-511")
        if MESSAGE not in boot[:510]:
            raise ValueError("boot.bin: missing zero-terminated ASCII Hello, world!")
        print("OK: boot.bin: 512 bytes, 55 AA signature, expected message")
        check_image(build / "os.img", 1440 * 1024, boot)
        xt_image = build / "xt.img"
        if xt_image.exists():
            check_image(xt_image, 360 * 1024, boot)
        else:
            print("SKIP: optional xt.img is absent (create it with make xt-image)")
    except (OSError, ValueError) as error:
        print(f"FAIL: {error}", file=sys.stderr)
        return 1
    print("Structural checks passed; 8088 compatibility requires source review.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
