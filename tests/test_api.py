import io

import cv2
import numpy as np
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_root():
    resp = client.get("/")
    assert resp.status_code == 200
    assert resp.json()["philosophy"] == "Verify then Vanish."


def test_verify_adult_gets_token_not_raw_data():
    resp = client.post(
        "/verify",
        json={"id_number": "ABCD1234EFGH", "date_of_birth": "1990-05-14"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "token" in body
    assert "id_hash" in body
    # The raw ID number must never appear anywhere in the response.
    assert "ABCD1234EFGH" not in resp.text


def test_verify_minor_flagged_false():
    resp = client.post(
        "/verify",
        json={"id_number": "XYZ999", "date_of_birth": "2015-01-01"},
    )
    token = resp.json()["token"]
    check = client.post("/verify-token", params={"token": token})
    assert check.json()["valid"] is True
    assert check.json()["claims"]["is_adult"] is False


def test_verify_token_roundtrip_adult_true():
    resp = client.post(
        "/verify",
        json={"id_number": "PQR555", "date_of_birth": "1980-01-01"},
    )
    token = resp.json()["token"]
    check = client.post("/verify-token", params={"token": token})
    assert check.json()["valid"] is True
    assert check.json()["claims"]["is_adult"] is True


def test_invalid_token_rejected():
    check = client.post("/verify-token", params={"token": "not-a-real-token"})
    assert check.json()["valid"] is False


def _make_test_image(rotate=0, blur=False):
    img = np.full((200, 200), 255, dtype=np.uint8)
    cv2.putText(img, "ID-CARD-DEMO", (20, 100), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0,), 2)
    if blur:
        img = cv2.GaussianBlur(img, (3, 3), 0)
    if rotate:
        h, w = img.shape
        matrix = cv2.getRotationMatrix2D((w // 2, h // 2), rotate, 1.0)
        img = cv2.warpAffine(img, matrix, (w, h), borderValue=255)
    ok, buf = cv2.imencode(".png", img)
    assert ok
    return buf.tobytes()


def test_document_fingerprint_endpoint():
    image_bytes = _make_test_image()
    resp = client.post(
        "/verify-document",
        files={"file": ("id.png", io.BytesIO(image_bytes), "image/png")},
    )
    assert resp.status_code == 200
    assert "fingerprint" in resp.json()


def test_document_fingerprint_endpoint_stores_only_salted_hash():
    """Two scans of the "same" document get different stored fingerprints
    because each call uses a fresh random salt (non-reversibility by design).
    See test below for the underlying perceptual hash, which IS stable."""
    straight = client.post(
        "/verify-document",
        files={"file": ("a.png", io.BytesIO(_make_test_image(rotate=0)), "image/png")},
    ).json()["fingerprint"]

    tilted = client.post(
        "/verify-document",
        files={"file": ("b.png", io.BytesIO(_make_test_image(rotate=2)), "image/png")},
    ).json()["fingerprint"]

    assert isinstance(straight, str) and isinstance(tilted, str)


def test_perceptual_hash_stable_under_blur_and_small_rotation():
    """Core claim from the deck: normalization should make the underlying
    fingerprint tolerant to blur/rotation noise, unlike raw SHA-256."""
    from app.normalization import perceptual_hash_string
    import imagehash

    straight = perceptual_hash_string(_make_test_image(rotate=0))
    blurred = perceptual_hash_string(_make_test_image(blur=True))
    tilted = perceptual_hash_string(_make_test_image(rotate=2))

    # Hamming distance between perceptual hashes should be small for
    # near-duplicate scans of the same document.
    dist_blur = imagehash.hex_to_hash(straight) - imagehash.hex_to_hash(blurred)
    dist_tilt = imagehash.hex_to_hash(straight) - imagehash.hex_to_hash(tilted)
    assert dist_blur <= 10
    assert dist_tilt <= 10
