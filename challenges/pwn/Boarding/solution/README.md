# Boarding — author writeup

The terminal leaks two things in `found_stuff()`:

* the glibc **pointer guard** (`%fs:0x30`), and
* a **libc** pointer (`&puts`) — the "gate access code".

`load_profile()` `read`s 80 bytes into a 64-byte buffer, overflowing 16 bytes
into the trailing `jmp_buf` and overwriting the (pointer-mangled) `rbp` slot.
With the guard leak you forge it as `rol(value ^ guard, 0x11)`; `longjmp`
returns into `load_profile`, whose `leave ; ret` epilogue then pivots the stack
to your forged `rbp`. Pivot into the fixed `mmap` page `0x13370000`.

With the libc leak in hand, drop a short `execve("/bin/sh", 0, 0)` ROP chain
(libc gadgets) into that page. `execve` is a syscall, so it is happy on the
tiny pivot stack, and the chain fits the ~8-slot window.

```
python3 solution/solve.py            # local
python3 solution/solve.py HOST PORT  # remote
```

## Note on the `baggage_reclaim` gadget

This binary (PIE) contains an unused `pop rdi ; pop rsi ; pop rdx ; ret`
gadget. It is **not needed** here — the free libc leak already gives you every
gadget in libc, and the gadget sits at a PIE-randomized address anyway. It
exists so this binary and its non-PIE sibling **Boarding Revenge** differ only
by *{libc leak removed, PIE → non-PIE}*; in the revenge, where there is no libc
leak, that fixed gadget is the one argument-control primitive you get.

## Rebuilding

```
gcc -pie -fPIE -fno-stack-protector -Wl,-z,lazy -O0 -o boarding boarding.c
patchelf --set-interpreter './ld-linux-x86-64.so.2' boarding
patchelf --set-rpath '.' boarding
```
