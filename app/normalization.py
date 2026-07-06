"""
Handles "real-world noise" in scanned documents.

A raw SHA-256 of image bytes changes completely if a single pixel
changes -- so a slightly blurry photo or a 2-degree tilt of the same
document would look like a totally different file. KavachID instead:

  1. Normalizes the scan (grayscale, denoise, deskew/align).
  2. Computes a *perceptual* hash (pHash) of the normalized image,
     which stays stable across small variations in lighting/angle/blur.
  3. Salts + SHA-256-hashes that perceptual hash for storage, so the
     stored fingerprint is still one-way and non-reversible.
"""

import io

import cv2
import numpy as np
from PIL import Image
import imagehash

from .crypto_utils import salted_hash


def _deskew(gray: np.ndarray) -> np.ndarray:
    """Estimate and correct small rotations using the image's minAreaRect."""
    coords = np.column_stack(np.where(gray < 250))
    if coords.size == 0:
        return gray
    angle = cv2.minAreaRect(coords)[-1]
    if angle < -45:
        angle = -(90 + angle)
    else:
        angle = -angle
    (h, w) = gray.shape[:2]
    center = (w // 2, h // 2)
    matrix = cv2.getRotationMatrix2D(center, angle, 1.0)
    return cv2.warpAffine(gray, matrix, (w, h), flags=cv2.INTER_CUBIC,
                           borderMode=cv2.BORDER_REPLICATE)


def normalize_document_image(raw_bytes: bytes) -> Image.Image:
    """Grayscale -> denoise -> deskew. Returns a PIL Image (in-memory only)."""
    array = np.frombuffer(raw_bytes, dtype=np.uint8)
    bgr = cv2.imdecode(array, cv2.IMREAD_COLOR)
    if bgr is None:
        raise ValueError("Could not decode image bytes")

    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    denoised = cv2.fastNlMeansDenoising(gray, h=10)
    aligned = _deskew(denoised)
    return Image.fromarray(aligned)


def perceptual_hash_string(raw_bytes: bytes) -> str:
    """
    Return the raw perceptual hash (as a hex string) of a normalized
    document image. This value itself is stable/comparable across
    blur, small rotations, and lighting changes -- unlike SHA-256 of
    raw bytes -- which is what makes the "Real-World Noise" problem
    from the deck solvable.
    """
    normalized = normalize_document_image(raw_bytes)
    return str(imagehash.phash(normalized))


def fingerprint_document(raw_bytes: bytes) -> str:
    """
    Normalize a scanned document and return a salted, one-way fingerprint
    that is stable across blur/rotation/lighting noise.

    Note: this salts the phash with a *fresh random salt every call*
    (see crypto_utils.salted_hash), which keeps the stored artifact
    non-reversible but means two scans of the same document won't
    produce identical fingerprint strings. A production system that
    needs to *match* repeat scans of the same document would instead
    use a fixed, per-document or per-session salt so the same input
    always hashes the same way -- see README "Known limitations".
    """
    phash = perceptual_hash_string(raw_bytes)
    return salted_hash(phash)
