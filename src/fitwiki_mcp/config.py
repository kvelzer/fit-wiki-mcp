"""Explicit configuration; importing this module never logs or rewrites credentials."""

import hashlib
import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import dotenv_values

from .errors import WikiError


@dataclass(frozen=True)
class Config:
    username: str = field(default="", repr=False)
    password: str = field(default="", repr=False)
    data_dir: Path = field(default_factory=lambda: Path.home() / ".cache" / "fitwiki-mcp")
    request_interval: float = 1.0
    page_ttl: int = 3600
    index_ttl: int = 86400
    search_ttl: int = 300
    html_limit: int = 5 * 1024 * 1024
    attachment_limit: int = 50 * 1024 * 1024
    ocr_languages: str = "ces+eng"
    ocr_timeout: int = 40
    max_pixels: int = 20_000_000
    base_url: str = "https://fit-wiki.cz"

    @property
    def account_key(self) -> str:
        return hashlib.sha256(f"{self.base_url}\0{self.username}".encode()).hexdigest()[:24]

    @property
    def account_dir(self) -> Path:
        return self.data_dir / self.account_key

    @classmethod
    def from_env(cls, env_file: Path | None = None) -> "Config":
        if env_file is None:
            explicit = os.environ.get("FITWIKI_ENV_FILE")
            checkout = Path(__file__).resolve().parents[2] / ".env"
            env_file = (
                Path(explicit)
                if explicit
                else (checkout if checkout.is_file() else Path.cwd() / ".env")
            )
        values = dotenv_values(env_file) if env_file.is_file() else {}

        def get(name: str, default: str = "", alias: str | None = None) -> str:
            for source in (os.environ, values):
                for key in (name, alias):
                    if key and key in source and source[key] is not None:
                        return str(source[key])
            return default

        try:
            result = cls(
                username=get("FITWIKI_USERNAME", alias="COURSES_USERNAME"),
                password=get("FITWIKI_PASSWORD", alias="COURSES_PASSWORD"),
                data_dir=Path(get("FITWIKI_DATA_DIR", str(Path.home() / ".cache" / "fitwiki-mcp")))
                .expanduser()
                .resolve(),
                request_interval=float(get("FITWIKI_REQUEST_INTERVAL", "1")),
                page_ttl=int(get("FITWIKI_PAGE_TTL", "3600")),
                index_ttl=int(get("FITWIKI_INDEX_TTL", "86400")),
                search_ttl=int(get("FITWIKI_SEARCH_TTL", "300")),
                ocr_languages=get("FITWIKI_OCR_LANGUAGES", "ces+eng"),
            )
            if (
                result.request_interval < 0
                or min(result.page_ttl, result.index_ttl, result.search_ttl) < 0
            ):
                raise ValueError
            if not result.ocr_languages or any(
                c not in "abcdefghijklmnopqrstuvwxyz_+" for c in result.ocr_languages
            ):
                raise ValueError
            return result
        except (ValueError, OSError) as exc:
            raise WikiError(
                "CONFIG_ERROR",
                "Invalid FITWIKI configuration (interval, TTL, path or OCR language).",
            ) from exc
