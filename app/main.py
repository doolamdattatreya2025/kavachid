"""
KavachID demo backend -- "Verify then Vanish".

Endpoints:
  POST /verify            Submit ID number + DOB -> get back a signed
                           attribute token. Raw data is wiped before the
                           response is even serialized.
  POST /verify-document    Upload a scanned document image -> get a
                           noise-tolerant fingerprint hash (no attribute
                           extraction/OCR in this demo).
  POST /verify-token        A relying party (bank, app, landlord) checks
                           a token's validity and reads only the boolean
                           attribute claims -- never raw PII.
"""

import gc

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import JSONResponse

from .auth import issue_attribute_token, verify_attribute_token
from .crypto_utils import encrypt_ephemeral, salted_hash
from .normalization import fingerprint_document
from .schemas import TokenCheckResponse, VerifyRequest, VerifyResponse

app = FastAPI(
    title="KavachID Demo",
    description="Reference implementation of the Verify-and-Discard privacy-preserving KYC pattern.",
    version="0.1.0",
)


@app.get("/")
def root():
    return {"service": "KavachID", "philosophy": "Verify then Vanish."}


@app.post("/verify", response_model=VerifyResponse)
def verify(payload: VerifyRequest):
    # --- Privacy Buffer: encrypt immediately, in memory only ---
    capsule = encrypt_ephemeral(payload.id_number.encode("utf-8"))

    # --- Validation Engine: derive attributes, never persist raw values ---
    today = _today()
    age_years = (today - payload.date_of_birth).days // 365
    is_adult = age_years >= 18

    # Salted hash stands in for the raw ID number in any logs/DB.
    id_hash = salted_hash(payload.id_number)

    # --- Purge: drop references to raw plaintext/key material now ---
    capsule.wipe()
    del payload
    gc.collect()

    token = issue_attribute_token({"is_adult": is_adult, "id_hash": id_hash})
    return VerifyResponse(token=token, id_hash=id_hash)


@app.post("/verify-document")
async def verify_document(file: UploadFile = File(...)):
    raw_bytes = await file.read()
    try:
        fingerprint = fingerprint_document(raw_bytes)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    finally:
        # Purge: don't keep the uploaded bytes around after fingerprinting.
        del raw_bytes
        gc.collect()

    return JSONResponse({"fingerprint": fingerprint, "message": "Raw image discarded."})


@app.post("/verify-token", response_model=TokenCheckResponse)
def check_token(token: str):
    try:
        claims = verify_attribute_token(token)
        return TokenCheckResponse(valid=True, claims=claims)
    except ValueError as exc:
        return TokenCheckResponse(valid=False, error=str(exc))


def _today():
    from datetime import date

    return date.today()
