#!/usr/bin/env python3
"""Boot a compiled floppy graphically; optionally exercise VER and DIR through QMP."""

import argparse
import json
from pathlib import Path
import shutil
import socket
import subprocess
import time


PROJECT = Path(__file__).resolve().parent.parent
BUILD = PROJECT / "build"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--xt", action="store_true", help="boot the 360 KB floppy")
    parser.add_argument("--verify", action="store_true", help="test the shell, save screenshots, and close QEMU")
    parser.add_argument("--qemu", default=shutil.which("qemu-system-i386") or PROJECT.parent / ".tmp/tools/qemu/qemu-system-i386.exe")
    parser.add_argument("--display", default="gtk")
    args = parser.parse_args()
    image = BUILD / ("freedos-360k.img" if args.xt else "freedos.img")
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    drive = f"file={image},format=raw,if=floppy" + (",readonly=on" if args.verify else "")
    command = [str(args.qemu), "-drive", drive,
               "-boot", "a", "-m", "1", "-display", args.display,
               "-qmp", f"tcp:127.0.0.1:{port},server=on,wait=off"]
    if not args.verify:
        subprocess.run(command, check=True)
        return
    suffix = "360k" if args.xt else "1440k"
    with (BUILD / f"qemu-{suffix}.log").open("w") as log:
        process = subprocess.Popen(command, stdout=log, stderr=log)
        try:
            deadline = time.monotonic() + 20
            while True:
                if process.poll() is not None:
                    raise RuntimeError("QEMU exited before connecting; inspect its build log")
                try:
                    connection = socket.create_connection(("127.0.0.1", port), timeout=1)
                    break
                except OSError:
                    if time.monotonic() >= deadline:
                        raise TimeoutError("QMP connection timed out")
                    time.sleep(0.2)
            with connection:
                stream = connection.makefile("rwb")
                stream.readline()

                def qmp(name, arguments=None):
                    request = {"execute": name, "id": name}
                    if arguments is not None:
                        request["arguments"] = arguments
                    stream.write((json.dumps(request) + "\n").encode())
                    stream.flush()
                    while True:
                        line = stream.readline()
                        if not line:
                            raise RuntimeError("QMP disconnected")
                        response = json.loads(line)
                        if response.get("id") == name:
                            if "error" in response:
                                raise RuntimeError(response["error"])
                            return response.get("return")

                def console(stage):
                    path = BUILD / f"console-{suffix}.bin"
                    qmp("pmemsave", {"val": 0xB8000, "size": 4000, "filename": str(path)})
                    text = path.read_bytes()[::2].decode("cp437").replace("\x00", " ")
                    formatted = "\n".join(text[i:i + 80].rstrip() for i in range(0, 2000, 80))
                    (BUILD / f"console-{suffix}-{stage}.txt").write_text(formatted + "\n", encoding="utf-8")
                    return formatted

                def type_command(text):
                    keys = {" ": "spc", "/": "slash"}
                    for character in text:
                        qmp("human-monitor-command", {"command-line": "sendkey " + keys.get(character, character)})
                        time.sleep(0.15)
                    qmp("human-monitor-command", {"command-line": "sendkey ret"})
                    time.sleep(1)

                qmp("qmp_capabilities")
                deadline = time.monotonic() + 30
                while True:
                    initial = console("boot")
                    if "FreeDOS 1.4 source build for 8086/8088." in initial and "A:\\>" in initial:
                        break
                    if time.monotonic() >= deadline:
                        qmp("screendump", {"filename": str(BUILD / f"boot-{suffix}.png"), "format": "png"})
                        raise RuntimeError("Compiled disk did not reach the expected shell prompt")
                    time.sleep(0.5)
                type_command("ver /r")
                version = console("ver")
                if "0.86" not in version or "2043" not in version:
                    raise RuntimeError("VER did not identify the compiled shell and kernel")
                if "XMS_Swap" in version:
                    raise RuntimeError("The shell was built with XMS swapping enabled")
                type_command("dir")
                listing = console("dir")
                if "KERNEL" not in listing or "COMMAND" not in listing or "A:\\>" not in listing:
                    raise RuntimeError("DIR did not list the runtime files and return to the prompt")
                qmp("screendump", {"filename": str(BUILD / f"boot-{suffix}.png"), "format": "png"})
                qmp("quit")
            process.wait(timeout=10)
            print(f"PASS: graphical boot, VER /R, and DIR on {suffix}; guest memory: 1 MB")
        finally:
            if process.poll() is None:
                process.terminate()
                process.wait(timeout=10)


if __name__ == "__main__":
    main()
