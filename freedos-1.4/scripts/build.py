#!/usr/bin/env python3
"""Compile FreeDOS 1.4 components inside a DOS build VM, then create boot disks."""

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import socket
import subprocess

from fat import Reader, Writer, short_name, source_tree


PROJECT = Path(__file__).resolve().parent.parent
WORKSPACE = PROJECT.parent
BUILD = PROJECT / "build"
TOOLS = WORKSPACE / ".tmp/tools"


def dos_text(text):
    return text.replace("\r\n", "\n").replace("\n", "\r\n").encode("ascii")


def run(command, **kwargs):
    print("Running:", " ".join(map(str, command)), flush=True)
    subprocess.run(list(map(str, command)), check=True, **kwargs)


def copy_sources(component):
    source = PROJECT / "upstream" / component
    target = BUILD / "sources" / component
    # Generated files from earlier host diagnostics must not enter a fresh disk.
    if target.exists():
        if (target.is_symlink() or BUILD.resolve().parent != PROJECT.resolve()
                or target.resolve().parent != (BUILD / "sources").resolve()
                or not target.resolve().is_relative_to(BUILD.resolve())):
            raise ValueError("Working sources must stay inside the project build directory")
        shutil.rmtree(target)
    shutil.copytree(source, target)
    return target


def tool_tree(path):
    result = {}
    for item in sorted(path.iterdir()):
        try:
            short_name(item.name)
        except ValueError:
            continue
        result[item.name] = tool_tree(item) if item.is_dir() else item.read_bytes()
    return result


