CPU 8086
BITS 16
ORG 0x7C00

; Normalize both BIOS entry conventions: 0000:7C00 and 07C0:0000.
    cli
    jmp 0x0000:start

start:
    xor ax, ax
    mov ss, ax
    mov sp, 0x7C00             ; The stack grows below the boot sector.
    mov ds, ax
    mov es, ax
    cld
    sti

    ; Clear the screen by resetting its current mode (including MDA mode 7).
    mov ah, 0x0F
    int 0x10
    xor ah, ah
    int 0x10

    ; Establish data segments again after the BIOS calls.
    xor ax, ax
    mov ds, ax
    mov es, ax
    mov si, message
    xor bx, bx                ; BH = display page 0, required by early BIOSes.
    mov bl, 0x07              ; Foreground color for graphics-mode teletype.

print_next:
    cld
    lodsb
    test al, al
    jz idle
    mov ah, 0x0E
    ; Preserve the string address and display page across BIOS implementations.
    push ds
    push si
    push bx
    int 0x10
    pop bx
    pop si
    pop ds
    jmp print_next

idle:
    sti
    hlt
    jmp idle

message db 'Hello, world!', 0

times 510 - ($ - $$) db 0
dw 0xAA55
