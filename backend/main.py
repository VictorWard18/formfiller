"""
FormFiller API — FastAPI backend.
Endpoints:
  POST /api/extract       — upload PDFs, extract data dictionary
  GET  /api/dictionaries   — list all saved dictionaries
  GET  /api/dictionaries/{id} — get one dictionary
  PUT  /api/dictionaries/{id} — update dictionary data (edit fields)
  DELETE /api/dictionaries/{id} — delete dictionary
  POST /api/fill           — upload .docx forms + dictionary_id, get filled forms
  GET  /api/download/{filename} — download a filled form
"""

import os
import io
import zipfile
import logging
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from database import init_db, create_dictionary, get_dictionary, list_dictionaries, update_dictionary, delete_dictionary
from extractor import extract_and_merge
from filler import fill_form

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

UPLOAD_DIR = Path("/data/uploads")
OUTPUT_DIR = Path("/data/outputs")
STATIC_DIR = Path("/app/static")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    init_db()
    logger.info("FormFiller API started")
    yield
    # Shutdown
    logger.info("FormFiller API stopped")


app = FastAPI(title="FormFiller", version="1.0.0", lifespan=lifespan)

# CORS for local dev
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Auth middleware (simple shared password) ---

GATE_PASSWORD = os.environ.get("GATE_PASSWORD", "")


class AuthBody(BaseModel):
    password: str


@app.post("/api/auth")
async def check_auth(body: AuthBody):
    if not GATE_PASSWORD:
        return {"ok": True}
    if body.password == GATE_PASSWORD:
        return {"ok": True}
    raise HTTPException(status_code=401, detail="Wrong password")


# --- Extraction ---

@app.post("/api/extract")
async def extract_pdfs(
    files: list[UploadFile] = File(...),
    language: str = Form("ru"),
    name: str = Form("New Dictionary"),
):
    """Upload PDFs → extract → merge → save dictionary."""
    if not files:
        raise HTTPException(400, "No files uploaded")

    pdf_files = []
    for f in files:
        if not f.filename.lower().endswith(".pdf"):
            raise HTTPException(400, f"File {f.filename} is not a PDF")
        content = await f.read()
        pdf_files.append((f.filename, content))

    try:
        merged = await extract_and_merge(pdf_files, language)
    except Exception as e:
        logger.error(f"Extraction failed: {e}")
        raise HTTPException(500, f"Extraction failed: {str(e)}")

    dict_id = create_dictionary(name, language, merged)
    return {"id": dict_id, "name": name, "data": merged}


# --- Dictionaries CRUD ---

@app.get("/api/dictionaries")
async def api_list_dictionaries():
    return list_dictionaries()


@app.get("/api/dictionaries/{dict_id}")
async def api_get_dictionary(dict_id: int):
    d = get_dictionary(dict_id)
    if d is None:
        raise HTTPException(404, "Dictionary not found")
    return d


class DictUpdateBody(BaseModel):
    data: dict


@app.put("/api/dictionaries/{dict_id}")
async def api_update_dictionary(dict_id: int, body: DictUpdateBody):
    ok = update_dictionary(dict_id, body.data)
    if not ok:
        raise HTTPException(404, "Dictionary not found")
    return {"ok": True}


@app.delete("/api/dictionaries/{dict_id}")
async def api_delete_dictionary(dict_id: int):
    ok = delete_dictionary(dict_id)
    if not ok:
        raise HTTPException(404, "Dictionary not found")
    return {"ok": True}


# --- Form Filling ---

@app.post("/api/fill")
async def fill_forms(
    files: list[UploadFile] = File(...),
    dictionary_id: int = Form(...),
    language: str = Form("ru"),
):
    """Upload .docx forms + dictionary ID → fill → return zip of filled forms."""
    d = get_dictionary(dictionary_id)
    if d is None:
        raise HTTPException(404, "Dictionary not found")

    dictionary_data = d["data"]
    filled_files = []

    for f in files:
        if not f.filename.lower().endswith((".docx", ".doc")):
            raise HTTPException(400, f"File {f.filename} is not a .docx")
        content = await f.read()

        try:
            filled_bytes = await fill_form(content, dictionary_data, language)
        except Exception as e:
            logger.error(f"Fill failed for {f.filename}: {e}")
            raise HTTPException(500, f"Fill failed for {f.filename}: {str(e)}")

        out_name = f"filled_{f.filename}"
        out_path = OUTPUT_DIR / out_name
        with open(out_path, "wb") as out_f:
            out_f.write(filled_bytes)

        filled_files.append((out_name, filled_bytes))

    # If single file, return it directly
    if len(filled_files) == 1:
        name, data = filled_files[0]
        return StreamingResponse(
            io.BytesIO(data),
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            headers={"Content-Disposition": f'attachment; filename="{name}"'},
        )

    # Multiple files: return zip
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, data in filled_files:
            zf.writestr(name, data)
    zip_buffer.seek(0)

    return StreamingResponse(
        zip_buffer,
        media_type="application/zip",
        headers={"Content-Disposition": 'attachment; filename="filled_forms.zip"'},
    )


@app.get("/api/download/{filename}")
async def download_file(filename: str):
    path = OUTPUT_DIR / filename
    if not path.exists():
        raise HTTPException(404, "File not found")
    return FileResponse(path, filename=filename)


# --- Serve frontend static files (production) ---
if STATIC_DIR.exists():
    app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")
