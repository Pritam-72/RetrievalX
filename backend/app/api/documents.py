import hashlib
import io
import zipfile
from pathlib import Path
from uuid import UUID, uuid4

from fastapi import APIRouter, BackgroundTasks, Depends, File, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db_session
from app.api.errors import ApiError
from app.config import get_settings
from app.db.database import session_factory
from app.models.entities import Document, DocumentStatus, User
from app.schemas import DocumentListResponse, DocumentOut, UploadResponse
from app.services.embedding_service import get_embedding_service
from app.services.ingestion_service import ingest_existing_document

router = APIRouter(prefix="/documents", tags=["documents"])
ALLOWED_TYPES = {".pdf": "pdf", ".docx": "docx", ".txt": "txt", ".md": "md"}


def _content_hash(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _validate_upload(filename: str, content: bytes) -> str:
    suffix = Path(filename).suffix.lower()
    file_type = ALLOWED_TYPES.get(suffix)
    if file_type is None:
        raise ApiError(400, "INVALID_FILE_TYPE", "Unsupported document extension")
    if file_type == "pdf" and not content.startswith(b"%PDF-"):
        raise ApiError(400, "INVALID_FILE_TYPE", "PDF magic bytes are invalid")
    if file_type == "docx":
        try:
            with zipfile.ZipFile(io.BytesIO(content)) as archive:
                names = set(archive.namelist())
        except zipfile.BadZipFile as error:
            raise ApiError(
                400, "INVALID_FILE_TYPE", "DOCX is not a valid ZIP"
            ) from error
        if "[Content_Types].xml" not in names or "word/document.xml" not in names:
            raise ApiError(400, "INVALID_FILE_TYPE", "DOCX structure is invalid")
    if file_type in {"txt", "md"}:
        if b"\x00" in content:
            raise ApiError(400, "INVALID_FILE_TYPE", "Text file contains NUL bytes")
        try:
            content.decode("utf-8")
        except UnicodeDecodeError as error:
            raise ApiError(
                400, "INVALID_FILE_TYPE", "Text file must be UTF-8"
            ) from error
    return file_type


async def _process_document(document_id: UUID, user_id: UUID) -> None:
    settings = get_settings()
    async with session_factory() as session:
        document = (
            await session.execute(
                select(Document).where(
                    Document.id == document_id, Document.user_id == user_id
                )
            )
        ).scalar_one_or_none()
        if document is None:
            return
        try:
            await ingest_existing_document(
                session,
                document=document,
                path=Path(document.storage_path),
                embedder=get_embedding_service(settings.embedding_model),
            )
        except Exception:
            return


@router.post("/upload", response_model=UploadResponse, status_code=202)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> UploadResponse:
    settings = get_settings()
    filename = file.filename or "upload"
    content = await file.read()
    max_bytes = settings.max_upload_mb * 1024 * 1024
    if len(content) > max_bytes:
        raise ApiError(413, "FILE_TOO_LARGE", "Document exceeds the upload limit")
    file_type = _validate_upload(filename, content)
    content_hash = _content_hash(content)
    duplicate = (
        await session.execute(
            select(Document).where(
                Document.user_id == user.id, Document.content_hash == content_hash
            )
        )
    ).scalar_one_or_none()
    if duplicate is not None:
        raise ApiError(409, "DUPLICATE_DOCUMENT", "Document already uploaded")

    upload_dir = Path(settings.upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)
    storage_path = upload_dir / f"{uuid4()}.{file_type}"
    storage_path.write_bytes(content)
    document = Document(
        user_id=user.id,
        filename=filename,
        file_type=file_type,
        file_size=len(content),
        content_hash=content_hash,
        storage_path=str(storage_path),
        status=DocumentStatus.UPLOADED,
    )
    session.add(document)
    await session.commit()
    await session.refresh(document)
    background_tasks.add_task(_process_document, document.id, user.id)
    return UploadResponse(
        document_id=document.id, filename=document.filename, status="processing"
    )


@router.get("", response_model=DocumentListResponse)
async def list_documents(
    limit: int = 50,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> DocumentListResponse:
    if not 1 <= limit <= 100:
        raise ApiError(400, "VALIDATION_ERROR", "limit must be between 1 and 100")
    documents = list(
        (
            await session.execute(
                select(Document)
                .where(Document.user_id == user.id)
                .order_by(Document.created_at.desc())
                .limit(limit)
            )
        ).scalars()
    )
    return DocumentListResponse(
        items=[DocumentOut.model_validate(doc) for doc in documents]
    )


@router.get("/{document_id}", response_model=DocumentOut)
async def get_document(
    document_id: UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> DocumentOut:
    document = (
        await session.execute(
            select(Document).where(
                Document.id == document_id, Document.user_id == user.id
            )
        )
    ).scalar_one_or_none()
    if document is None:
        raise ApiError(404, "NOT_FOUND", "Document not found")
    return DocumentOut.model_validate(document)


@router.get("/{document_id}/file")
async def download_document(
    document_id: UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> FileResponse:
    document = (
        await session.execute(
            select(Document).where(
                Document.id == document_id, Document.user_id == user.id
            )
        )
    ).scalar_one_or_none()
    if document is None or not Path(document.storage_path).is_file():
        raise ApiError(404, "NOT_FOUND", "Document not found")
    return FileResponse(document.storage_path, filename=document.filename)


@router.delete("/{document_id}", status_code=204)
async def delete_document(
    document_id: UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> None:
    document = (
        await session.execute(
            select(Document).where(
                Document.id == document_id, Document.user_id == user.id
            )
        )
    ).scalar_one_or_none()
    if document is None:
        raise ApiError(404, "NOT_FOUND", "Document not found")
    path = Path(document.storage_path)
    await session.delete(document)
    await session.commit()
    path.unlink(missing_ok=True)
