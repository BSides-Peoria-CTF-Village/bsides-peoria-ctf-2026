import hashlib

# Canonical registration-key recipe for the Marketplace Portal.
#
#   registration_key = SHAKE256( shadow_hash + admin_password )  ->  512-bit hex
#
# Where:
#   shadow_hash    = mysterioususer's hashed-password field (the "$6$salt$..."
#                    crypt string) read from /etc/shadow on the maintenance host
#                    (port 50050), obtainable only with root code execution there.
#   admin_password = the store admin password from the first app (recovered via
#                    SQLi + base64 decode).
#
# SHAKE256 with a 512-bit (64-byte) output, lowercase hex (128 hex chars). The
# two inputs are concatenated directly, with no separator, in the order
# shadow_hash then admin_password.
#
# IMPORTANT: this function is the single source of truth. gen_flags.py duplicates
# the same two lines to precompute REGISTRATION_KEY at deploy time; keep them in
# sync.

SHAKE_OUTPUT_BYTES = 64  # 512 bits


def compute_registration_key(shadow_hash: str, admin_password: str) -> str:
    data = (shadow_hash + admin_password).encode()
    return hashlib.shake_256(data).hexdigest(SHAKE_OUTPUT_BYTES)
