import pytest
import requests

from fitwiki_mcp.client import WikiClient, html_state
from fitwiki_mcp.config import Config
from fitwiki_mcp.errors import WikiError

LOGIN = '<form id="dw__login" action="/doku.php"><input type="hidden" name="sectok" value="synthetic-token"><input type="hidden" name="do" value="login"></form>'
LOGGED_IN = '<script>JSINFO={"ACT":"show"}</script><a href="/obsah?do=logout">Logout</a>'


class Response:
    def __init__(self, body="", status=200, headers=None):
        self.body = body.encode()
        self.status_code = status
        self.headers = {"Content-Type": "text/html", **(headers or {})}
        self.is_redirect = status in {301, 302, 303, 307, 308}
        self.url = "https://fit-wiki.cz/obsah"

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def iter_content(self, size):
        for i in range(0, len(self.body), size):
            yield self.body[i : i + size]


class Session:
    def __init__(self, responses):
        self.responses = list(responses)
        self.headers = {}
        self.calls = []

    def request(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        response.url = url
        return response

    def close(self):
        pass


def client(responses):
    session = Session(responses)
    config = Config(username="synthetic-user", password="synthetic-password", request_interval=0)
    return WikiClient(config, session), session


def test_login_hidden_fields_and_single_expiration_renewal():
    c, s = client(
        [
            Response(LOGIN),
            Response(LOGGED_IN),
            Response(LOGIN),
            Response(LOGIN),
            Response(LOGGED_IN),
            Response('<div class="page">content</div>'),
        ]
    )
    assert "content" in c.get("https://fit-wiki.cz/škola/test").text
    posts = [call for call in s.calls if call[0] == "POST"]
    assert len(posts) == 2 and posts[0][2]["data"]["sectok"] == "synthetic-token"
    assert c.authenticated


def test_wrong_password_fails_without_repeated_login():
    c, s = client([Response(LOGIN), Response(LOGIN)])
    with pytest.raises(WikiError, match="AUTH_FAILED"):
        c.get("https://fit-wiki.cz/škola/test")
    assert len(s.calls) == 2


def test_denied_with_valid_session_does_not_relogin():
    c, s = client([Response('<script>JSINFO={"ACT":"denied"}</script>')])
    c.authenticated = True
    with pytest.raises(WikiError, match="ACCESS_DENIED"):
        c.get("https://fit-wiki.cz/škola/test")
    assert len(s.calls) == 1


def test_redirect_cannot_send_auth_to_external_host():
    c, s = client([Response(status=307, headers={"Location": "https://evil.test/collect"})])
    with pytest.raises(WikiError, match="INVALID_URL"):
        c._send("POST", "https://fit-wiki.cz/doku.php", data={"p": "synthetic-password"})
    assert len(s.calls) == 1


def test_redirect_cannot_trigger_non_reading_action():
    c, s = client([Response(status=302, headers={"Location": "/obsah?do=logout"})])
    c.authenticated = True
    with pytest.raises(WikiError, match="INVALID_URL"):
        c.get("https://fit-wiki.cz/škola/test")
    assert len(s.calls) == 1


def test_login_html_is_never_a_download():
    c, s = client([Response(LOGIN), Response(LOGIN), Response(LOGGED_IN), Response(LOGIN)])
    c.authenticated = True
    with pytest.raises(WikiError, match="AUTH_REQUIRED"):
        c.get("https://fit-wiki.cz/_media/škola/test.pdf", attachment=True)


def test_bounded_stream_and_rate_limit():
    c, _ = client([Response("x" * 100)])
    with pytest.raises(WikiError, match="TOO_LARGE"):
        c._send("GET", "https://fit-wiki.cz/škola/test", limit=10)
    c, s = client([Response(status=429, headers={"Retry-After": "3600"})])
    with pytest.raises(WikiError, match="RATE_LIMITED"):
        c._send("GET", "https://fit-wiki.cz/škola/test")
    assert len(s.calls) == 1


def test_network_failure_is_secret_free(monkeypatch):
    monkeypatch.setattr("fitwiki_mcp.client.time.sleep", lambda _: None)
    c, _ = client([requests.ConnectionError("sensitive-internal-details")] * 3)
    with pytest.raises(WikiError) as error:
        c._send("GET", "https://fit-wiki.cz/škola/test")
    assert error.value.code == "UPSTREAM_UNAVAILABLE"
    assert "sensitive" not in str(error.value)


def test_http_200_not_found_and_denied_states():
    assert html_state('<script>JSINFO={"ACT":"notFound"}</script>') == "missing"
    assert html_state('<div class="mode_denied"></div>') == "denied"
