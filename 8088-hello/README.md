# Intel 8088 bare-metal Hello World

A custom BIOS boot sector displays exactly `Hello, world!` and then waits in an
interrupt-enabled loop. It uses no DOS, GRUB, operating system, or C runtime.
The target is an original Intel 8088-compatible IBM PC/XT with a compatible BIOS.

## Tools and CPU constraints

NASM assembles a raw 16-bit binary, GNU Make builds floppy images, and Python 3
checks their structure using only its standard library. QEMU provides quick
BIOS/floppy boot iteration. `qemu-system-i386` does **not** emulate the exact 8088
CPU or its timing: a successful QEMU boot cannot establish PC/XT compatibility.
Optional 86Box testing provides a more faithful PC/XT configuration.

`boot.asm` uses `CPU 8086`, `BITS 16`, and `ORG 0x7C00`. NASM's
[CPU directive](https://www.nasm.us/doc/nasm08.html#section-8.11) restricts the
instruction set, but source review remains necessary. The executable code uses
only 8086/8088 forms of `CLI`, far/short `JMP`, `XOR`, `MOV`, `CLD`, `STI`, `INT`,
`LODSB`, `TEST`, short `JZ`, segment/register `PUSH` and `POP`, and `HLT`.
There are no 186/286+ opcodes, 32-bit operands, or protected-mode operations.
Neither structural checks nor QEMU booting proves that all opcodes are
8088-compatible.

## Ubuntu 24.04 / WSL2 setup

Use Ubuntu 24.04 under WSL2 on Windows 11. From PowerShell, inspect WSL first:

```powershell
wsl --list --verbose
```

If WSL/Ubuntu is not installed, run this in an administrator PowerShell, then
complete any required reboot and Ubuntu's initial user setup:

```powershell
wsl --install -d Ubuntu-24.04
```

In Ubuntu, inspect the environment and dependencies:

```sh
cat /etc/os-release
for tool in nasm make python3 qemu-system-i386; do
    command -v "$tool" || true
done
```

Install missing tools with the following actual Ubuntu commands. Already
installed packages are retained by apt; if every tool is present, skip this step.

```sh
sudo apt-get update
sudo apt-get install -y nasm make python3 qemu-system-x86
```

Verify installed versions:

```sh
nasm -v
make --version
python3 --version
qemu-system-i386 --version
```

Open the project directory in VS Code's WSL environment (for example, `code .`
from Ubuntu) and use its Ubuntu terminal. When working in the Windows workspace:

```sh
cd /mnt/c/Users/diego/Code/baremetal/pc/8080/8088-hello
```

### Graphical display

