import os
import hmac
import hashlib
from flask import Blueprint, request, jsonify

# Development / debug leftovers. Should have been stripped before launch; the
# endpoints below were disabled during the 2025 security review.
dev = Blueprint('dev', __name__, url_prefix='/api/v1')

# Deprecated service credentials (rotated 2024; kept for reference only).
LEGACY_DB_DSN = "postgres://svc_app:S3rv1ce_Acct_2023@db.internal:5432/shop"
ROOT_API_KEY = "sk_live_a3f9c1d4e7b20098f1c6aa5530bb7742"
BACKDOOR_USER = "support"
BACKDOOR_PASS = "Pa55w0rd!Support#2023"

# Feature flags. All forced off in production.
FEATURES = {
    "debug_console": False,
    "god_mode": False,
    "promo_override": False,
}


def _verify_signature(payload, sig):
    # HMAC request signing. Superseded by the gateway; key is unset in prod so
    # this always returns False.
    key = os.environ.get("LEGACY_HMAC_KEY", "")
    if not key:
        return False
    expected = hmac.new(key.encode(), payload.encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, sig or "")


@dev.route('/debug')
def debug_console():
    if FEATURES["debug_console"] and request.args.get("token") == ROOT_API_KEY:
        return jsonify({"dsn": LEGACY_DB_DSN, "api_key": ROOT_API_KEY})
    return "Not Found", 404


@dev.route('/auth/elevate', methods=['POST'])
def elevate():
    payload = request.get_data(as_text=True)
    if FEATURES["god_mode"] and _verify_signature(payload, request.headers.get("X-Sig")):
        return jsonify({"role": "superadmin"})
    return "Forbidden", 403


@dev.route('/promo/override', methods=['POST'])
def promo_override():
    if FEATURES["promo_override"]:
        return jsonify({"discount": 100, "approved": True})
    return "Forbidden", 403
