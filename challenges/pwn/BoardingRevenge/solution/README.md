# Boarding Revenge — author writeup

Revenge of `Boarding`. The source is identical to the original except for two
changes:

1. **The libc leak is gone.** `found_stuff()` no longer prints
   `(void *)puts`. You still get the **pointer-guard** leak (`%fs:0x30`) —
   without it you cannot forge the mangled `rbp`, so the pivot would be
   impossible.
2. **The binary is non-PIE** (`-no-pie`). Every PLT/GOT entry, every gadget,
   and `.bss` now live at a fixed address.

Everything else is the same: `-fno-stack-protector` (no canary), Partial RELRO
(lazy binding / writable `.got.plt`), and the shipped `libc.so.6` + loader
(glibc 2.36) via `RUNPATH .`.

```
Arch: amd64   PIE: No   RELRO: Partial   Canary: No   NX: Yes
```

## The bug (unchanged)

`load_profile()` `read`s **80** bytes into a **64**-byte `profile`, so 16 bytes
overflow into the following `jmp_buf`, overwriting `jmpbuf[0]` (`rbx`) and
`jmpbuf[1]` (`rbp`). On x86-64 glibc, the `rbp`, `rsp` and `PC` slots of a
`jmp_buf` are **pointer-mangled**: `stored = rol(value ^ guard, 0x11)`. We only
reach `rbp` (and leave `rsp`/`PC` intact), so `longjmp` returns normally into
`load_profile`, but with a **rbp we control**.

`load_profile`'s epilogue is `leave ; ret` → `mov rsp, rbp ; pop rbp ; ret`, so
controlling `rbp` is a **stack pivot**: `rsp` becomes our forged value and the
`ret` starts a ROP chain. We pivot into the fixed `mmap` scratch page at
`0x13370000`, which holds the 80 bytes we just sent.

## Why it's harder now

With no libc pointer you must ROP, but the binary is almost gadget-free — only
`pop rbp ; ret` and `leave ; ret`. The loader (which *is* gadget-rich) is still
ASLR'd and we have no binary/loader leak. The author therefore left exactly one
argument-control gadget in the binary:

```
baggage_reclaim:  pop rdi ; pop rsi ; pop rdx ; ret
```

Because the binary is non-PIE, this gadget — and `read@plt`, `puts@plt`,
`.bss` — are all at fixed addresses.

## Two gotchas

* **The pivot page is tiny.** `0x13370000` is only `0x108` bytes with nothing
  mapped below it, so any *libc* call (e.g. `puts`) blows through the bottom
  into an unmapped page and segfaults. A bare `read` **syscall wrapper** is
  shallow enough to survive, so the first thing we do is `read` a bigger chain
  into roomy, fixed `.bss` and pivot there.
* **No leak is handed to us, so make one.** With lazy binding, call
  `puts(puts@got)` to print the resolved libc address of `puts`, giving the
  libc base. The shipped `libc.so.6` then gives `system` and `/bin/sh`.

## Chain

1. **Pivot** (≤ 80 B, in `0x13370000`): forge `jmpbuf[1] = rol(0x13370000 ^
   guard, 0x11)`; chain = `read(0, .bss, 0x400)` then re-pivot (`pop rbp` +
   `leave ; ret`) into `.bss`.
2. **Stage 2** (in `.bss`, roomy stack): `puts(puts@got)` → leak libc; then
   `read(0, .bss2, 0x400)` and pivot to stage 3.
3. **Stage 3**: `system("/bin/sh")`.

The self-leak via `puts` can be truncated by a NUL byte (~1/256); just
reconnect. `solve.py` validates the leak and exits cleanly if so.

## Run

```
cd src && cp ../solution/solve.py . && ../../...   # or just:
python3 solution/solve.py            # local (needs ./boarding ./libc.so.6 ./ld in cwd)
python3 solution/solve.py HOST PORT  # remote
```

Verified against the shipped binary + glibc 2.36 with ASLR on: 12/12 shells.

## Rebuilding the binary

```
gcc -no-pie -fno-pie -fno-stack-protector -Wl,-z,lazy -O0 \
    -o boarding boarding_revenge.c
patchelf --set-interpreter './ld-linux-x86-64.so.2' boarding
patchelf --set-rpath '.' boarding
```
