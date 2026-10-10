SHELL := /bin/sh
.DEFAULT_GOAL := build
.DELETE_ON_ERROR:

NASM ?= nasm
PYTHON ?= python3
QEMU ?= qemu-system-i386
# Leave empty to let QEMU select its graphical display (GTK under WSLg).
QEMU_DISPLAY ?=

.PHONY: build run check clean xt-image

build: build/boot.bin build/os.img

build/boot.bin: boot.asm | build/
	$(NASM) -f bin -Werror -o "$@" "$<"

build/:
	mkdir -p "$@"

build/os.img: build/boot.bin
	dd if=/dev/zero of="$@" bs=512 count=2880
	dd if="$<" of="$@" bs=512 count=1 conv=notrunc

build/xt.img: build/boot.bin
	dd if=/dev/zero of="$@" bs=512 count=720
	dd if="$<" of="$@" bs=512 count=1 conv=notrunc

xt-image: build/xt.img

check: build
	$(PYTHON) scripts/check_boot.py

run: build
	$(QEMU) -drive file=build/os.img,format=raw,if=floppy -boot a $(if $(QEMU_DISPLAY),-display $(QEMU_DISPLAY))

clean:
	rm -f build/boot.bin build/os.img build/xt.img
