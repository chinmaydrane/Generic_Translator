import os
from pathlib import Path
from typing import Optional
import hashlib
from io import BytesIO
from docx import Document

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, UploadFile, File, Response, Form
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

TRANSLATOR_KEY = os.getenv("TRANSLATOR_KEY", "").strip()
TRANSLATOR_ENDPOINT = os.getenv(
    "TRANSLATOR_ENDPOINT",
    "https://api.cognitive.microsofttranslator.com",
).rstrip("/")
TRANSLATOR_REGION = os.getenv("TRANSLATOR_REGION", "global").strip()
DOCUMENT_TRANSLATOR_ENDPOINT = os.getenv(
    "DOCUMENT_TRANSLATOR_ENDPOINT",
    "",
).strip().rstrip("/")
TRANSLATOR_API_VERSION = "2026-06-06"

app = FastAPI(title="Azure Email Translator")


class TranslateRequest(BaseModel):
    subject: str = ""
    body: str
    targets: list[str] = Field(min_length=1, max_length=20)
    source_language: Optional[str] = None


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "translator_configured": bool(TRANSLATOR_KEY),
    }


@app.post("/api/translate")
async def translate_email(request: TranslateRequest):
    if not TRANSLATOR_KEY:
        raise HTTPException(
            status_code=500,
            detail="Translator key is not configured. Create a .env file from .env.example.",
        )

    subject = request.subject.strip()
    body = request.body

    if not body.strip() and not subject:
        raise HTTPException(status_code=400, detail="Enter an email subject or body.")

    targets = list(dict.fromkeys([x.strip() for x in request.targets if x.strip()]))
    if not targets:
        raise HTTPException(status_code=400, detail="Select at least one target language.")

    inputs = []
    if subject:
        item = {
            "text": subject,
            "targets": [{"language": lang} for lang in targets],
        }
        if request.source_language:
            item["language"] = request.source_language
        inputs.append(item)

    if body:
        item = {
            "text": body,
            "targets": [{"language": lang} for lang in targets],
        }
        if request.source_language:
            item["language"] = request.source_language
        inputs.append(item)

    url = f"{TRANSLATOR_ENDPOINT}/translate?api-version={TRANSLATOR_API_VERSION}"
    headers = {
        "Content-Type": "application/json",
        "Ocp-Apim-Subscription-Key": TRANSLATOR_KEY,
        "Ocp-Apim-Subscription-Region": TRANSLATOR_REGION,
    }

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(url, headers=headers, json={"inputs": inputs})
    except httpx.RequestError as exc:
        raise HTTPException(status_code=502, detail=f"Could not reach Azure Translator: {exc}") from exc

    

    if response.status_code >= 400:
        try:
            azure_error = response.json()
        except Exception:
            azure_error = response.text
        raise HTTPException(
            status_code=502,
            detail=f"Azure Translator returned HTTP {response.status_code}: {azure_error}",
        )

    data = response.json()
    values = data.get("value", [])

    # We send subject first (when present), then body.
    subject_values = values[0] if subject else None
    body_values = values[1] if subject else values[0]

    subject_map = {}
    if subject_values:
        for item in subject_values.get("translations", []):
            subject_map[item["language"]] = item.get("text", "")

    body_map = {}
    if body_values:
        for item in body_values.get("translations", []):
            body_map[item["language"]] = item.get("text", "")

    results = []
    for lang in targets:
        results.append(
            {
                "language": lang,
                "subject": subject_map.get(lang, ""),
                "body": body_map.get(lang, ""),
            }
        )

    return {"results": results}

# =========================
# DOCX TRANSLATION USING AZURE TEXT TRANSLATION API
# =========================

from pathlib import Path

TEXT_API_VERSION = "3.0"
MAX_CHARS_PER_BATCH = 4500


def get_docx_paragraphs(container):
    """Get paragraphs from document body and tables."""
    for paragraph in container.paragraphs:
        yield paragraph

    for table in container.tables:
        for row in table.rows:
            for cell in row.cells:
                yield from get_docx_paragraphs(cell)


def split_text(text, limit=4500):
    """Split long paragraph text into smaller pieces."""
    parts = []

    while len(text) > limit:
        split_at = text.rfind(" ", 0, limit + 1)

        if split_at <= 0:
            split_at = limit

        parts.append(text[:split_at])
        text = text[split_at:]

    if text:
        parts.append(text)

    return parts


