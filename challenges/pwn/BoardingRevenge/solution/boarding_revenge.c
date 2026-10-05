#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <setjmp.h>
#include <stdint.h>
#include <sys/mman.h>

#define BP_ADDR ((void *)0x13370000)

/*
 * A stray luggage-handling routine. Never called, but the gate agents keep
 * it around "just in case". It happens to provide a
 *      pop rdi ; pop rsi ; pop rdx ; ret
 * sequence so an operator can line up the paperwork by hand.
 *
 * (Revenge note: the original Boarding handed you a libc pointer for free.
 *  This one does not -- but the binary is non-PIE, so every gadget, PLT and
 *  GOT entry lives at a fixed address. This routine is the only argument-
 *  control gadget you get.)
 */
__attribute__((used, naked)) void baggage_reclaim(void)
{
    __asm__ volatile(
        "pop %rdi\n\t"
        "pop %rsi\n\t"
        "pop %rdx\n\t"
        "ret\n\t"
    );
}

struct boarding_pass {
    char profile[64];
    jmp_buf recovery;
};

void found_stuff(void)
{
    uint64_t guard;

    __asm__ volatile (
        "mov %%fs:0x30, %0"
        : "=r"(guard)
    );

    /* The pointer guard still falls out of the agent's pocket. You will need
     * it to forge the mangled rbp inside the jmp_buf -- but the gate access
     * code (a libc pointer) is gone this time. */
    printf("🛡️ You found a security key on the floor: 0x%016lx\n", guard);
}

static void load_profile(void)
{
    struct boarding_pass *bp = mmap(BP_ADDR, sizeof(struct boarding_pass),
                                     PROT_READ | PROT_WRITE,
                                     MAP_PRIVATE | MAP_ANONYMOUS | MAP_FIXED,
                                     -1, 0);

    if (bp == MAP_FAILED) {
        perror("mmap");
        exit(1);
    }

    puts("✈️ Enter boarding pass data:");

    if (setjmp(bp->recovery) != 0) {
        puts("🛄 validating ticket...");
        return;
    }

    read(STDIN_FILENO, bp->profile, 80);

    puts("🛫 Boarding pass accepted.");

    longjmp(bp->recovery, 1);
}

int main(void)
{
    setvbuf(stdout, NULL, _IONBF, 0);
    setvbuf(stderr, NULL, _IONBF, 0);
    found_stuff();
    load_profile();

    puts("🛬 Ticket successfully validated.");
    return 0;
}
