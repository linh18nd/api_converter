from io import BytesIO
import logging
import os
import secrets
import subprocess
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from threading import BoundedSemaphore
from typing import List, Optional, Dict, Set
from uuid import UUID
from fastapi.responses import FileResponse, StreamingResponse
from docx import Document as DocxDocument

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import (
    FastAPI,
    File,
    Form,
    UploadFile,
    HTTPException,
    BackgroundTasks,
    Depends,
    Security,
    Response,
    Query,
)
from fastapi.openapi.models import APIKey
from fastapi.responses import FileResponse, JSONResponse
from fastapi.security import APIKeyHeader
from sqlalchemy.orm import Session
from starlette.status import HTTP_403_FORBIDDEN
from api.database import Documents, get_db, get_document_by_id, save_document_to_database
from api.models import Document, Lang, set_to_string


from api.settings import config
from api.tools import save_upload_file
import sys
sys.path.append("/Users/linhth1/Documents/python/api_converter")


logger = logging.getLogger("gunicorn.error")


app = FastAPI(
    title="api_converter",
    description="Basic API for OCR PDF to TXT",
    version="0.0.3",
    redoc_url=None,
)
Schedule = AsyncIOScheduler({"apscheduler.timezone": "UTC"})
Schedule.start()

pool_ocr = BoundedSemaphore(value=config.max_ocr_process)

documents: Dict[UUID, Document] = {}
workdir = config.workdir

script_directory = Path(os.path.dirname(os.path.abspath(__file__))).resolve()
expiration_delta = timedelta(hours=config.document_expire_hour)

if not workdir.exists():
    workdir.mkdir()
    

async def do_ocr(_doc: Document):
    pool_ocr.acquire()
    _doc.ocr(config.enable_wsl_compat)
    pool_ocr.release()

    file_content = _doc.output_txt.read_text(encoding="utf-8")

    document_data = {
        "id": str(_doc.pid),
        "lang": set_to_string(_doc.lang),
        "created_at": _doc.created,
        "pdf_path": str(_doc.output),
        "ocr_content": file_content,
        "file_name": _doc.file_name,
    }

    try:
        # save_document_to_database(document_data)
        logger.info(f"Document with ID {document_data['id']} added to the database.")
    except Exception as e:
        logger.error(f"Error adding document to the database. Error: {str(e)}")


api_key_header = APIKeyHeader(name="X-API-KEY")


async def check_api_key(x_api_key: str = Security(api_key_header)):
    if secrets.compare_digest(x_api_key, config.api_key_secret):
        return api_key_header
    else:
        raise HTTPException(
            status_code=HTTP_403_FORBIDDEN, detail="Could not validate credentials"
        )


# @app.get("/", include_in_schema=False, status_code=204, response_class=Response)
# def root():
#     pass


# @app.get("/status", include_in_schema=False)
# def status():
#     ocrmypdf = subprocess.check_output(
#         f"{config.base_command_ocr} --version", shell=True
#     )
#     return {"status": "ok", "version_ocr": ocrmypdf.strip()}

# @app.get("/documents/{document_id}", response_model=Document, response_class=JSONResponse)
# async def get_document(
#     document_id: UUID,
#     db: Session = Depends(get_db),
#     api_key: APIKey = Depends(check_api_key),
# ):
#     document = get_document_by_id(db, document_id)

#     if not document:
#         raise HTTPException(status_code=404, detail="Document not found")

#     return document

# @app.get("/documents", response_model=List[Document], response_class=JSONResponse)
# async def get_all_documents(
#     db: Session = Depends(get_db),
#     api_key: APIKey = Depends(check_api_key),
# ):
#     documents = db.query(Documents).all()
#     return documents



@app.post(
    "/ocr", response_model=Document, status_code=200,
)
async def ocr(
    background_tasks: BackgroundTasks,
    lang: Optional[Set[str]] = Query([Lang.eng]),
    file: UploadFile = File(...),
    file_name: str = Form(...),
    api_key: APIKey = Depends(check_api_key),
):
    pid = uuid.uuid4()
    now = datetime.now()
    expire = now + expiration_delta
    filename = f"{pid}_{int(expire.timestamp())}"

    input_file = workdir / Path(f"i_{filename}.pdf")
    save_upload_file(file, input_file)
    output_file = workdir / Path(f"o_{filename}.pdf")
    output_file_json = workdir / Path(f"o_{filename}.json")
    output_file_txt = workdir / Path(f"o_{filename}.txt")

    documents[pid] = Document.parse_obj(
        {
            "pid": pid,
            "lang": lang,
            "input": input_file,
            "output": output_file,
            "output_json": output_file_json,
            "output_txt": output_file_txt,
            "status": "received",
            "created": now,
            "expire": expire,
            "file_name": file_name,
        }
    )
    documents[pid].save_state()

    await do_ocr(documents[pid])

    return documents[pid]
