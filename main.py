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
DOCUMENT_API_VERSION = "2024-05-01"
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
# DOCX TRANSLATION USING AZURE DOCUMENT TRANSLATION API
# =========================

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

    if not DOCUMENT_TRANSLATOR_ENDPOINT:
        raise HTTPException(
            status_code=500,
            detail="Document Translation endpoint is not configured."
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

    url = (
        f"{DOCUMENT_TRANSLATOR_ENDPOINT.rstrip('/')}"
        f"/translator/document:translate"
    )

    params = {
        "api-version": DOCUMENT_API_VERSION,
        "targetLanguage": target_language
    }

    if source_language:
        params["sourceLanguage"] = source_language

    headers = {
        "Ocp-Apim-Subscription-Key": TRANSLATOR_KEY
    }

    files = {
        "document": (
            file.filename,
            document_bytes,
            "application/vnd.openxmlformats-officedocument."
            "wordprocessingml.document"
        )
    }

    try:
        async with httpx.AsyncClient(timeout=180.0) as client:
            response = await client.post(
                url,
                params=params,
                headers=headers,
                files=files
            )

        if response.status_code != 200:
            try:
                error_data = response.json()
            except Exception:
                error_data = response.text

            raise HTTPException(
                status_code=502,
                detail=(
                    f"Azure Document Translation returned "
                    f"HTTP {response.status_code}: {error_data}"
                )
            )

        safe_language = "".join(
            c for c in target_language
            if c.isalnum() or c in "_-"
        )

        original_name = Path(file.filename).stem

        download_name = (
            f"translated_{safe_language}_{original_name}.docx"
        )

        return Response(
            content=response.content,
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

    except httpx.RequestError as exc:
        raise HTTPException(
            status_code=502,
            detail=(
                f"Could not connect to Azure Document Translation: {exc}"
            )
        ) from exc


# Serve the frontend from the same FastAPI app.
app.mount("/", StaticFiles(directory=BASE_DIR / "frontend", html=True), name="frontend")
