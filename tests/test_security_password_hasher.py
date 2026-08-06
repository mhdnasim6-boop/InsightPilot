"""Tests for PasswordHasher: PBKDF2-HMAC-SHA256 hashing/verification."""

from backend.security.authentication.password_hasher import PasswordHasher


def test_hash_produces_a_self_describing_string() -> None:
    hashed = PasswordHasher().hash("correct horse battery staple")
    algorithm, iterations, salt, digest = hashed.split("$")
    assert algorithm == "pbkdf2_sha256"
    assert int(iterations) > 0
    assert salt and digest


def test_hashing_the_same_password_twice_produces_different_hashes() -> None:
    hasher = PasswordHasher()
    first = hasher.hash("hunter2")
    second = hasher.hash("hunter2")
    assert first != second  # different random salts


def test_verify_accepts_the_correct_password() -> None:
    hasher = PasswordHasher()
    hashed = hasher.hash("hunter2")
    assert hasher.verify("hunter2", hashed) is True


def test_verify_rejects_the_wrong_password() -> None:
    hasher = PasswordHasher()
    hashed = hasher.hash("hunter2")
    assert hasher.verify("not-hunter2", hashed) is False


def test_verify_rejects_a_malformed_hash() -> None:
    assert PasswordHasher().verify("hunter2", "not-a-real-hash") is False


def test_verify_rejects_an_unrecognized_algorithm_prefix() -> None:
    assert PasswordHasher().verify("hunter2", "md5$1$salt$digest") is False
