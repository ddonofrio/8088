PYTHON ?= python3
QEMU ?= qemu-system-i386

.PHONY: build check run xt-image clean

build:
	$(PYTHON) scripts/build.py

check:
	$(PYTHON) scripts/check.py

run: check
	$(PYTHON) scripts/run.py --qemu $(QEMU)

xt-image: check
	@echo build/freedos-360k.img is ready for a 360 KB XT drive.

clean:
	$(PYTHON) scripts/clean.py
