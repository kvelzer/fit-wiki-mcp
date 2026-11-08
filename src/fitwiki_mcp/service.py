"""Shared use cases for MCP tools/resources; no protocol code or credentials in outputs."""

import base64
import hashlib
import hmac
import json
import re
import secrets
import threading
import time
import unicodedata
from collections.abc import Callable
from datetime import UTC, datetime

from .cache import Cache, private_dir
from .client import WikiClient
from .config import Config
from .errors import WikiError
from .parsers import parse_courses, parse_page, parse_search, section_markdown
from .urls import page_id, page_url


def folded(text: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFKD", text.casefold()) if not unicodedata.combining(c)
    )


def fingerprint(value) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True).encode()
    ).hexdigest()


class Service:
    def __init__(self, config: Config, client: WikiClient | None = None):
        self.config = config
        private_dir(config.data_dir)
        private_dir(config.account_dir)
        self.client = client or WikiClient(config)
        self.cache = Cache(config.account_dir / "cache")
        self.lock = threading.RLock()
        self.cursor_secret = secrets.token_bytes(32)
        # Imported here to keep PDF and OCR dependencies out of navigation-only imports.
        from .attachments import Attachments

        self.attachments = Attachments(self)

    def close(self) -> None:
        self.client.close()

    def cached(
        self, key: str, ttl: int, loader: Callable[[], dict], refresh: bool = False
    ) -> tuple[dict, dict]:
        with self.lock:
            old = self.cache.get(key)
            hit = old and not refresh and time.time() - old["stored_at"] < ttl
            stale, warning = False, []
            if hit:
                entry, status = old, "hit"
            else:
                try:
                    entry = self.cache.put(key, loader())
                    status = "refreshed" if old else "miss"
                except WikiError as exc:
                    if not old or exc.code not in {"UPSTREAM_UNAVAILABLE", "RATE_LIMITED"}:
                        raise
                    entry, status, stale = old, "stale", True
                    warning = [
                        f"Serving an older copy because {exc.code}; use refresh when the wiki is available."
                    ]
            meta = {
                "fetched_at": datetime.fromtimestamp(entry["stored_at"], UTC).isoformat(),
                "cache_status": status,
                "stale": stale,
                "partial": False,
                "warnings": warning,
            }
            return entry["value"], meta

    def paginate(
        self, values, key: str, cursor: str | None, limit: int
    ) -> tuple[object, str | None]:
        if not 1 <= limit <= 50:
            raise WikiError("INVALID_ARGUMENT", "limit must be between 1 and 50.")
        snapshot = fingerprint(values)
        offset = 0
        if cursor:
            try:
                encoded, signature = cursor.split(".")
                if not hmac.compare_digest(
                    hmac.new(self.cursor_secret, encoded.encode(), "sha256").hexdigest(), signature
                ):
                    raise ValueError
                payload = json.loads(base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4)))
                if payload["key"] != fingerprint(key) or payload["snapshot"] != snapshot:
                    raise ValueError
                offset = payload["offset"]
                if type(offset) is not int or offset < 0 or offset > len(values):
                    raise ValueError
            except (ValueError, KeyError, TypeError, UnicodeError):
                raise WikiError(
                    "INVALID_CURSOR",
                    "Cursor is invalid, expired after server restart, or its source changed. Start again without cursor.",
                ) from None
        output = values[offset : offset + limit]
        next_cursor = None
        if offset + limit < len(values):
            payload = {"key": fingerprint(key), "snapshot": snapshot, "offset": offset + limit}
            encoded = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
            next_cursor = (
                encoded + "." + hmac.new(self.cursor_secret, encoded.encode(), "sha256").hexdigest()
            )
        return output, next_cursor

    def catalog(self, refresh: bool = False) -> tuple[list[dict], dict]:
        url = page_url("škola:předměty")
        value, meta = self.cached(
            "courses",
            self.config.index_ttl,
            lambda: {"items": parse_courses(self.client.get(url).text, url)},
            refresh,
        )
        return value["items"], meta

    def list_courses(
        self, query: str = "", cursor: str | None = None, limit: int = 30, refresh: bool = False
    ) -> dict:
        if len(query) > 200:
            raise WikiError("INVALID_ARGUMENT", "Catalog query is too long.")
        courses, meta = self.catalog(refresh)
        if query:
            courses = [c for c in courses if folded(query) in folded(c["code"] + " " + c["title"])]
        items, next_cursor = self.paginate(courses, "courses:" + query, cursor, limit)
        return {
            "items": items,
            "total": len(courses),
            "next_cursor": next_cursor,
            "source_url": page_url("škola:předměty"),
            "metadata": meta,
        }

    def resolve_course(self, value: str) -> dict:
        courses, _ = self.catalog()
        matches = [
            c
            for c in courses
            if c["code"].casefold() == value.casefold() or c["course_id"] == value
        ]
        if not matches and value.startswith(("https://", "/")):
            ident = page_id(value)
            matches = [c for c in courses if c["course_id"] == ident]
        if len(matches) > 1:
            raise WikiError(
                "AMBIGUOUS_COURSE",
                "Multiple course variants match. Use an exact course_id returned by list_courses.",
            )
        if not matches:
            raise WikiError(
                "NOT_FOUND",
                "Course not found in the wiki catalog; use list_courses to discover its exact identifier.",
            )
        return matches[0]

    def full_page(
        self, ident: str, refresh: bool = False, ttl: int | None = None
    ) -> tuple[dict, dict]:
        ident = page_id(ident)
        source = page_url(ident)
        value, meta = self.cached(
            "page:" + ident,
            self.config.page_ttl if ttl is None else ttl,
            lambda: parse_page(self.client.get(page_url(ident, True)).text, source, ident),
            refresh,
        )
        # Media namespaces are independent of the courses that link to them.
        with self.lock:
            for link in value["links"]:
                if link["kind"] != "attachment":
                    continue
                key = "media_refs:" + link["id"]
                previous = self.cache.get(key)
                pages = previous["value"]["pages"] if previous else []
                if ident not in pages:
                    self.cache.put(key, {"pages": sorted(set(pages + [ident]))})
        return value, meta

    def get_page(
        self,
        ident: str,
        section: str | None = None,
        cursor: str | None = None,
        max_chars: int = 20000,
        refresh: bool = False,
    ) -> dict:
        if not 100 <= max_chars <= 30000:
            raise WikiError("INVALID_ARGUMENT", "max_chars must be between 100 and 30000.")
        page, meta = self.full_page(ident, refresh)
        text = (
            section_markdown(page["markdown"], page["sections"], section)
            if section
            else page["markdown"]
        )
        # The cursor paginator uses bounded chunks as its sequence; changed max_chars invalidates the key.
        chunks = [text[i : i + max_chars] for i in range(0, len(text), max_chars)]
        selected, next_cursor = self.paginate(
            chunks, f"page:{page['page_id']}:{section}:{max_chars}", cursor, 1
        )
        result = {k: v for k, v in page.items() if k != "markdown"}
        result.update(
            {
                "markdown": selected[0] if selected else "",
                "total_chars": len(text),
                "next_cursor": next_cursor,
                "metadata": meta,
            }
        )
        meta["warnings"] += page["warnings"]
        # A long page's link list can itself overwhelm the context; return a bounded preview.
        result["links"] = page["links"][:100]
        result["links_total"] = len(page["links"])
        if len(page["links"]) > 100:
            meta["warnings"].append(
                "Link preview limited to 100; use list_pages for the complete navigation."
            )
        return result

    def get_course_index(
        self, course_id: str, cursor: str | None = None, limit: int = 30, refresh: bool = False
    ) -> dict:
        course = self.resolve_course(course_id)
        page, meta = self.full_page(course["course_id"], refresh, self.config.index_ttl)
        items, next_cursor = self.paginate(
            page["links"], "index:" + course["course_id"], cursor, limit
        )
        return {
            "course": course,
            "sections": page["sections"],
            "items": items,
            "total": len(page["links"]),
            "next_cursor": next_cursor,
            "metadata": meta,
        }

    def list_pages(
        self,
        course_id: str,
        section_id: str | None = None,
        cursor: str | None = None,
        limit: int = 30,
        refresh: bool = False,
    ) -> dict:
        course = self.resolve_course(course_id)
        page, meta = self.full_page(course["course_id"], refresh, self.config.index_ttl)
        allowed = None
        if section_id:
            if not any(s["section_id"] == section_id for s in page["sections"]):
                raise WikiError("NOT_FOUND", "Course section not found.")
            allowed = {section_id}
            for section in page["sections"]:
                if section["parent"] in allowed:
                    allowed.add(section["section_id"])
        values = [
            link for link in page["links"] if allowed is None or link["section_id"] in allowed
        ]
        items, next_cursor = self.paginate(
            values, f"pages:{course['course_id']}:{section_id}", cursor, limit
        )
        return {
            "course_id": course["course_id"],
            "items": items,
            "total": len(values),
            "next_cursor": next_cursor,
            "metadata": meta,
        }

    def search(
        self,
        query: str,
        course_id: str | None = None,
        cursor: str | None = None,
        limit: int = 20,
        refresh: bool = False,
    ) -> dict:
        query = query.strip()
        # Keep namespace operators server-owned; support plain terms and quoted phrases only.
        if (
            not query
            or len(query) > 200
            or re.search(r"[@^:*|()<>\x00-\x1f]", query)
            or re.search(r"\bns\s*:", query, re.I)
        ):
            raise WikiError(
                "INVALID_ARGUMENT",
                "Use plain search terms or quoted phrases, without namespace/query operators.",
            )
        course = self.resolve_course(course_id) if course_id else None
        scope = course["course_id"].removesuffix(":obsah") if course else "škola"
        upstream_url = self.config.base_url + "/doku.php"
        query_key = f"search:{scope}:{query}"
        result, meta = self.cached(
            query_key,
            self.config.search_ttl,
            lambda: {
                "items": parse_search(
                    self.client.get(
                        upstream_url, params={"do": "search", "q": f"{query} @{scope}"}
                    ).text,
                    upstream_url,
                    scope,
                )
            },
            refresh,
        )
        values = list(result["items"])
        if course:
            # DokuWiki namespace filters exclude the namespace's own root page.
            page, page_meta = self.full_page(course["course_id"], refresh)
            terms = [folded(term.strip('"')) for term in query.split() if term.strip('"')]
            haystack = folded(page["markdown"])
            if (
                terms
                and all(term in haystack for term in terms)
                and not any(v["page_id"] == page["page_id"] for v in values)
            ):
                index = haystack.find(terms[0])
                values.insert(
                    0,
                    {
                        "page_id": page["page_id"],
                        "title": page["title"],
                        "source_url": page["source_url"],
                        "snippet": page["markdown"][max(0, index - 100) : index + 400],
                        "origin": "course_index",
                    },
                )
            meta["stale"] |= page_meta["stale"]
            meta["warnings"] += page_meta["warnings"]
        ocr, count = self.attachments.search_transcriptions(query, scope)
        values.extend(ocr)
        items, next_cursor = self.paginate(values, query_key, cursor, limit)
        meta["partial"] = True
        meta["warnings"] += [
            "Wiki results depend on the upstream fulltext index. OCR search covers only materials already processed; unopened scans are not searched."
        ]
        return {
            "items": items,
            "total": len(values),
            "next_cursor": next_cursor,
            "scope": scope,
            "ocr_indexed_pages": count,
            "source_url": upstream_url,
            "metadata": meta,
        }