async def translate_docx_text(segments, target_language, source_language=None):
    """Translate text using Azure Translator Text API v3.0."""

    url = f"{TRANSLATOR_ENDPOINT}/translate"

    params = {
        "api-version": TEXT_API_VERSION,
        "to": target_language
    }

    if source_language:
        params["from"] = source_language

    headers = {
        "Content-Type": "application/json; charset=UTF-8",
        "Ocp-Apim-Subscription-Key": TRANSLATOR_KEY,
        "Ocp-Apim-Subscription-Region": TRANSLATOR_REGION
    }

    translated_segments = []

    async with httpx.AsyncClient(timeout=60.0) as client:

        batch = []
        batch_chars = 0

        async def send_batch(items):
            response = await client.post(
                url,
                params=params,
                headers=headers,
                json=[{"Text": text} for text in items]
            )

            if response.status_code >= 400:
                try:
                    error_data = response.json()
                except Exception:
                    error_data = response.text

                raise HTTPException(
                    status_code=502,
                    detail=(
                        f"Azure Text Translation returned HTTP "
                        f"{response.status_code}: {error_data}"
                    )
                )

            data = response.json()

            if len(data) != len(items):
                raise HTTPException(
                    status_code=502,
                    detail="Unexpected response from Azure Translator."
                )

            return [
                item["translations"][0]["text"]
                for item in data
            ]

        for segment in segments:

            if batch and (
                batch_chars + len(segment) > MAX_CHARS_PER_BATCH
                or len(batch) >= 100
            ):
                translated_segments.extend(
                    await send_batch(batch)
                )

                batch = []
                batch_chars = 0

            batch.append(segment)
            batch_chars += len(segment)

        if batch:
            translated_segments.extend(
                await send_batch(batch)
            )

    return translated_segments


@app.post("/api/translate-document")
async def translate_document(
    file: UploadFile = File(...),
    target_language: str = Form("en"),
    source_language: Optional[str] = Form(None)
):

    if not TRANSLATOR_KEY:
        raise HTTPException(
            status_code=500,
            detail="Translator key is not configured."
        )

    if not file.filename:
        raise HTTPException(
            status_code=400,
            detail="No file was uploaded."
        )

    if not file.filename.lower().endswith(".docx"):
        raise HTTPException(
            status_code=400,
            detail="Only Word (.docx) files are supported."
        )

    document_bytes = await file.read()

    if not document_bytes:
        raise HTTPException(
            status_code=400,
            detail="The uploaded file is empty."
        )

    if len(document_bytes) > 10 * 1024 * 1024:
        raise HTTPException(
            status_code=413,
            detail="Please upload a DOCX smaller than 10 MB."
        )

    try:
        document = Document(BytesIO(document_bytes))

    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail="The uploaded file is not a valid DOCX document."
        ) from exc

    paragraphs = [
        paragraph
        for paragraph in get_docx_paragraphs(document)
        if paragraph.text.strip()
    ]

    if not paragraphs:
        raise HTTPException(
            status_code=400,
            detail="No translatable text found in the DOCX file."
        )

    # Split paragraphs into API-sized segments.
    segment_mapping = []
    all_segments = []

    for paragraph in paragraphs:

        parts = split_text(paragraph.text)

        segment_mapping.append(
            (paragraph, len(parts))
        )

        all_segments.extend(parts)

    try:
        translated_segments = await translate_docx_text(
            all_segments,
            target_language,
            source_language
        )

    except httpx.RequestError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Could not reach Azure Text Translation: {exc}"
        ) from exc

    # Put translated text back into the original document.
    offset = 0

    for paragraph, part_count in segment_mapping:

        translated_text = "".join(
            translated_segments[offset:offset + part_count]
        )

        offset += part_count

        paragraph.text = translated_text

    # Generate the translated DOCX.
    output = BytesIO()

    document.save(output)

    output.seek(0)

    safe_language = "".join(
        c for c in target_language
        if c.isalnum() or c in "_-"
    )

    original_name = Path(file.filename).stem

    download_name = (
        f"translated_{safe_language}_{original_name}.docx"
    )

    return Response(
        content=output.getvalue(),
        media_type=(
            "application/vnd.openxmlformats-officedocument."
            "wordprocessingml.document"
        ),
        headers={
            "Content-Disposition": (
                f'attachment; filename="{download_name}"'
            )
        }
    )

# Serve the frontend from the same FastAPI app.
app.mount("/", StaticFiles(directory=BASE_DIR / "frontend", html=True), name="frontend")