def build(args):
    BUILD.mkdir(exist_ok=True)
    kernel = copy_sources("kernel")
    freecom = copy_sources("freecom")
    # Git does not retain the empty upstream output directory.
    kernel.joinpath("bin").mkdir(exist_ok=True)
    # Host cross-build/CI scripts are not needed inside the DOS build environment.
    freecom.joinpath("ci_prereq.sh").unlink(missing_ok=True)
    boot_source = kernel / "boot/boot.asm"
    boot_source.write_bytes(b"CPU 8086\n" + (PROJECT / "upstream/kernel/boot/boot.asm").read_bytes())
    run([args.nasm, "-f", "bin", "-DISFAT12", "-o", BUILD / "boot.bin", boot_source])
    boot = (BUILD / "boot.bin").read_bytes()
    kernel.joinpath("config.bat").write_bytes(dos_text("""@echo off
set COMPILER=WATCOM
set XNASM=C:\\TOOLS\\NASM.EXE
set XCPU=86
set XFAT=16
set XUPX=
set LOADSEG=0x60
"""))
    kernel_config = kernel / "mkfiles/watcom.mak"
    freecom.joinpath("config.bat").write_bytes(dos_text("""@echo off
set COMPILER=WATCOM
set XNASM=C:\\TOOLS\\NASM.EXE
"""))
    freecom.joinpath("config.mak").write_bytes(freecom.joinpath("config.std").read_bytes())
    watcom_config = freecom / "mkfiles/watcom.mak"
    watcom_config.write_bytes(watcom_config.read_bytes()
                             .replace(b"CFLAGS1 = -os-s-wx", b"CFLAGS1 = -0-os-s-wx"))
    # MS2WLINK's compatibility mode otherwise merges toUpper and toupper.
    shell_linker = freecom / "shell/wlinker.bat"
    shell_linker.write_bytes(shell_linker.read_bytes()
                             .replace(b"op map,statics,verbose,stack=4k",
                                      b"op caseexact,map,statics,verbose,stack=4k"))
    guest_batch = dos_text("""@echo off
if exist C:\\SUCCESS.TXT del C:\\SUCCESS.TXT
if exist C:\\FAILED.TXT del C:\\FAILED.TXT
set WATCOM=C:\\WATCOM
set PATH=C:\\WATCOM\\BINW;C:\\TOOLS;C:\\FREECOM\\SCRIPTS;C:\\KERNEL\\UTILS
set INCLUDE=C:\\WATCOM\\H
set EDPATH=C:\\WATCOM\\EDDAT
set DOS4G=QUIET
C:
cd \\KERNEL
echo Building FreeDOS kernel 2043 for 8086, FAT12/FAT16.
call config.bat
set MAKE=wmaker /ms /h
call default.bat
cd utils
%MAKE% production
if errorlevel 1 goto failed
cd ..\\lib
%MAKE%
if errorlevel 1 goto failed
cd ..\\drivers
%MAKE% production
if errorlevel 1 goto failed
cd ..\\boot
%MAKE% fat12com.bin
if errorlevel 1 goto failed
cd ..\\kernel
%MAKE% ..\\bin\\KWC8616.SYS
if errorlevel 1 goto failed
cd ..
if not exist BIN\\KWC8616.SYS goto failed
call default.bat clearset
cd \\FREECOM
echo Building English FreeCOM 0.86a without XMS swapping.
set MAKE=wmaker -ms -h -f makefile.mak
rem Rebuild these small resources when resuming an interrupted assembler.
if exist CRITER\\CRITER del CRITER\\CRITER
if exist CRITER\\CRITER1 del CRITER\\CRITER1
rem Relink after updating the wrapper, including on a resumed compiler disk.
if exist SHELL\\COMMAND.EXE del SHELL\\COMMAND.EXE
if exist COMMAND.COM del COMMAND.COM
call build.bat wc no-xms-swap english
if not exist C:\\FREECOM\\COMMAND.COM goto failed
if not exist C:\\FREECOM\\SUPPL\\SUPPL_S.LIB goto failed
if not exist C:\\FREECOM\\CMD\\CMDS.LIB goto failed
echo SUCCESS>C:\\SUCCESS.TXT
goto finished
:failed
echo FAILED>C:\\FAILED.TXT
:finished
cd \\
""")
    watcom = Path(args.watcom)
    nasm_dos = Path(args.dos_nasm)
    work_tree = {
        "KERNEL": source_tree(kernel),
        "FREECOM": source_tree(freecom),
        "WATCOM": {
            "BINW": tool_tree(watcom / "binw"),
            "H": tool_tree(watcom / "h"),
            "LIB286": tool_tree(watcom / "lib286"),
        },
        "TOOLS": {
            "NASM.EXE": (nasm_dos / "nasm.exe").read_bytes(),
            "CWSDPMI.EXE": (nasm_dos / "cwsdpmi.exe").read_bytes(),
            # isa-debug-exit is available only in the build VM, never on target.
            "VMEXIT.COM": bytes.fromhex("ba f4 00 31 c0 ef fa f4 eb fd"),
        },
        "BUILD.BAT": guest_batch,
    } if not args.resume else None
    work_image = BUILD / "compiler.img"
    if not args.resume:
        Writer(128 * 1024 * 1024, boot, fat16=True, partitioned=True).write(work_image, work_tree)
    elif not work_image.exists():
        raise ValueError("No compiler.img is available to resume")
    else:
        Reader(work_image).update_file(work_image, "BUILD.BAT", guest_batch)
        Reader(work_image).update_file(work_image, "FREECOM/MKFILES/WATCOM.MAK", watcom_config.read_bytes())
        Reader(work_image).update_file(work_image, "KERNEL/MKFILES/WATCOM.MAK", kernel_config.read_bytes())
        Reader(work_image).update_file(work_image, "FREECOM/SHELL/WLINKER.BAT", shell_linker.read_bytes())
    # Prebuilt release files bootstrap the compiler only; final media uses outputs.
    bootstrap = {
        "KERNEL.SYS": Path(args.bootstrap_kernel).read_bytes(),
        "COMMAND.COM": Path(args.bootstrap_shell).read_bytes(),
        "HIMEMX.EXE": Path(args.himem).read_bytes(),
        "FDCONFIG.SYS": dos_text("DEVICE=A:\\HIMEMX.EXE\nDOS=HIGH\nSHELL=A:\\COMMAND.COM A:\\ /E:4096 /P\n"),
        "AUTOEXEC.BAT": dos_text("@echo off\nA:\\COMMAND.COM /E:4096 /C C:\\BUILD.BAT >C:\\BUILD.LOG\nC:\\TOOLS\\VMEXIT.COM\n"),
    }
    Writer(1440 * 1024, boot).write(BUILD / "bootstrap.img", bootstrap)
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        qmp_port = probe.getsockname()[1]
    (BUILD / "qmp.json").write_text(json.dumps({"port": qmp_port}) + "\n")
    command = [args.qemu, "-accel", "tcg", "-m", "64", "-boot", "a", "-no-reboot",
               "-drive", f"file={BUILD / 'bootstrap.img'},format=raw,if=floppy,readonly=on",
               "-drive", f"file={work_image},format=raw,if=ide,cache=unsafe",
               "-display", "none", "-monitor", "none", "-serial", "none",
               "-qmp", f"tcp:127.0.0.1:{qmp_port},server=on,wait=off",
               "-device", "isa-debug-exit,iobase=0xf4,iosize=2"]
    print("Compiling inside the DOS VM; output will be saved to build/compile.log.", flush=True)
    with (BUILD / "qemu-build.log").open("w") as log:
        result = subprocess.run(list(map(str, command)), stdout=log, stderr=log, timeout=args.timeout)
    disk = Reader(work_image).files()
    (BUILD / "compile.log").write_bytes(disk.get("BUILD.LOG", b"No build log was produced."))
    if (result.returncode != 1 or "SUCCESS.TXT" not in disk or "FAILED.TXT" in disk
            or b"All done. COMMAND.COM is ready for use!" not in disk.get("BUILD.LOG", b"")):
        print((BUILD / "compile.log").read_text(errors="replace")[-5000:])
        raise RuntimeError(f"DOS build failed (QEMU exit {result.returncode}); see build/compile.log")
    kernel_binary = disk["KERNEL"]["BIN"]["KWC8616.SYS"]
    shell_binary = disk["FREECOM"]["COMMAND.COM"]
    (BUILD / "KERNEL.SYS").write_bytes(kernel_binary)
    (BUILD / "COMMAND.COM").write_bytes(shell_binary)
    runtime = {
        "KERNEL.SYS": kernel_binary,
        "COMMAND.COM": shell_binary,
        "FDCONFIG.SYS": dos_text("DOS=LOW\nSHELL=A:\\COMMAND.COM A:\\ /E:1024 /P\n"),
        "AUTOEXEC.BAT": dos_text("@echo off\nprompt $p$g\necho FreeDOS 1.4 source build for 8086/8088.\nver\n"),
    }
    for name, size in [("freedos.img", 1440 * 1024), ("freedos-360k.img", 360 * 1024)]:
        Writer(size, boot).write(BUILD / name, runtime)
    metadata = {
        "kernel": "2043", "freecom": "0.86a", "cpu": "8086/8088",
        "kernel_flags": "XCPU=86 XFAT=16 TARGETOPT=-0",
        "freecom_flags": "-0, English, no-xms-swap",
        "freecom_linker_flags": "OPTION CASEEXACT, stack=4k",
        "sha256": {name: hashlib.sha256((BUILD / name).read_bytes()).hexdigest()
                   for name in ("boot.bin", "KERNEL.SYS", "COMMAND.COM", "freedos.img", "freedos-360k.img")},
    }
    (BUILD / "build.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    print("Compiled kernel and shell; generated 1.44 MB and 360 KB boot images.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--nasm", default=shutil.which("nasm") or TOOLS / "nasm/nasm-3.02/nasm.exe")
    parser.add_argument("--qemu", default=shutil.which("qemu-system-i386") or TOOLS / "qemu/qemu-system-i386.exe")
    parser.add_argument("--watcom", default=TOOLS / "watcom")
    parser.add_argument("--dos-nasm", default=WORKSPACE / ".tmp/nasm-dos-package/DEVEL/NASM")
    parser.add_argument("--bootstrap-kernel", default=WORKSPACE / ".tmp/kernel14-package/BIN/KERNL86N.SYS")
    parser.add_argument("--bootstrap-shell", default=WORKSPACE / ".tmp/freecom14-package/BIN/COMMAND.COM")
    parser.add_argument("--himem", default=WORKSPACE / ".tmp/himemx-package/BIN/HimemX.exe")
    parser.add_argument("--timeout", type=int, default=7200)
    parser.add_argument("--resume", action="store_true", help="resume an interrupted compiler disk")
    args = parser.parse_args()
    build(args)


if __name__ == "__main__":
    main()
