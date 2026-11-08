import json
from pathlib import Path

import anyio
import pytest
from mcp import Client

from fitwiki_mcp.client import Response
from fitwiki_mcp.errors import WikiError
from fitwiki_mcp.parsers import content_root, parse_namespace, parse_page
from fitwiki_mcp.server import create_server
from fitwiki_mcp.urls import classify_link, media_id, namespace_url, page_url

HTML = (Path(__file__).parent / "fixtures/namespace.html").read_text()
NS = "škola:státnice"


def test_namespace_children_are_typed_bounded_and_deduplicated():
    nodes = parse_namespace(HTML, NS)
    assert len(nodes) == 2
    assert nodes[0]["kind"] == "namespace" and nodes[0]["namespace_id"] == NS + ":bi_szz_2023"
    assert nodes[1]["kind"] == "page" and nodes[1]["page_id"] == NS + ":info"
    assert nodes[0]["source_url"] == namespace_url(NS + ":bi_szz_2023")
    assert parse_namespace("", NS) == []
    with pytest.raises(WikiError, match="PARSE_ERROR"):
        parse_namespace("<html>Unexpected login or error</html>", NS)
    with pytest.raises(WikiError, match="PARSE_ERROR"):
        parse_namespace(HTML, "škola:elsewhere")


def test_namespace_pagination_cache_scope_and_refresh(service, monkeypatch):
    calls = []

    def get_index(namespace):
        calls.append(namespace)
        if service.client.error:
            raise service.client.error
        return Response(HTML.encode(), "text/html", "https://fit-wiki.cz/lib/exe/ajax.php")

    monkeypatch.setattr(service.client, "get_namespace_html", get_index, raising=False)
    first = service.get_namespace_index(NS, limit=1)
    second = service.get_namespace_index(NS, limit=1, cursor=first["next_cursor"])
    assert first["items"][0]["kind"] == "namespace" and second["items"][0]["kind"] == "page"
    assert first["namespace_exists"] is True and calls == [NS]
    with pytest.raises(WikiError, match="INVALID_ARGUMENT"):
        service.get_namespace_index("uživatelé")
    assert calls == [NS]
    service.client.error = WikiError("UPSTREAM_UNAVAILABLE", "network")
    assert service.get_namespace_index(NS, refresh=True)["metadata"]["stale"]
    service.client.error = WikiError("ACCESS_DENIED", "denied")
    with pytest.raises(WikiError, match="ACCESS_DENIED"):
        service.get_namespace_index(NS, refresh=True)


def test_namespace_empty_is_not_a_claim_that_namespace_exists(service, monkeypatch):
    monkeypatch.setattr(
        service.client,
        "get_namespace_html",
        lambda ns: Response(b"", "text/html", "https://fit-wiki.cz/lib/exe/ajax.php"),
        raising=False,
    )
    result = service.get_namespace_index(NS)
    assert result["items"] == [] and result["namespace_exists"] is None


def test_mcp_namespace_tool_and_resource(service, monkeypatch):
    monkeypatch.setattr(
        service.client,
        "get_namespace_html",
        lambda ns: Response(HTML.encode(), "text/html", "https://fit-wiki.cz/lib/exe/ajax.php"),
        raising=False,
    )

    async def scenario():
        async with Client(create_server(service=service)) as client:
            result = await client.call_tool("get_namespace_index", {"namespace": NS})
            assert not result.is_error and result.structured_content["total"] == 2
            resource = await client.read_resource("fitwiki://namespaces/škola%3Astátnice")
            assert json.loads(resource.contents[0].text)["total"] == 2

    anyio.run(scenario)


def test_priority_content_root_does_not_capture_navigation_or_account_controls():
    html = '<body class="dokuwiki"><nav>Private navigation</nav><div class="page"><h1>Real content</h1><p>Study text.</p></div><footer>Account name</footer></body>'
    _, root = content_root(html)
    assert root.get("class") == ["page"]
    page = parse_page(html, page_url("škola:test"), "škola:test")
    assert "Study text." in page["markdown"]
    assert "Private navigation" not in page["markdown"] and "Account name" not in page["markdown"]


@pytest.mark.parametrize(
    "target", ["https://www.overleaf.com/read/example", "https://example.org/file.pdf?version=2"]
)
def test_wrapped_external_media_remains_external_without_wiki_fetch(target):
    from urllib.parse import quote

    href = "https://fit-wiki.cz/lib/exe/fetch.php?tok=public-checksum&media=" + quote(
        target, safe=""
    )
    assert classify_link(href) == {"kind": "external", "url": target}
    with pytest.raises(WikiError, match="INVALID_ARGUMENT"):
        media_id(href)


def test_internal_media_still_normalizes_as_an_attachment():
    item = classify_link("/lib/exe/fetch.php?media=škola:předměty:sample.pdf")
    assert item["kind"] == "attachment" and item["id"] == "škola:předměty:sample.pdf"


def test_wrapped_external_media_in_markdown_keeps_the_destination_and_fragment():
    html = '<div class="dokuwiki"><h1>References</h1><a href="/lib/exe/fetch.php?media=https%3A%2F%2Fexample.org%2Fpaper.pdf#page=3">Paper</a></div>'
    page = parse_page(html, page_url("škola:test"), "škola:test")
    assert "(https://example.org/paper.pdf#page=3)" in page["markdown"]
    assert page["links"][0]["kind"] == "external"
