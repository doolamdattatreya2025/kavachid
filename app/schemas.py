from datetime import date

from pydantic import BaseModel, Field


class VerifyRequest(BaseModel):
    """
    A synthetic identity payload for the demo. In a real deployment this
    would arrive from a document-scanning frontend (e.g. an OCR step
    reading an Aadhaar/PAN card) -- this demo skips OCR and lets you
    pass the extracted fields directly so the crypto pipeline can be
    exercised end-to-end.
    """

    id_number: str = Field(..., description="Unique ID/document number. Never stored.")
    date_of_birth: date = Field(..., description="Never stored; only used to derive is_adult.")


class VerifyResponse(BaseModel):
    token: str
    id_hash: str
    message: str = "Raw PII discarded. Token issued."


class TokenCheckResponse(BaseModel):
    valid: bool
    claims: dict | None = None
    error: str | None = None
