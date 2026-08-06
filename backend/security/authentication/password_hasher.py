"""PasswordHasher: PBKDF2-HMAC-SHA256 password hashing — no new dependency.

PBKDF2-HMAC-SHA256 (NIST SP 800-132's own recommended construction) is
built entirely from the standard library (``hashlib``/``hmac``/``secrets``)
— no ``bcrypt``/``argon2`` C-extension dependency needed for a
production-quality result. Every hash carries its own random salt and
iteration count (``pbkdf2_sha256$<iterations>$<salt>$<hash>``, mirroring
Django's own self-describing hash format), so the iteration count can be
raised in a future release without invalidating already-stored hashes.
"""

import hashlib
import hmac
import secrets

_ALGORITHM = "pbkdf2_sha256"
_ITERATIONS = 260_000  # OWASP's current (2023+) minimum recommendation for PBKDF2-HMAC-SHA256
_SALT_BYTES = 16


class PasswordHasher:
    """Hashes and verifies passwords. Never stores or logs a plaintext password."""

    def hash(self, password: str) -> str:
        """Return a new, self-describing hash for ``password``. A fresh random salt every call —
        hashing the same password twice produces two different (both valid) hashes."""
        salt = secrets.token_hex(_SALT_BYTES)
        digest = self._derive(password, salt, _ITERATIONS)
        return f"{_ALGORITHM}${_ITERATIONS}${salt}${digest}"

    def verify(self, password: str, hashed: str) -> bool:
        """Whether ``password`` matches a hash previously produced by ``hash()``.
        Constant-time comparison (``hmac.compare_digest``) — never a plain ``==``,
        which would leak timing information about how many leading bytes matched."""
        try:
            algorithm, iterations_str, salt, expected_digest = hashed.split("$")
        except ValueError:
            return False
        if algorithm != _ALGORITHM:
            return False
        actual_digest = self._derive(password, salt, int(iterations_str))
        return hmac.compare_digest(actual_digest, expected_digest)

    def _derive(self, password: str, salt: str, iterations: int) -> str:
        return hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), salt.encode("utf-8"), iterations
        ).hex()