[WSLg supports Linux graphical applications under WSL2](https://learn.microsoft.com/en-us/windows/wsl/tutorials/gui-apps).
Check `printenv DISPLAY WAYLAND_DISPLAY`. `make run` lets QEMU select its default
graphical backend; to request GTK explicitly, use `make run QEMU_DISPLAY=gtk`.
If no display is available, a headless run does not verify visible text. Configure
WSLg or use Windows QEMU from the
[Windows builds linked by QEMU](https://www.qemu.org/download/#windows).
After building, launch the same image from PowerShell:

```powershell
& 'C:\Program Files\qemu\qemu-system-i386.exe' -drive 'file=build/os.img,format=raw,if=floppy' -boot a
```

Run this inside `8088-hello` and adjust the executable path to the installation.
The Windows fallback uses the same custom boot sector and does not require DOS.

## Build and use

From `8088-hello` in an Ubuntu/WSL2 terminal:

```sh
make build       # build/boot.bin and the raw 1.44 MB build/os.img
make check       # validate boot.bin, os.img, and xt.img when present
make run         # boot os.img graphically in QEMU; close the window to exit
make xt-image    # optional raw 360 KB build/xt.img for an XT floppy drive
make check       # also validate the generated XT image
make clean       # remove only the three generated binary/image files
```

The default `make` target is `build`. All generated files live under ignored
`build/`. `NASM`, `PYTHON`, `QEMU`, and `QEMU_DISPLAY` can be overridden on the make
command line. The 1.44 MB image is exactly 1,474,560 bytes; the 360 KB image is
368,640 bytes. Both start with the same 512-byte boot sector, followed by zeroes.
These are raw boot media with no filesystem, partition table, or additional code.

`scripts/check_boot.py` validates the boot-sector length, signature bytes `55 AA`
at offsets 510 and 511, the zero-terminated ASCII message, image sizes, and exact
boot-sector equality at image offset zero. Missing or malformed required files
produce a nonzero exit status. An absent optional XT image is reported as skipped.

## Boot flow

1. The BIOS reads the first floppy sector to physical address `0x7C00`.
2. A far jump normalizes `CS:IP` to `0000:start`, supporting BIOS entry at either
   `0000:7C00` or `07C0:0000`.
3. With interrupts disabled, the boot sector establishes `SS:SP = 0000:7C00`,
   initializes `DS` and `ES` to zero, clears the direction flag, and enables
   interrupts. The stack grows below the boot sector.
4. BIOS `INT 10h` retrieves and resets the current video mode to clear the
   display, preserving the adapter's mode (including monochrome mode 7).
5. The code reinitializes data segments and prints the zero-terminated string
   using `INT 10h`, `AH=0Eh`, display page zero. No newline is appended.
6. `STI`, `HLT`, and a backward jump form a stable idle loop. BIOS timer interrupts
   may wake the CPU; execution always returns to the loop.

## Manual 86Box PC/XT test

Obtain 86Box from [86box.net](https://86box.net/) or the
[official repository](https://github.com/86Box/86Box). See its
[setup documentation](https://86box.readthedocs.io/en/latest/usage/gettingstarted.html).
86Box requires BIOS and hardware ROMs appropriate for the chosen machine. Obtain
ROMs you are entitled to use separately; none are bundled or downloaded here.

1. Create a machine using a supported IBM PC/XT configuration and an **8088**
   CPU (for example, IBM PC/XT at 4.77 MHz). Select a compatible CGA or monochrome
   display adapter and configure the necessary ROMs.
2. Configure drive A and its controller to match the disk geometry. A typical
   original XT configuration uses a 5.25-inch, 360 KB drive.
3. Run `make xt-image` and insert `build/xt.img` into that 360 KB drive. Use
   `build/os.img` only if the selected machine, controller, and drive support
   1.44 MB media; a stock XT drive cannot read that density.
4. Boot/reset from drive A. Confirm that `Hello, world!` is visible, then leave
   it running briefly to confirm that the idle loop remains stable.

This manual test is a separate verification step; QEMU cannot substitute for it.

## Future extensions

- [Open Watcom v2](https://github.com/open-watcom/open-watcom-v2) for later 16-bit
  C experiments. It is not a dependency of this assembly-only build.
- GDB with QEMU's debugging interface, or emulator debugger facilities.
- BIOS keyboard input and loading additional sectors.

These extensions are intentionally unimplemented in this milestone.

## Verification on the implementation host (2026-10-10)

- NASM 3.02 and Python 3.13.15 assembled and validated the sector and both floppy
  images. The commands from the Make recipes were executed directly using Git
  Bash's POSIX utilities. All ten additional checker cases passed, including
  damaged signatures, missing messages, wrong sizes, mismatched sectors, missing
  required media, and an absent optional XT image.
- The executable portion of the assembled sector was reviewed with NDISASM:
  instructions through the idle loop use only 8086/8088 encodings. The message
  and padding are data, not executable instructions.
- Windows QEMU 11.1.0 booted `build/os.img` using its **graphical GTK backend**.
  Its rendered screen was captured through QMP and visually inspected:
  `Hello, world!` appeared at the top left. Guest registers showed execution in
  the idle loop with `CS`, `DS`, `ES`, and `SS` equal to zero, `SP=0x7C00`, and
  interrupts enabled. The verification session was closed afterward.
- `make build`, `make check`, and `make run` were attempted together but could
  not execute: Windows Application Control blocked the downloaded MSYS2 GNU
  Make 4.4.1 executable. These targets have **not** been verified through Make
  on this host; successful direct build/check execution is reported separately.
- `wsl --list --verbose` failed with
  `Wsl/CallMsi/Install/REGDB_E_CLASSNOTREG` (class not registered). No working
  Ubuntu distribution could be inspected, and apt installation was not run.
  The manual host setup step is to repair/install WSL2 with Ubuntu 24.04, then
  install the listed missing packages and run the Make targets in Ubuntu.
- Manual 86Box testing was not performed. No BIOS ROMs were obtained.

NASM and QEMU were installed locally under the parent workspace's ignored
`.tmp/tools/` directory; Python and Git Bash were already installed. The QEMU
installer's SHA-512 checksum and GNU Make package's SHA-256 checksum matched
their published values. No Windows application-control policy was changed.
Until WSL is repaired, this host can rerun the validator and graphical emulator
from PowerShell inside `8088-hello`:

```powershell
python scripts/check_boot.py
& '..\.tmp\tools\qemu\qemu-system-i386.exe' -drive 'file=build/os.img,format=raw,if=floppy' -boot a -display gtk
```
