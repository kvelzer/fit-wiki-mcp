"""DokuWiki identities. Only generated, same-origin, read-only URLs reach HTTP."""

import re
import unicodedata
from urllib.parse import parse_qs, quote, unquote, urljoin, urlsplit

from .errors import WikiError

BASE_URL = "https://fit-wiki.cz"


def identity(value: str) -> str:
    value = unicodedata.normalize("NFC", unquote(value)).strip().strip(":/")
    if not value or len(value) > 1000 or re.search(r"[\x00-\x20\\?#%]", value):
        raise WikiError("INVALID_ARGUMENT", "Invalid wiki identifier.")
    parts = re.split(r"[:/]", value)
    if any(not part or part in (".", "..") for part in parts):
        raise WikiError("INVALID_ARGUMENT", "Invalid wiki namespace or path.")
    return ":".join(parts)


def page_id(value: str) -> str:
    if value.startswith(("https://", "http://", "/")):
        link = classify_link(value)
        if not link or link["kind"] != "page":
            raise WikiError("INVALID_ARGUMENT", "Expected a read-only FIT Wiki page.")
        result = link["id"]
    else:
        result = identity(value)
    if result != "škola" and not result.startswith("škola:"):
        raise WikiError("INVALID_ARGUMENT", "Only the study namespace škola is exposed.")
    return result


def media_id(value: str) -> str:
    if value.startswith(("https://", "http://", "/")):
        link = classify_link(value)
        if not link or link["kind"] != "attachment":
            raise WikiError("INVALID_ARGUMENT", "Expected a FIT Wiki attachment.")
        return link["id"]
    return identity(value)


def page_url(value: str, export: bool = False) -> str:
    path = quote(identity(value).replace(":", "/"), safe="/.-_")
    return f"{BASE_URL}/{'_export/xhtml/' if export else ''}{path}"


def media_url(value: str) -> str:
    return f"{BASE_URL}/_media/{quote(identity(value).replace(':', '/'), safe='/.-_')}"


def same_origin(url: str) -> bool:
    try:
        parsed = urlsplit(url)
        return (
            parsed.scheme == "https"
            and parsed.hostname == "fit-wiki.cz"
            and parsed.port in (None, 443)
            and not parsed.username
            and not parsed.password
        )
    except ValueError:
        return False


def namespace_url(value: str) -> str:
    return f"{BASE_URL}/obsah?do=index&idx={quote(page_id(value), safe='')}"


def classify_link(href: str, base: str = BASE_URL + "/") -> dict | None:
    if not href or href.startswith(("#", "mailto:", "javascript:", "data:")):
        return None
    url = urljoin(base, href)
    if not same_origin(url):
        return (
            {"kind": "external", "url": url} if urlsplit(url).scheme in ("http", "https") else None
        )
    parsed = urlsplit(url)
    query = parse_qs(parsed.query, keep_blank_values=True)
    if any(k not in {"id", "media", "do", "rev", "w", "h", "cache", "tok", "s[]"} for k in query):
        return None
    if "do" in query and query["do"] != ["show"]:
        return None
    if "rev" in query:  # This server reads current revisions only.
        return None
    path = unquote(parsed.path)
    kind = "page"
    if path.startswith(("/_media/", "/_detail/")):
        raw = path.split("/", 2)[2]
        kind = "attachment"
    elif path == "/lib/exe/fetch.php":
        raw = query.get("media", [""])[0]
        if raw.startswith(("https://", "http://", "//")):
            external = urljoin(BASE_URL + "/", raw)
            target = urlsplit(external)
            if target.hostname and not target.username and not target.password:
                if parsed.fragment and not target.fragment:
                    external += "#" + parsed.fragment
                return {"kind": "external", "url": external}
            return None
        kind = "attachment"
    elif path in ("/doku.php", "/"):
        raw = query.get("id", ["obsah"])[0]
    elif path.startswith(("/lib/", "/_")):
        return None
    else:
        raw = path
    try:
        ident = identity(raw)
    except WikiError:
        return None
    return {
        "kind": kind,
        "id": ident,
        "url": media_url(ident) if kind == "attachment" else page_url(ident),
        "anchor": unquote(parsed.fragment),
    }
