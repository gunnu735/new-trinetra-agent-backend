import os
import uuid
import structlog
import pdfplumber
from PyPDF2 import PdfReader
from fastapi import UploadFile, HTTPException
from app.core.config import settings

logger = structlog.get_logger()

class PDFService:
    def __init__(self):
        self.upload_dir = settings.UPLOAD_DIR
        self.max_size = settings.MAX_FILE_SIZE_MB * 1024 * 1024
        os.makedirs(self.upload_dir, exist_ok=True)

    async def validate_and_save(self, file: UploadFile) -> dict:
        if not file.filename.endswith(".pdf"):
            raise HTTPException(status_code=400, detail="Only PDF files are allowed")

        contents = await file.read()

        if len(contents) > self.max_size:
            raise HTTPException(status_code=400, detail=f"File too large. Max size is {settings.MAX_FILE_SIZE_MB}MB")

        if contents[:4] != b'%PDF':
            raise HTTPException(status_code=400, detail="Invalid or corrupted PDF file")

        file_id = str(uuid.uuid4())
        file_path = os.path.join(self.upload_dir, f"{file_id}.pdf")

        with open(file_path, "wb") as f:
            f.write(contents)

        logger.info("pdf_saved", file_id=file_id, size=len(contents))
        return {"file_id": file_id, "file_path": file_path, "file_size": len(contents)}

    def extract_text(self, file_path: str) -> dict:
        try:
            extracted = {"pages": [], "metadata": {}, "tables": []}

            with pdfplumber.open(file_path) as pdf:
                for i, page in enumerate(pdf.pages):
                    text = page.extract_text() or ""
                    tables = page.extract_tables() or []
                    extracted["pages"].append({
                        "page_number": i + 1,
                        "text": text,
                        "tables": tables
                    })
                    extracted["tables"].extend(tables)

            reader = PdfReader(file_path)
            meta = reader.metadata
            if meta:
                extracted["metadata"] = {
                    "title": meta.get("/Title", ""),
                    "author": meta.get("/Author", ""),
                    "subject": meta.get("/Subject", ""),
                    "total_pages": len(reader.pages)
                }

            full_text = "\n".join([p["text"] for p in extracted["pages"]])
            extracted["full_text"] = full_text
            logger.info("pdf_extracted", pages=len(extracted["pages"]))
            return extracted

        except Exception as e:
            logger.error("pdf_extraction_failed", error=str(e))
            raise Exception(f"PDF extraction failed: {str(e)}")

pdf_service = PDFService()
