# KavachID — Verify-and-Discard KYC

**"Verify then vanish."**

KavachID is a small backend I built to try out a simple idea: checking
someone's identity shouldn't mean keeping a permanent copy of their ID
document. Most systems today treat "verify this person" as a chance to
collect data — they scan your ID, save it, and now it sits in a database
forever as a breach risk. This project treats it as a one-time check
instead: look at the document, give back a yes/no answer, and forget
everything else.

This is not a production KYC system — just a working proof of concept for
the idea. See [Known limitations](#known-limitations) for what's missing
before you'd ever run real ID documents through this.

## The problem I'm solving

Every company that keeps a copy of your Aadhaar/PAN card, passport, or
driver's license is one more place that document could leak from. Most of
the time, the company doesn't even need your actual document — they just
need one fact: are you over 18? Are you who you say you are? A yes/no
answer is enough. Keeping the whole document around "just in case" is
what turns a simple sign-up into a long-term risk.

## How it works

```
Upload ──▶ Privacy Buffer ──▶ Validation Engine ──▶ Purge ──▶ Signed Token
 (HTTPS)    (AES-GCM, RAM      (derive boolean         (wipe raw    (short-lived
             only)              attributes)             plaintext)   JWT claim)
```

| Concern | How it's handled |
|---|---|
| Storage you can't reverse | Salted + peppered SHA-256 (`app/crypto_utils.py`) |
| Data only exists briefly | AES-GCM with a key made fresh per request, wiped right after use |
| Only sends back a yes/no fact | `is_adult: true/false` instead of a raw date of birth |
| Passing trust along | Short-lived signed JWT (`app/auth.py`) |
| Blurry or tilted scans | OpenCV cleanup + perceptual hashing (`app/normalization.py`) |

### Why perceptual hashing for document scans

A normal SHA-256 hash of an image changes completely if even one pixel
changes — so a slightly blurry photo, or a scan tilted by a couple
degrees, would hash as a totally different file, even though it's clearly
the same document. To fix that, I clean up the image first (turn it
grayscale, remove noise, straighten it), then take a perceptual hash of
the result — a type of hash that stays close even with small real-world
differences. That hash gets salted for storage, same as everything else.

## API

### `POST /verify`
```json
{ "id_number": "ABCD1234EFGH", "date_of_birth": "1990-05-14" }
```
Returns a signed token and a salted hash. The raw `id_number` and
`date_of_birth` never appear in the response, and they're wiped from
memory before the response is even built.

### `POST /verify-document`
Upload a scanned document image, get back a fingerprint that stays stable
even with small scan differences. The raw image is thrown away right
after the fingerprint is made.

### `POST /verify-token?token=...`
This is the one a relying party (a bank, a rental app, an age-gated
service) would call. It checks the token's signature and expiry, and
returns only the yes/no facts — it never sees the actual document.

## Running it locally

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload
# then open http://127.0.0.1:8000/docs
```

## Tests

```bash
pip install -r requirements-dev.txt
pytest -v
```

## Known limitations

I built this to show the idea works, not as a certified KYC system. A few
things I left out on purpose for now:

- **No real OCR.** `/verify` expects clean, structured fields — not a raw
  photo of an ID card. A real system would need a document-scanning/OCR
  step in front of this (which brings its own privacy questions).
- **Document fingerprints use a new salt each time**, so scanning the
  same document twice won't give you the exact same stored fingerprint.
  That's good for privacy, but a real duplicate-detection feature would
  need a fixed salt per document or per session instead.
- **No database.** Nothing is saved — no stored hashes, no history log,
  no way to catch duplicate accounts.
- **Secrets are only kept in memory**, made fresh each time the app
  starts. A real deployment would need a proper secrets manager (like KMS
  or Vault) with key rotation.
- **No zero-knowledge proofs.** That would be a good next step for this
  idea, but it's not built yet — this is just the verify-and-discard part.
- Not security-audited. Please don't run real ID documents through this
  without a proper review first.

## Author

Built by [Dattatreya](https://github.com/doolamdattatreya2025) — cybersecurity student.

## License

MIT — use it however you like, no warranty.
