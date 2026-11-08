from pathlib import Path

import pytest

from fitwiki_mcp.errors import WikiError
from fitwiki_mcp.parsers import parse_courses, parse_page, parse_search, section_markdown
from fitwiki_mcp.urls import classify_link, identity, media_id, page_id, page_url

FIXTURES = Path(__file__).parent / "fixtures"


def test_catalog_preserves_actual_variant_urls():
    courses = parse_courses((FIXTURES / "catalog.html").read_text(), page_url("škola:předměty"))
    assert {c["course_id"] for c in courses} == {
        "škola:předměty:bi-test",
        "škola:předměty:bi-test.21:obsah",
        "škola:předměty:bie-test",
    }
    assert next(c for c in courses if c["code"] == "BI-TEST.21")["source_url"].endswith(
        "bi-test.21/obsah"
    )


@pytest.mark.parametrize(
    "value", ["škola:předměty:bi-test.21:obsah", "škola:předměty:bi-test:2024:test"]
)
def test_unicode_nested_roundtrip(value):
    assert page_id(page_url(value)) == value


@pytest.mark.parametrize(
    "value",
    [
        "../etc/passwd",
        "škola:..:x",
        "škola:%2e%2e:x",
        "škola:%252e%252e:x",
        "škola:a\\b",
        "škola:a?do=logout",
        "škola:a//b",
    ],
)
def test_identifier_rejects_traversal_and_actions(value):
    with pytest.raises(WikiError):
        identity(value)


@pytest.mark.parametrize(
    "url",
    [
        "https://evil.test/file.pdf",
        "https://fit-wiki.cz/obsah?do=logout",
        "https://fit-wiki.cz/obsah?do=edit",
        "https://fit-wiki.cz.evil.test/a",
    ],
)
def test_media_rejects_foreign_urls_and_actions(url):
    with pytest.raises(WikiError):
        media_id(url)


def test_media_detail_and_manager_are_distinct():
    assert classify_link("/_detail/škola/a.png?id=škola:x")["id"] == "škola:a.png"
    assert classify_link("/obsah?do=media") is None


def test_heading_hierarchy_and_markdown_content():
    page = parse_page(
        (FIXTURES / "page.html").read_text(),
        page_url("škola:předměty:bi-test"),
        "škola:předměty:bi-test",
    )
    assert next(s for s in page["sections"] if s["section_id"] == "written")["parent"] == "exam"
    exam = section_markdown(page["markdown"], page["sections"], "exam")
    assert "Written material" in exam and "Other content" not in exam
    assert "Navigation noise" not in page["markdown"] and "Edit section" not in page["markdown"]
    assert 'print("hello")' in page["markdown"] and "| Name | Value |" in page["markdown"]
    assert any(
        link["kind"] == "attachment" and link["section_id"] == "written" for link in page["links"]
    )
    assert not any(link["url"].endswith("do=edit") for link in page["links"])


def test_fulltext_excludes_title_suggestions_and_out_of_scope():
    results = parse_search(
        (FIXTURES / "search.html").read_text(),
        "https://fit-wiki.cz/doku.php",
        "škola:předměty:bi-test",
    )
    assert len(results) == 1
    assert results[0]["title"] == "Exam" and "SQL" in results[0]["snippet"]


def test_unknown_html_fails_explicitly():
    with pytest.raises(WikiError, match="PARSE_ERROR"):
        parse_page('<html><form id="dw__login">Login</form></html>', page_url("škola:x"), "škola:x")


def test_genuine_empty_search_is_not_a_parser_error():
    assert (
        parse_search(
            '<div class="nothing">Nic nenalezeno.</div>', "https://fit-wiki.cz/doku.php", "škola"
        )
        == []
    )


def test_duplicate_heading_titles_select_by_identity_not_name():
    page = parse_page(
        '<div class="dokuwiki"><h1 id="main">Title</h1><h2 id="first">Same</h2><p>first content</p><h2 id="second">Same</h2><p>second content</p></div>',
        "https://fit-wiki.cz/škola/test",
        "škola:test",
    )
    text = section_markdown(page["markdown"], page["sections"], "second")
    assert "second content" in text and "first content" not in text
