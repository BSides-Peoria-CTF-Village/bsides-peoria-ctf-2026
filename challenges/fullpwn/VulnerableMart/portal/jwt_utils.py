import json
import hmac
import hashlib
import base64

from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.exceptions import InvalidSignature


def b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b'=').decode()


def b64url_decode(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + '=' * (-len(s) % 4))


def _int_b64(n: int) -> str:
    return b64url(n.to_bytes((n.bit_length() + 7) // 8, 'big'))


class JWT:
    """Minimal JWT signer/verifier.

    Tokens are issued with RS256. The verifier reads the algorithm from the
    token header and, for HS256, uses the RSA public key (its PEM bytes) as the
    HMAC secret. That is the intended RS256/HS256 algorithm-confusion weakness:
    anyone who can read the published public key can forge a valid HS256 token.
    """

    def __init__(self, private_pem: bytes, public_pem: bytes, kid: str):
        self.private_key = serialization.load_pem_private_key(private_pem, password=None)
        self.public_key = serialization.load_pem_public_key(public_pem)
        self.public_pem = public_pem
        self.kid = kid

    def sign(self, payload: dict) -> str:
        header = {"alg": "RS256", "typ": "JWT", "kid": self.kid}
        signing_input = (
            b64url(json.dumps(header, separators=(',', ':')).encode())
            + '.'
            + b64url(json.dumps(payload, separators=(',', ':')).encode())
        )
        sig = self.private_key.sign(signing_input.encode(), padding.PKCS1v15(), hashes.SHA256())
        return signing_input + '.' + b64url(sig)

    def verify(self, token: str) -> dict:
        header_b64, payload_b64, sig_b64 = token.split('.')
        header = json.loads(b64url_decode(header_b64))
        signing_input = (header_b64 + '.' + payload_b64).encode()
        sig = b64url_decode(sig_b64)
        alg = header.get('alg')

        if alg == 'RS256':
            self.public_key.verify(sig, signing_input, padding.PKCS1v15(), hashes.SHA256())
        elif alg == 'HS256':
            expected = hmac.new(self.public_pem, signing_input, hashlib.sha256).digest()
            if not hmac.compare_digest(expected, sig):
                raise InvalidSignature("bad HS256 signature")
        else:
            raise InvalidSignature(f"unsupported alg: {alg}")

        return json.loads(b64url_decode(payload_b64))

    def jwks(self) -> dict:
        nums = self.public_key.public_numbers()
        return {
            "keys": [{
                "kty": "RSA",
                "use": "sig",
                "alg": "RS256",
                "kid": self.kid,
                "n": _int_b64(nums.n),
                "e": _int_b64(nums.e),
            }]
        }
