import time

import pytest

from fitwiki_mcp.config import Config
from fitwiki_mcp.errors import WikiError


def test_environment_precedence_and_checkout_independence(monkeypatch, tmp_path):
    env = tmp_path / ".env"
    env.write_text("FITWIKI_USERNAME=file\nFITWIKI_PASSWORD=private-file-value\n")
    monkeypatch.setenv("COURSES_USERNAME", "process")
    monkeypatch.delenv("FITWIKI_USERNAME", raising=False)
    config = Config.from_env(env)
    assert config.username == "process"
    assert "private-file-value" not in repr(config)


def test_full_catalog_can_be_paginated_and_filter_has_own_cursor(service):
    first = service.list_courses(limit=1)
    second = service.list_courses(cursor=first["next_cursor"], limit=1)
    assert first["items"][0]["course_id"] != second["items"][0]["course_id"]
    assert len(service.client.calls) == 1
    with pytest.raises(WikiError, match="INVALID_CURSOR"):
        service.list_courses(query="TEST.21", cursor=first["next_cursor"], limit=1)


def test_cursor_rejects_changed_snapshot_and_tampering(service):
    _, cursor = service.paginate([1, 2], "key", None, 1)
    for token, values in [(cursor + "a", [1, 2]), (cursor, [1, 2, 3])]:
        with pytest.raises(WikiError, match="INVALID_CURSOR"):
            service.paginate(values, "key", token, 1)


def test_cache_only_falls_back_for_network_errors(service):
    service.list_courses()
    service.client.error = WikiError("UPSTREAM_UNAVAILABLE", "network")
    stale = service.list_courses(refresh=True)
    assert stale["metadata"]["stale"] and stale["items"]
    service.client.error = WikiError("ACCESS_DENIED", "no access")
    with pytest.raises(WikiError, match="ACCESS_DENIED"):
        service.list_courses(refresh=True)


def test_expired_cache_refreshes(service):
    service.list_courses()
    entry = service.cache.get("courses")
    entry["stored_at"] = time.time() - 90000
    from fitwiki_mcp.cache import atomic_json

    atomic_json(service.cache.path("courses"), entry)
    assert service.list_courses()["metadata"]["cache_status"] == "refreshed"
    assert len(service.client.calls) == 2


def test_nested_section_listing_and_long_page_continuation(service):
    result = service.list_pages("BI-TEST", "exam")
    assert result["total"] == 3  # page, PDF, deduplicated image
    assert all(i["section_id"] in {"exam", "written"} for i in result["items"])
    first = service.get_page("škola:předměty:bi-test", max_chars=100)
    assert first["next_cursor"]
    second = service.get_page("škola:předměty:bi-test", max_chars=100, cursor=first["next_cursor"])
    assert first["markdown"] != second["markdown"]


def test_course_search_includes_index_and_honest_ocr_coverage(service):
    result = service.search("SQL", "BI-TEST")
    assert {r["origin"] for r in result["items"]} == {"course_index", "wiki_fulltext"}
    assert result["metadata"]["partial"] and result["ocr_indexed_pages"] == 0


def test_scope_operator_injection_rejected_before_network(service):
    with pytest.raises(WikiError, match="INVALID_ARGUMENT"):
        service.search("SQL @uživatelé")
    assert not service.client.calls


def test_accounts_are_isolated(tmp_path):
    one = Config(username="one", data_dir=tmp_path)
    two = Config(username="two", data_dir=tmp_path)
    assert one.account_dir != two.account_dir


def test_symlink_cache_entry_is_not_followed(service, tmp_path):
    target = tmp_path / "outside.json"
    target.write_text('{"sensitive":true}')
    service.cache.path("courses").symlink_to(target)
    with pytest.raises(WikiError, match="STORAGE_ERROR"):
        service.list_courses()
    assert target.read_text() == '{"sensitive":true}'
