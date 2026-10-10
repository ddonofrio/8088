# FreeDOS 1.4 source build for the 8088

This directory builds a usable BIOS-bootable FreeDOS floppy with an English
command interpreter. It targets an original 8086/8088 PC with 640 KB conventional
memory. The runtime contains `KERNEL.SYS`, `COMMAND.COM`, `FDCONFIG.SYS`, and
`AUTOEXEC.BAT`. FreeCOM supplies internal commands such as `DIR`, `VER`, `TYPE`,
and `COPY`; external utilities and an installer are not included on these disks.

FreeDOS 1.4 is a distribution of separately versioned components. This project
uses **kernel 2043** and **FreeCOM 0.86a** from the official 1.4 packages, rather
than current development branches. The
[1.4 release report](https://www.ibiblio.org/pub/micro/pc-stuff/freedos/files/distributions/1.4/report.html)
identifies FreeCOM 0.86a; the downloaded kernel package and its `hdr/version.h`
identify kernel 2043.
The shell's upstream version string reports `0.86`; its package version is `0.86a`.

## Source layout and provenance

- `upstream/kernel/`: the kernel 2043 source snapshot and GPL license.
- `upstream/freecom/`: the FreeCOM 0.86a source snapshot, SUPPL source, and GPL license.
- `upstream/sources.json`: official package URLs, package/source SHA-256 hashes,
  and a list of omitted files.
- `scripts/`: build orchestration, FAT12/FAT16 image generation and validation,
  dependency setup, and cleanup. Python's standard library is sufficient.
- `build/`: ignored generated images, binaries, intermediate sources, and logs.

The build source subsets omit upstream tests, prebuilt outputs, documentation,
and non-English localization resources. The original source archives remain in
the dependency cache. License and copyright notices are preserved. The kernel
and FreeCOM retain their upstream GPL terms; see `upstream/kernel/COPYING` and
`upstream/freecom/license` before redistributing them.

## Build approach

Python creates a FAT12 bootstrap floppy and a partitioned FAT16 compiler disk.
QEMU boots the official prebuilt 8086 kernel and English shell **only to run the
compiler**. Open Watcom's DOS tools and DOS NASM then compile the source snapshots
inside this environment. No native Windows Watcom executable is needed.

The compiler VM runs on a modern emulated x86 CPU with 64 MB RAM; the compiler
itself is not an 8088 program. The output kernel uses `XCPU=86`, `XFAT=16`, and
Watcom `-0`; FreeCOM uses `-0`, English strings, and `no-xms-swap`, so the runtime
does not require XMS memory. The FAT12 boot sector is assembled from the upstream
source with an added `CPU 8086` directive. UPX compression is disabled.
HimemX supplies extended memory to the compiler VM and its DOS extenders; it is
not installed on the final runtime disks. The recipe uses the DOS real-mode
`wmaker` version of WMake. In this VM, the protected-mode `wmake` executable
stalled while launching DOS NASM; the real-mode executable completes those calls.
The kernel retains its upstream `*wcc` prefix, which lets WMake pass long DOS
command lines through an environment variable; see the
[WMake command execution reference](https://open-watcom.github.io/open-watcom-v2-wikidocs/ctools.html#Command_List_Execution).

The kernel recipe builds its helper utilities, device library, FAT12 boot sector,
and kernel. Optional `SYS.COM`, `COUNTRY.SYS`, `SETVER.SYS`, and other filesystem
boot templates are not required by this recipe. FreeCOM and SUPPL are compiled
from source, including the build utilities and libraries needed to produce
`COMMAND.COM`.

The FreeCOM linker wrapper explicitly selects `OPTION CASEEXACT`. Its legacy
MS2WLINK compatibility mode otherwise merges SUPPL's `toUpper` with the C
library's `toupper`, making the fallback call itself recursively during shell
initialization. This setting keeps the two symbols distinct; see the
[Open Watcom linker reference](https://open-watcom.github.io/open-watcom-v2-wikidocs/lguide.html).
Only generated working copies are adjusted: build configuration files, the
FreeCOM `-0` compiler flag and linker wrapper, and the boot-sector CPU directive.
The vendored source snapshots are kept separate from these changes.

## Dependencies and setup

On this Windows workspace, Python 3 and the existing Windows QEMU installation
are used directly. The dependency cache is in the parent directory's ignored
`.tmp/`. Run from `freedos-1.4`:

```powershell
python scripts/setup.py
python scripts/build.py
python scripts/check.py
python scripts/run.py
```

Setup downloads pinned packages and verifies their SHA-256 hashes. It extracts
Open Watcom locally without running its installer. It does not change application
control policy or install anything globally. It provisions these dependencies:

- Open Watcom v2, official `2026-10-01-Build`, including its DOS tools and libraries.
- DOS NASM 3.02 with CWSDPMI, from the FreeDOS package repository.
- HimemX 3.39, used only for compiler-VM extended memory.
- Windows NASM 3.02, for assembling the bootstrap sector.
- Official kernel/FreeCOM release binaries, used only as compiler-VM bootstrap files.

QEMU must already be available; see the
[Windows builds linked by QEMU](https://www.qemu.org/download/#windows).
The build searches `PATH` for host NASM/QEMU first, then uses the existing local
Windows paths. Their paths and the other dependency locations can be overridden:

```powershell
python scripts/build.py --help
```

On Ubuntu, install `python3`, `nasm`, and `qemu-system-x86`, run the same setup
script with `python3`, and build with `--nasm nasm --qemu qemu-system-i386`.
The DOS compiler VM uses the same toolchain on both hosts. If GNU Make is
available, `make build`, `make check`, `make run`, `make xt-image`, and `make clean`
wrap the Python commands. On Windows, `python scripts/clean.py` removes only the
resolved project `build/` directory.

The first compilation can take tens of minutes with QEMU software emulation. `build/compiler.img`
contains the compiler filesystem, and `build/compile.log` records the completed
build's output. The VM exits automatically when the batch job finishes. An
interrupted compiler disk can be continued with `python scripts/build.py --resume`.
The default build timeout is two hours and can be overridden with `--timeout`.
Use a normal build after changing source or build configuration.
The disposable compiler disk uses QEMU's `cache=unsafe` for build speed; the
source snapshots and final images are outside that disk.

## Outputs and boot test

- `build/KERNEL.SYS`: locally compiled 8086 kernel with FAT12/FAT16 support.
- `build/COMMAND.COM`: locally compiled English command interpreter.
- `build/boot.bin`: assembled upstream FAT12 boot sector.
- `build/freedos.img`: 1.44 MB FAT12 boot disk for quick QEMU iteration.
- `build/freedos-360k.img`: 360 KB FAT12 boot disk for an XT floppy drive.
- `build/build.json`: CPU configuration and hashes of the resulting artifacts.

Structural checks validate both FAT copies, image sizes, boot code/signature,
runtime file set, and exact equality with the compiled binaries. At the command
prompt, run `VER` and `DIR` to confirm that the shell and disk access work.
`python scripts/run.py --xt` opens the 360 KB disk. `--verify` exercises `VER /R`
and `DIR`, checks text-mode video memory, saves a graphical screenshot and console
transcripts in `build/`, and closes QEMU. Both runtime tests use 1 MB guest RAM
(640 KB conventional memory), without XMS drivers.

Both generated images have passed structural validation and graphical QEMU
boot tests through the `A:\>` prompt, `VER /R`, and `DIR`. The screenshots are
`build/boot-1440k.png` and `build/boot-360k.png`; console transcripts record the
compiled kernel and shell versions. The runtime binaries were compiled locally,
not copied from the bootstrap disk.

QEMU does not emulate exact 8088 execution or timing; passing these checks and
booting QEMU cannot prove compatibility with an original XT. For a faithful test,
configure 86Box with an IBM PC/XT and 8088 CPU, appropriate separately supplied
ROMs, and a 360 KB drive, then insert `build/freedos-360k.img`. No copyrighted ROMs
are bundled or obtained by these scripts.
