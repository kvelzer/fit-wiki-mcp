"""Published output schemas shared by tools and integration tests."""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class Model(BaseModel):
    model_config = ConfigDict(extra="allow")


class Metadata(Model):
    fetched_at: str
    cache_status: str
    stale: bool
    partial: bool
    warnings: list[str] = Field(default_factory=list)


class Course(Model):
    course_id: str
    code: str
    title: str
    source_url: str


class Listing(Model):
    items: list[dict[str, Any]]
    total: int
    next_cursor: str | None
    metadata: Metadata


class Courses(Listing):
    items: list[Course]
    source_url: str


class Page(Model):
    page_id: str
    title: str
    source_url: str
    markdown: str
    total_chars: int
    sections: list[dict[str, Any]]
    links: list[dict[str, Any]]
    next_cursor: str | None
    metadata: Metadata


class Search(Listing):
    scope: str
    ocr_indexed_pages: int


class Attachment(Model):
    attachment_id: str
    source_url: str
    source_hash: str
    mime_type: str
    size_bytes: int
    local_path: str
    metadata: Metadata


class AttachmentText(Attachment):
    page: int
    page_count: int
    text: str
    method: str
    status: str
    next_cursor: str | None


class MaterialImage(Attachment):
    page: int
    width: int
    height: int
    instructions: str


class Transcription(Model):
    attachment_id: str
    source_hash: str
    source_url: str
    page: int
    text: str
    method: str
    verified: bool
    partial: bool
    warnings: list[str]
