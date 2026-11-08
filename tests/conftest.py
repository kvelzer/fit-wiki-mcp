from pathlib import Path

import pytest

from fitwiki_mcp.client import Response
from fitwiki_mcp.config import Config
from fitwiki_mcp.service import Service

FIXTURES = Path(__file__).parent / "fixtures"


class FakeClient:
    def __init__(self):
        self.calls = []
        self.error = None
        self.media = None

    def get(self, url, *, params=None, attachment=False):
        self.calls.append((url, params, attachment))
        if self.error:
            raise self.error
        if attachment:
            return Response(
                self.media,
                "application/pdf" if self.media.startswith(b"%PDF") else "image/png",
                url,
            )
        name = (
            "search.html"
            if params
            else ("catalog.html" if url.endswith("p%C5%99edm%C4%9Bty") else "page.html")
        )
        return Response((FIXTURES / name).read_bytes(), "text/html", url)

    def close(self):
        pass


@pytest.fixture
def service(tmp_path):
    client = FakeClient()
    instance = Service(
        Config(username="test-account", data_dir=tmp_path / "private", request_interval=0), client
    )
    yield instance
    instance.close()
