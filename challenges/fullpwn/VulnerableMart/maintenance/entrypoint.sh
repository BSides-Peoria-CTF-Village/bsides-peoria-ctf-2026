#!/bin/sh
set -e

echo "${SHELL_FLAG:-<SHELL_FLAG not set>}" > /root/flag.txt
chmod 644 /root/flag.txt

# Create the gated service account whose /etc/shadow hash feeds the next app's
# registration key. The hash is precomputed at deploy time (gen_flags.py) and
# passed in base64-encoded to keep '$' out of env files.
if ! id mysterioususer >/dev/null 2>&1; then
    useradd -m -s /bin/bash mysterioususer || true
fi
if [ -n "$MYSTERIOUS_USER_HASH_B64" ]; then
    HASH=$(printf '%s' "$MYSTERIOUS_USER_HASH_B64" | base64 -d)
    usermod -p "$HASH" mysterioususer
fi

exec python maintenance.py
