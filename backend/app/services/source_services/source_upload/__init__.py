"""
Source Upload Module - Handles different types of source uploads.

Educational Note: Upload logic is separated by type for cleaner code:
- file_upload: File uploads (PDF, DOCX, images, audio, etc.)
- url_upload: URL sources (websites, YouTube links)
- text_upload: Pasted text content
- research_upload: Deep research sources (AI agent researched topics)
"""
from app.services.source_services.source_upload.file_upload import (
    upload_file,
    create_from_existing_file
)
from app.services.source_services.source_upload.url_upload import upload_url
from app.services.source_services.source_upload.text_upload import upload_text
from app.services.source_services.source_upload.research_upload import upload_research
from app.services.source_services.source_upload.database_upload import upload_database

__all__ = [
    "upload_file",
    "create_from_existing_file",
    "upload_url",
    "upload_text",
    "upload_research",
    "upload_database"
]
