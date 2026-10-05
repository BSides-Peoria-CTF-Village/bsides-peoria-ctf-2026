FROM pwn.red/jail

COPY --from=ubuntu / /srv

COPY flag.txt /srv/app/flag.txt
COPY src/boarding /srv/app/run

COPY src/libc.so.6 /srv/app/libc.so.6
COPY src/ld-linux-x86-64.so.2 /srv/app/ld-linux-x86-64.so.2

RUN chmod +x /srv/app/run
