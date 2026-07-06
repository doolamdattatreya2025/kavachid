# KavachID — Verify-and-Discard KYC

**"Verify then Vanish."** A reference implementation of a privacy-preserving
identity verification pattern: instead of storing a copy of someone's ID
document, the system validates it in memory, issues a signed boolean
claim (e.g. `is_adult: true`), and discards the raw data before the
request even finishes.

> This project started life as a hackathon pitch deck (Cybersecurity
> Innovation Challenge). This repo is a working backend prototype of
> the core "Gatekeeper Model" from that pitch — not a production KYC
> system. See [Known limitations](#known-limitations) before using it
> for anything real.

## The problem

Centralized storage of documents like Aadhaar/PAN cards is a standing
liability: every organization that keeps a copy is another place that
data can leak from. Verification is treated as a *data-sharing* event
when it should be a *validation* event — the relying party needs to
know "is this person over 18?", not "here is their exact birth date
and ID number forever."

## How this implementation works

```
Upload ──▶ Privacy Buffer ──▶ Validation Engine ──▶ Purge ──▶ Signed Token
 (HTTPS)    (AES-GCM, RAM      (derive boolean         (wipe raw    (short-lived
             only)              attributes)             plaintext)   JWT claim)
```

| Concern | Implementation |
|---|---|
| Non-reversible storage | Salted + peppered SHA-256 (`app/crypto_utils.py`) |
| Ephemeral processing | AES-GCM with a per-request key, wiped after use |
| Attribute-only output | `is_adult: true/false` instead of raw DOB |
| Trust hand-off | Short-lived signed JWT (`app/auth.py`) |
| Noisy scans (blur/tilt) | OpenCV normalization + perceptual hashing (`app/normalization.py`) |

### Why perceptual hashing for documents?

A plain SHA-256 of an image changes completely if a single pixel does
(a slightly blurry photo or a 2° tilt looks like a totally different
file). This project normalizes the scan (grayscale → denoise →
deskew) and takes a **perceptual hash** of the result, which stays
close under small real-world variations — then salts *that* for
one-way storage.

## API

### `POST /verify`
```json
{ "id_number": "ABCD1234EFGH", "date_of_birth": "1990-05-14" }
```
→ Returns a signed token and a salted hash. The raw `id_number` and
`date_of_birth` never appear in the response and are wiped from
memory before the response is built.

### `POST /verify-document`
Multipart file upload of a scanned document image → returns a
noise-tolerant fingerprint. Raw image bytes are discarded after
fingerprinting.

### `POST /verify-token?token=...`
A relying party (bank, rental app, age-gated service) checks a
token's signature/expiry and reads only the attribute claims —
never the underlying document.

## Running locally

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload
# → http://127.0.0.1:8000/docs for interactive API docs
```

## Tests

```bash
pip install -r requirements-dev.txt
pytest -v
```

## Known limitations

This is a hackathon-grade prototype meant to demonstrate the pattern,
not a certified KYC system. Before treating this as production-ready:

- **No real OCR/document parsing.** `/verify` takes structured fields
  directly; a real system needs a document-scanning/OCR step feeding
  into this pipeline (and that step has its own privacy requirements).
- **Document fingerprints are salted per-call**, so two scans of the
  same document won't produce identical stored fingerprints. That's
  correct for non-reversibility, but a real duplicate-detection
  feature would need a fixed per-document or per-session salt.
- **No persistence layer.** There's no database here — hashes/tokens
  aren't stored anywhere, so there's no duplicate-account detection
  or audit trail yet.
- **Secrets are process-local.** The JWT secret and hashing pepper are
  generated in-memory by default; production use requires a real
  secrets manager (KMS/Vault) with rotation.
- **No formal Zero-Knowledge Proof implementation.** The pitch deck's
  "Tier 2" (ZKP) is a stated future direction, not implemented here —
  this repo only covers "Tier 1: Verify-and-Discard."
- Not audited. Don't use this for real identity documents without a
  proper security review.

## License

MIT — do whatever you like with it, no warranty implied.
