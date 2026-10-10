# Intel 8088 bare-metal projects

Experiments and bootable software for original Intel 8088-compatible IBM PCs.
All project code, comments, and documentation are written in English.

- [8088 Hello World](8088-hello/README.md): a custom BIOS boot sector with no
  operating system, assembled with NASM.
- [FreeDOS 1.4 source build](freedos-1.4/README.md): an 8086/8088 kernel and English
  command interpreter compiled from the distribution's source packages.

Each project keeps generated artifacts in its ignored `build/` directory.
QEMU supports fast iteration; use an appropriate 8088 machine in 86Box or original
hardware for a separate compatibility test.
