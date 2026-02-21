import io
import re
from pathlib import Path
from typing import Any, Dict, List

import numpy as np
import pdfplumber
import pytesseract
from PIL import Image

try:
    import spacy
except Exception:  # pragma: no cover
    spacy = None


MED_REGEX = re.compile(
    r"(?P<name>[A-Za-z][A-Za-z0-9]+)\s+(?P<dose>\d+\s?(mg|ml|mcg))\s+(?P<freq>(once|twice|thrice|daily|bd|tid|qhs)[^\n,.;]*)",
    flags=re.IGNORECASE,
)
MED_FALLBACK_REGEX = re.compile(
    r"(?P<name>[A-Za-z][A-Za-z0-9\-]{2,})\s+(?P<dose>\d+\s?(mg|ml|mcg|g|units?))",
    flags=re.IGNORECASE,
)
FOLLOW_UP_REGEX = re.compile(
    r"(follow[-\s]?up|review)\s*(on|in)?\s*(\d+\s*(days?|weeks?|months?)|\d{1,2}[-/]\d{1,2}[-/]\d{2,4})",
    flags=re.IGNORECASE,
)


def extract_text(file_name: str, file_bytes: bytes) -> str:
    suffix = Path(file_name).suffix.lower()
    if suffix == ".pdf":
        return _extract_text_pdf(file_bytes)
    if suffix in {".png", ".jpg", ".jpeg", ".webp"}:
        return _extract_text_image(file_bytes)
    try:
        return file_bytes.decode("utf-8", errors="ignore")
    except Exception:
        return ""


def _extract_text_pdf(file_bytes: bytes) -> str:
    chunks: List[str] = []
    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text() or ""
            chunks.append(page_text)
    return "\n".join(chunks).strip()


def _extract_text_image(file_bytes: bytes) -> str:
    image = Image.open(io.BytesIO(file_bytes)).convert("RGB")

    # Prefer system Tesseract when available (best accuracy for many cases).
    try:
        _ = pytesseract.get_tesseract_version()
        return pytesseract.image_to_string(image)
    except Exception:
        pass

    # Streamlit Cloud often doesn't include the Tesseract binary.
    # Fall back to a pure-pip OCR engine if installed.
    try:
        from rapidocr_onnxruntime import RapidOCR  # type: ignore

        ocr = RapidOCR()
        img = np.asarray(image)
        result, _ = ocr(img)
        if not result:
            return ""
        # result items: [ [box], ("text", score) ] in common RapidOCR outputs
        texts: List[str] = []
        for item in result:
            try:
                texts.append(str(item[1][0]).strip())
            except Exception:
                continue
        return "\n".join([t for t in texts if t]).strip()
    except Exception:
        return ""


def extract_entities(text: str) -> Dict[str, Any]:
    medicines = []
    for m in MED_REGEX.finditer(text):
        medicines.append(
            {
                "name": m.group("name"),
                "dose": m.group("dose"),
                "frequency": m.group("freq"),
            }
        )
    if not medicines:
        medicines = _extract_medicine_fallback(text)

    follow_up = []
    for m in FOLLOW_UP_REGEX.finditer(text):
        follow_up.append(m.group(0))

    diagnoses, tests = _extract_with_spacy_or_rules(text)
    return {
        "medicines": medicines[:8],
        "diagnoses": diagnoses[:6],
        "tests": tests[:8],
        "follow_up": follow_up[:4],
    }


def _extract_with_spacy_or_rules(text: str) -> tuple[list[str], list[str]]:
    if spacy is not None:
        try:
            nlp = spacy.blank("en")
            doc = nlp(text)
            candidates = [t.text for t in doc if t.is_alpha and len(t.text) > 4]
            diagnoses = [c for c in candidates if c.lower() in {"diabetes", "hypertension", "asthma"}]
            tests = [c for c in candidates if c.lower() in {"cbc", "hba1c", "xray", "ecg"}]
            return list(dict.fromkeys(diagnoses)), list(dict.fromkeys(tests))
        except Exception:
            pass

    text_lower = text.lower()
    diagnosis_terms = ["diabetes", "hypertension", "asthma", "anemia", "infection", "heart failure"]
    test_terms = ["cbc", "hba1c", "xray", "ecg", "creatinine", "lipid profile"]
    diagnoses = [term for term in diagnosis_terms if term in text_lower]
    tests = [term for term in test_terms if term in text_lower]
    return diagnoses, tests


def _extract_medicine_fallback(text: str) -> List[Dict[str, str]]:
    meds: List[Dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for m in MED_FALLBACK_REGEX.finditer(text):
        name = m.group("name").strip().title()
        dose = m.group("dose").strip().lower().replace("  ", " ")
        key = (name.lower(), dose)
        if key in seen:
            continue
        seen.add(key)
        meds.append({"name": name, "dose": dose, "frequency": "as prescribed"})
    return meds
