"""Serialized, rate-limited HTTP session and bounded DokuWiki authentication."""

import re
import threading
import time
from dataclasses import dataclass
from urllib.parse import parse_qs, urljoin, urlsplit

import requests
from bs4 import BeautifulSoup

from .config import Config
from .errors import WikiError
from .urls import same_origin


@dataclass
class Response:
    body: bytes
    content_type: str
    url: str

    @property
    def text(self) -> str:
        return self.body.decode("utf-8", errors="replace")


def html_state(text: str) -> str:
    if re.search(r'ACT["\s]*[:=]\s*["\']notFound', text) or "mode_notfound" in text:
        return "missing"
    if re.search(r'ACT["\s]*[:=]\s*["\']denied', text) or "mode_denied" in text:
        return "login" if re.search(r'id=["\']dw__login["\']', text) else "denied"
    if re.search(r'id=["\']dw__login["\']', text):
        return "login"
    return "ok"


class WikiClient:
    def __init__(self, config: Config, session: requests.Session | None = None):
        self.config = config
        self.session = session or requests.Session()
        self.session.headers.update({"User-Agent": "curl/8.5.0 fitwiki-mcp/0.1"})
        self.lock = threading.RLock()
        self.authenticated = False
        self._last_request = 0.0

    def close(self) -> None:
        self.session.close()

    def _send(
        self,
        method: str,
        url: str,
        *,
        data: dict | None = None,
        params: dict | None = None,
        limit: int | None = None,
    ) -> Response:
        limit = limit or self.config.html_limit
        deadline = time.monotonic() + 45
        for attempt in range(3):
            current, verb, payload = url, method, data
            try:
                for redirect in range(6):
                    if not same_origin(current):
                        raise WikiError("INVALID_URL", "Refused redirect outside FIT Wiki.")
                    actions = parse_qs(urlsplit(current).query).get("do", [])
                    if any(action not in {"login", "show", "search"} for action in actions):
                        raise WikiError(
                            "INVALID_URL", "Refused redirect to a non-reading wiki action."
                        )
                    pause = self.config.request_interval - (time.monotonic() - self._last_request)
                    if pause > 0:
                        time.sleep(pause)
                    if time.monotonic() >= deadline:
                        raise WikiError(
                            "UPSTREAM_UNAVAILABLE", "Request time budget exceeded.", retryable=True
                        )
                    self._last_request = time.monotonic()
                    with self.session.request(
                        verb,
                        current,
                        data=payload,
                        params=params if redirect == 0 else None,
                        timeout=(10, 20),
                        stream=True,
                        allow_redirects=False,
                    ) as response:
                        if response.is_redirect:
                            current = urljoin(response.url, response.headers.get("Location", ""))
                            if response.status_code in (301, 302, 303):
                                verb, payload = "GET", None
                            continue
                        if response.status_code == 429:
                            # Do not block an MCP call for an unbounded Retry-After.
                            raise WikiError(
                                "RATE_LIMITED", "FIT Wiki rate limit; retry later.", retryable=True
                            )
                        if response.status_code >= 500:
                            raise requests.ConnectionError("upstream server failure")
                        if response.status_code == 404:
                            raise WikiError("NOT_FOUND", "Wiki page or attachment does not exist.")
                        if response.status_code == 401:
                            raise WikiError("AUTH_REQUIRED", "Wiki session needs authentication.")
                        if response.status_code == 403:
                            raise WikiError("ACCESS_DENIED", "FIT Wiki refused this request.")
                        if response.status_code >= 400:
                            raise WikiError("UPSTREAM_ERROR", "FIT Wiki rejected this request.")
                        length = response.headers.get("Content-Length", "")
                        if length.isdigit() and int(length) > limit:
                            raise WikiError(
                                "TOO_LARGE", "Upstream response exceeds the configured size limit."
                            )
                        chunks, size = [], 0
                        for chunk in response.iter_content(65536):
                            size += len(chunk)
                            if size > limit:
                                raise WikiError(
                                    "TOO_LARGE",
                                    "Upstream response exceeds the configured size limit.",
                                )
                            if time.monotonic() >= deadline:
                                raise WikiError(
                                    "UPSTREAM_UNAVAILABLE",
                                    "Request time budget exceeded.",
                                    retryable=True,
                                )
                            chunks.append(chunk)
                        return Response(
                            b"".join(chunks),
                            response.headers.get("Content-Type", "").split(";")[0],
                            response.url,
                        )
                raise WikiError("UPSTREAM_ERROR", "Too many wiki redirects.")
            except requests.RequestException:
                # Do not include exception strings: these can contain submitted URLs or credentials.
                if method != "GET" or attempt == 2 or time.monotonic() + 2**attempt >= deadline:
                    raise WikiError(
                        "UPSTREAM_UNAVAILABLE", "Cannot reach FIT Wiki.", retryable=True
                    ) from None
                time.sleep(2**attempt)
        raise AssertionError("unreachable")

    def login(self) -> None:
        with self.lock:
            self.authenticated = False
            if not self.config.username or not self.config.password:
                raise WikiError(
                    "AUTH_REQUIRED",
                    "Set FITWIKI_USERNAME/FITWIKI_PASSWORD (or COURSES aliases) in the server environment or .env.",
                )
            response = self._send("GET", self.config.base_url + "/obsah?do=login")
            soup = BeautifulSoup(response.text, "html.parser")
            form = soup.select_one("form#dw__login")
            if form is None:
                raise WikiError("AUTH_FAILED", "Wiki login form could not be found.")
            action = urljoin(response.url, form.get("action", ""))
            fields = {
                el["name"]: el.get("value", "") for el in form.select('input[type="hidden"][name]')
            }
            fields.update({"u": self.config.username, "p": self.config.password})
            result = self._send("POST", action, data=fields)
            if html_state(result.text) != "ok" or not re.search(
                r"do[=\%]+(?:logout|3Dlogout)", result.text, re.I
            ):
                raise WikiError(
                    "AUTH_FAILED",
                    "FIT Wiki login failed; check the configured wiki account and its activation.",
                )
            self.authenticated = True

    def get(self, url: str, *, params: dict | None = None, attachment: bool = False) -> Response:
        with self.lock:
            if not self.authenticated:
                self.login()
            for attempt in range(2):
                try:
                    response = self._send(
                        "GET",
                        url,
                        params=params,
                        limit=self.config.attachment_limit
                        if attachment
                        else self.config.html_limit,
                    )
                except WikiError as exc:
                    if exc.code == "AUTH_REQUIRED" and attempt == 0:
                        self.login()
                        continue
                    raise
                if "html" in response.content_type or response.body.lstrip().lower().startswith(
                    (b"<!doctype html", b"<html")
                ):
                    state = html_state(response.text)
                    if state == "login":
                        self.authenticated = False
                        if attempt == 0:
                            self.login()
                            continue
                        raise WikiError(
                            "AUTH_REQUIRED", "Wiki returned a login page after session renewal."
                        )
                    if state == "denied":
                        raise WikiError(
                            "ACCESS_DENIED", "Your wiki account cannot read this material."
                        )
                    if state == "missing":
                        raise WikiError("NOT_FOUND", "This wiki page does not exist.")
                    if attachment:
                        raise WikiError(
                            "INVALID_MEDIA", "Wiki returned HTML instead of an attachment."
                        )
                return response
            raise WikiError("AUTH_REQUIRED", "Wiki authentication required.")
