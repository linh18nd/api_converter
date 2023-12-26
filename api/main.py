from io import BytesIO
import logging
import os
import secrets
import subprocess
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from threading import BoundedSemaphore
from typing import Optional, Dict, Set
from uuid import UUID
from fastapi.responses import FileResponse, StreamingResponse
from docx import Document as DocxDocument

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import (
    FastAPI,
    File,
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
from starlette.status import HTTP_403_FORBIDDEN
from api.models import Document, Lang





from api.settings import config
from api.tools import save_upload_file

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
    

api_key_header = APIKeyHeader(name="X-API-KEY")


async def check_api_key(x_api_key: str = Security(api_key_header)):
    if secrets.compare_digest(x_api_key, config.api_key_secret):
        return api_key_header
    else:
        raise HTTPException(
            status_code=HTTP_403_FORBIDDEN, detail="Could not validate credentials"
        )


@app.get("/", include_in_schema=False, status_code=204, response_class=Response)
def root():
    pass


@app.get("/status", include_in_schema=False)
def status():
    ocrmypdf = subprocess.check_output(
        f"{config.base_command_ocr} --version", shell=True
    )
    return {"status": "ok", "version_ocr": ocrmypdf.strip()}


@app.get("/ocr/{pid}", response_model=Document)
def get_doc_detail(pid: UUID, api_key: APIKey = Depends(check_api_key)):
    if pid in documents:
        return documents[pid]
    raise HTTPException(status_code=404)


@app.get("/ocr/{pid}/pdf")
def get_doc_pdf(pid: UUID, api_key: APIKey = Depends(check_api_key)):
    if pid in documents:
        output_doc = documents[pid].output

        if output_doc.resolve().exists():
            return FileResponse(
                str(output_doc.resolve()),
                headers={"Content-Type": "application/pdf"},
                filename=f"{pid}.pdf",
            )

    raise HTTPException(status_code=404)



@app.get("/ocr/{pid}/txt")
def get_doc_txt(pid: UUID, api_key: APIKey = Depends(check_api_key)):
    if pid in documents:
        output_doc_txt = documents[pid].output_txt

        if output_doc_txt.resolve().exists():
            return FileResponse(
                str(output_doc_txt.resolve()),
                headers={"Content-Type": "text/plain; charset=utf-8"},
                filename=f"{pid}.txt",
            )

    raise HTTPException(status_code=404)

@app.get("/ocr/{pid}/docx")
def get_doc_docx(pid: UUID, api_key: APIKey = Depends(check_api_key)):
    if pid in documents:
        output_doc_txt = documents[pid].output_txt

        if output_doc_txt.resolve().exists():
            doc = DocxDocument()
            with open(str(output_doc_txt.resolve()), 'r', encoding='utf-8') as txt_file:
                for line in txt_file:
                    doc.add_paragraph(line.strip())

            docx_content = BytesIO()
            doc.save(docx_content)

            docx_content.seek(0)

            return StreamingResponse(
                content=docx_content,
                media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                headers={"Content-Disposition": f"attachment; filename={pid}.docx"},
            )

    raise HTTPException(status_code=404)

from fastapi import Query

@app.get("/search", response_model=list)
def search_files(query: str = Query(..., title="Search Query"), api_key: APIKey = Depends(check_api_key)):
    matching_pdfs = []

    for doc in documents.values():
        if doc.output_txt.resolve().exists():
            with open(str(doc.output_txt.resolve()), 'r', encoding='utf-8') as txt_file:
                txt_content = txt_file.read()
                if query.lower() in txt_content.lower():
                    matching_pdfs.append({"pid": str(doc.pid), "file_name": f"{doc.file_name}.pdf"})

    return matching_pdfs


@app.get("/documents", response_model=list)
def get_all_documents(api_key: APIKey = Depends(check_api_key)):
    all_docs = []

    for doc in documents.values():
        all_docs.append({"pid": str(doc.pid), "file_name": doc.file_name, "status": doc.status})

    return all_docs



@app.delete("/ocr/{pid}")
def delete_doc(pid: UUID, api_key: APIKey = Depends(check_api_key)):
    if pid in documents:

        del documents[pid]

        return {"status": "success", "message": f"Document {pid} deleted successfully"}

    raise HTTPException(status_code=404, detail="Document not found")


@app.post(
    "/ocr", response_model=Document, status_code=200,
)
async def ocr(
    background_tasks: BackgroundTasks,
    lang: Optional[Set[str]] = Query([Lang.eng]),
    file: UploadFile = File(...),
    api_key: APIKey = Depends(check_api_key),
    file_name: Optional[str] = Query(None),

):
    pid = uuid.uuid4()
    now = datetime.now()
    expire = now + expiration_delta
    filename = f"{file_name or pid}"
    

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
            "file_name": f"{filename}",
        }
    )
    documents[pid].save_state()

    await do_ocr(documents[pid])

    return documents[pid]