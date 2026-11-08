import json
from pathlib import Path

import anyio
import pytest
from mcp import Client

from fitwiki_mcp.client import Response
from fitwiki_mcp.errors import WikiError
from fitwiki_mcp.parsers import parse_comments
from fitwiki_mcp.server import create_server
from fitwiki_mcp.urls import page_url

PAGE = "škola:předměty:bi-test:example"
URL = page_url(PAGE)
HTML = (Path(__file__).parent / "fixtures" / "comments.html").read_text()


def comment_client(service, monkeypatch, html=HTML):
    calls = []

    def get(url, **kwargs):
        calls.append(url)
        if service.client.error:
            raise service.client.error
        return Response(html.encode(), "text/html", url)

    monkeypatch.setattr(service.client, "get", get)
    return calls


def test_hidden_content_media_author_dates_and_reply_tree():
    result = parse_comments(HTML, URL, PAGE)
    first, reply, nested, last = result["items"]
    assert first["author"] == "Test Žluťoučký"
    assert first["published_at"] == "2023-10-17T14:16:48Z"
    assert "Hidden explanation" in first["markdown"] and "**important detail**" in first["markdown"]
    assert all(
        noise not in first["markdown"]
        for noise in [
            "Click to",
            "Post a comment",
            "synthetic-secret",
            "untrusted_script",
            "Reply or delete",
        ]
    )
    assert first["attachments"] == [
        {
            "attachment_id": "škola:předměty:shared.png",
            "source_url": "https://fit-wiki.cz/_media/%C5%A1kola/p%C5%99edm%C4%9Bty/shared.png",
            "title": "Solution",
        }
    ]
    assert reply["parent_id"] == first["comment_id"]
    assert nested["parent_id"] == reply["comment_id"]
    assert last["parent_id"] is None and last["author"] is None and last["published_at"] is None
    assert nested["links"][0]["kind"] == "external"
    assert first["source_url"] == URL + "#comment_first"


def test_disabled_empty_and_broken_discussions_are_distinct():
    plain = '<div class="dokuwiki"><h1>Page</h1></div>'
    assert not parse_comments(plain, URL, PAGE)["discussion_available"]
    empty = parse_comments(plain + '<div id="comment_wrapper"></div>', URL, PAGE)
    assert empty["discussion_available"] and empty["items"] == []
    for html in [
        '<form id="dw__login">login</form>',
        plain + '<div class="hentry"><div class="comment_body">Unexpected layout</div></div>',
        plain + '<div id="comment_wrapper"><div class="hentry">Broken comment</div></div>',
    ]:
        with pytest.raises(WikiError, match="PARSE_ERROR"):
            parse_comments(html, URL, PAGE)


def test_nested_entries_and_duplicate_ids():
    html = HTML.replace(
        '<div class="comment_replies">',
        '<div class="hentry"><div class="comment_head"><a id="comment_container"></a></div><div class="comment_body">Parent</div>',
        1,
    )
    result = parse_comments(html, URL, PAGE)
    assert (
        next(c for c in result["items"] if c["comment_id"] == "comment_reply")["parent_id"]
        == "comment_container"
    )
    with pytest.raises(WikiError, match="PARSE_ERROR"):
        parse_comments(HTML.replace("comment_last", "comment_first"), URL, PAGE)


def test_author_filter_cursor_and_comment_reference(service, monkeypatch):
    calls = comment_client(service, monkeypatch)
    first = service.get_comments(PAGE, author="zlutoucky", limit=1)
    assert first["total"] == 2 and first["page_total"] == 4
    assert first["items"][0]["comment_id"] == "comment_first"
    second = service.get_comments(PAGE, author="zlutoucky", limit=1, cursor=first["next_cursor"])
    assert second["items"][0]["comment_id"] == "comment_nested"
    assert second["next_cursor"] is None and calls == [URL]
    assert (
        service.get_comments(PAGE, comment_id="comment_reply")["items"][0]["parent_id"]
        == "comment_first"
    )
    assert service.get_comments(PAGE, author="nobody")["total"] == 0
    assert service.cache.get("media_refs:škola:předměty:shared.png")["value"]["pages"] == [PAGE]
    with pytest.raises(WikiError, match="NOT_FOUND"):
        service.get_comments(PAGE, comment_id="missing")
    with pytest.raises(WikiError, match="INVALID_CURSOR"):
        service.get_comments(PAGE, cursor=first["next_cursor"])


def test_long_comment_can_be_reconstructed_without_silent_truncation(service, monkeypatch):
    text = "Long synthetic comment. " * 30
    html = f'<div class="dokuwiki">Page</div><div id="comment_wrapper"><div class="hentry"><div class="comment_head"><a id="comment_long"></a></div><div class="comment_body"><p>{text}</p></div></div></div>'
    comment_client(service, monkeypatch, html)
    cursor, chunks = None, []
    while True:
        result = service.get_comments(PAGE, limit=1, max_chars=100, cursor=cursor)
        assert result["total"] == 1
        chunks.extend(item["markdown"] for item in result["items"])
        cursor = result["next_cursor"]
        if not cursor:
            break
    assert "".join(chunks) == text.strip() and len(chunks) > 1


def test_refresh_failure_cannot_mask_denied_comments(service, monkeypatch):
    calls = comment_client(service, monkeypatch)
    service.get_comments(PAGE)
    service.get_comments(PAGE, refresh=True)
    assert len(calls) == 2
    service.client.error = WikiError("UPSTREAM_UNAVAILABLE", "network")
    assert service.get_comments(PAGE, refresh=True)["metadata"]["stale"]
    service.client.error = WikiError("ACCESS_DENIED", "denied")
    with pytest.raises(WikiError, match="ACCESS_DENIED"):
        service.get_comments(PAGE, refresh=True)


def test_comments_tool_and_resource_over_mcp(service, monkeypatch):
    comment_client(service, monkeypatch)

    async def run():
        async with Client(create_server(service=service)) as client:
            tool = next(t for t in (await client.list_tools()).tools if t.name == "get_comments")
            assert tool.output_schema and tool.annotations.read_only_hint
            result = await client.call_tool(
                "get_comments", {"page_id": PAGE, "author": "zlutoucky"}
            )
            assert not result.is_error and result.structured_content["total"] == 2
            resource = await client.read_resource(
                "fitwiki://pages/škola%3Apředměty%3Abi-test%3Aexample/comments"
            )
            assert json.loads(resource.contents[0].text)["total"] == 4
            invalid = await client.call_tool("get_comments", {"page_id": PAGE, "max_chars": 5})
            assert invalid.is_error

    anyio.run(run)
