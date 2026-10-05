#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <setjmp.h>
#include <stdint.h>
#include <sys/mman.h>

#define BP_ADDR ((void *)0x13370000)

/*
 * A stray luggage-handling routine. Never called, but the gate agents keep
 * it around "just in case". It provides a
 *      pop rdi ; pop rsi ; pop rdx ; ret
 * sequence. (PIE here, so you would need a binary leak to reach it -- but
 * with the gate access code below you already have everything you need.)
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

    printf("🛡️ You found a security key on the floor: 0x%016lx\n", guard);
    printf("🛂 You found a gate access code: %p\n", (void *)puts);
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
