# KavachID — Verify-and-Discard KYC

**"Verify then vanish."**

KavachID is a small backend I built to explore a simple idea: identity
verification shouldn't require someone to keep a permanent copy of
your ID document. Most systems today treat "verify this person" as a
data-collection event — they scan your ID, store it, and now it's
sitting in a database forever as a breach risk. This project treats
it as a one-time validation event instead: check the document, hand
back a yes/no answer, and forget everything else.

Not a production KYC system — just a working proof of concept for the
pattern. See [Known limitations](#known-limitations) for what's
missing before you'd ever put real ID documents through this.

## The problem I'm solving

Every company that stores a copy of your Aadhaar/PAN card, passport,
or driver's license is another place that document can leak from.
Most of the time, though, the company doesn't actually need your
document — they need one fact: are you over 18? Are you who you say
you are? A yes/no answer is enough. Keeping the whole document around
"just in case" is the part that turns a routine sign-up into a
long-term liability.

## How it works

```
Upload ──▶ Privacy Buffer ──▶ Validation Engine ──▶ Purge ──▶ Signed Token
 (HTTPS)    (AES-GCM, RAM      (derive boolean         (wipe raw    (short-lived
             only)              attributes)             plaintext)   JWT claim)
```

| Concern | How it's handled |
|---|---|
| Non-reversible storage | Salted + peppered SHA-256 (`app/crypto_utils.py`) |
| Ephemeral processing | AES-GCM with a per-request key, wiped right after use |
| Attribute-only output | `is_adult: true/false` instead of a raw date of birth |
| Trust hand-off | Short-lived signed JWT (`app/auth.py`) |
| Blurry/tilted scans | OpenCV normalization + perceptual hashing (`app/normalization.py`) |

### Why perceptual hashing for the document scans

A plain SHA-256 of an image file changes completely if even one pixel
does — so a slightly blurry photo or a scan tilted by a couple degrees
would hash as a totally different file, even though it's clearly the
same document. To get around that, I normalize the image first
(grayscale → denoise → deskew) and take a perceptual hash of the
result, which stays close under small real-world variations. That
gets salted for storage same as everything else.

## API

### `POST /verify`
```json
{ "id_number": "ABCD1234EFGH", "date_of_birth": "1990-05-14" }
```
Returns a signed token and a salted hash. The raw `id_number` and
`date_of_birth` never show up in the response, and they're wiped from
memory before the response is even built.

### `POST /verify-document`
Upload a scanned document image, get back a noise-tolerant
fingerprint. The raw image bytes are discarded right after
fingerprinting.

### `POST /verify-token?token=...`
This is what a relying party (a bank, a rental app, an age-gated
service) calls — it checks the token's signature and expiry and
returns only the attribute claims. It never sees the underlying
document.

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

I built this to demonstrate the pattern, not as a certified KYC
system. A few things I deliberately left out of scope for now:

- **No real OCR.** `/verify` expects structured fields, not a raw
  photo of an ID card. A real system needs a document-scanning/OCR
  step in front of this (which has its own privacy considerations).
- **Document fingerprints are salted per-call**, so scanning the same
  document twice won't produce an identical stored fingerprint. Good
  for non-reversibility, but a real duplicate-detection feature would
  need a fixed per-document or per-session salt instead.
- **No database.** Nothing here persists — no stored hashes, no audit
  trail, no duplicate-account detection.
- **Secrets live in-memory**, generated fresh per process. A real
  deployment needs a proper secrets manager (KMS/Vault) with rotation.
- **No zero-knowledge proofs.** That's a natural next step for this
  idea, but it's not implemented here — this is just the
  verify-and-discard layer.
- Not security-audited. Please don't run real identity documents
  through this without a proper review first.

## License

MIT — use it however you like, no warranty.
