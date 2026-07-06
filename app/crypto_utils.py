"""
Crypto utilities for KavachID's "Verify-and-Discard" pipeline.

Design goals (from the KavachID concept):
- Raw PII is only ever held in RAM, never written to disk.
- Unique identifiers are salted + hashed (SHA-256) so the stored
  artifact can never be reversed back into the original ID number.
- Any transient encryption uses AES-GCM with a key that lives only
  for the duration of a single request and is discarded afterwards.
"""

import hashlib
import hmac
import os
import secrets
from dataclasses import dataclass

from cryptography.hazmat.primitives.ciphers.aead import AESGCM


# In production this would come from a secrets manager (e.g. AWS KMS /
# HashiCorp Vault) and be rotated regularly. For this demo it's an
# in-memory constant so the project runs standalone.
_SERVER_PEPPER = os.environ.get("KAVACHID_PEPPER", secrets.token_hex(32)).encode()


@dataclass
class EphemeralCapsule:
    """A short-lived encrypted blob. Call `.wipe()` as soon as you're
    done with it -- nothing here is meant to outlive a single request."""

    ciphertext: bytes
    nonce: bytes
    _key: bytes

    def decrypt(self) -> bytes:
        aesgcm = AESGCM(self._key)
        return aesgcm.decrypt(self.nonce, self.ciphertext, None)

    def wipe(self):
        # Best-effort in-memory wipe. CPython doesn't guarantee secure
        # erasure of immutable bytes objects, but this keeps the key
        # from lingering as a live reference beyond this call.
        self._key = b"\x00" * len(self._key)
        self.ciphertext = b""
        self.nonce = b""


def encrypt_ephemeral(plaintext: bytes) -> EphemeralCapsule:
    """Encrypt data with a fresh, request-scoped AES-GCM key."""
    key = AESGCM.generate_key(bit_length=256)
    nonce = secrets.token_bytes(12)
    aesgcm = AESGCM(key)
    ciphertext = aesgcm.encrypt(nonce, plaintext, None)
    return EphemeralCapsule(ciphertext=ciphertext, nonce=nonce, _key=key)


def salted_hash(unique_value: str, request_salt: bytes | None = None) -> str:
    """
    Produce a one-way, salted+peppered fingerprint of a unique identifier
    (e.g. an ID number or a perceptual image hash).

    - `request_salt`: a random, per-request salt (store it alongside the
      hash if you need to re-derive the same hash later for a match,
      e.g. duplicate-account detection).
    - `_SERVER_PEPPER`: a secret held only by the server, never stored
      with the hash, so a stolen database of hashes+salts still can't
      be reversed without the pepper.
    """
    salt = request_salt or secrets.token_bytes(16)
    digest = hashlib.sha256(salt + unique_value.encode("utf-8") + _SERVER_PEPPER)
    return digest.hexdigest()


def constant_time_compare(a: str, b: str) -> bool:
    return hmac.compare_digest(a, b)
