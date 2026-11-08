#!/usr/bin/env python3
"""Opt-in live stdio smoke test. Reports metadata, never credentials or study answers."""

import argparse
import json
import os
import sys
import time
from pathlib import Path

import anyio
from mcp import Client
from mcp.client.stdio import StdioServerParameters

ROOT = Path(__file__).resolve().parents[1]


async def run(mode: str) -> dict:
    start = time.monotonic()
    params = StdioServerParameters(
        command=sys.executable, args=[str(ROOT / "mcp_server.py")], cwd=ROOT, env=dict(os.environ)
    )
    report = {"transport": "stdio", "mode": mode}
    async with Client(params, mode=mode, read_timeout_seconds=120) as client:
        report["protocol"] = client.protocol_version
        report["tools"] = len((await client.list_tools()).tools)

        async def call(name, **kwargs):
            result = await client.call_tool(name, kwargs)
            if result.is_error:
                raise RuntimeError(f"{name}: {result.content[0].text}")
            return result

        # Exercise every catalog page, not just the first 30 courses.
        first = (await call("list_courses", limit=50)).structured_content
        courses = list(first["items"])
        cursor = first["next_cursor"]
        while cursor:
            page = (await call("list_courses", limit=50, cursor=cursor)).structured_content
            courses.extend(page["items"])
            cursor = page["next_cursor"]
        report["catalog_total"] = first["total"]
        report["catalog_visited"] = len(courses)
        assert len(courses) == first["total"]
        variant = next(c["course_id"] for c in courses if ".21" in c["code"])
        summaries = []
        for cid in ["BI-DBS", "BI-AG1", variant]:
            index = (await call("get_course_index", course_id=cid)).structured_content
            page = (await call("get_page", page_id=index["course"]["course_id"])).structured_content
            summaries.append(
                {
                    "course_id": index["course"]["course_id"],
                    "sections": len(index["sections"]),
                    "links": index["total"],
                    "markdown_chars": page["total_chars"],
                }
            )
        report["courses"] = summaries
        query = (
            await call("search", query="SQL", course_id="BI-DBS", refresh=True)
        ).structured_content
        report["search"] = {
            "total": query["total"],
            "origins": sorted({i["origin"] for i in query["items"]}),
        }
        negative = (
            await call("search", query="qqqfitwikimcpnoresultqqq", refresh=True)
        ).structured_content
        assert negative["total"] == 0
        aid = "škola:předměty:bi-dbs:zadani-a-zverejneno.pdf"
        material = (await call("download_attachment", attachment_id=aid)).structured_content
        text = (await call("read_attachment", attachment_id=aid, mode="native")).structured_content
        rendered = await call("get_material_image", attachment_id=aid)
        assert any(c.type == "image" for c in rendered.content)
        report["attachment"] = {
            "size_bytes": material["size_bytes"],
            "mime": material["mime_type"],
            "pages": text["page_count"],
            "text_chars": len(text["text"]),
            "image_dimensions": [
                rendered.structured_content["width"],
                rendered.structured_content["height"],
            ],
        }
        t0 = time.monotonic()
        warm = (await call("get_page", page_id="škola:předměty:bi-dbs")).structured_content
        report["warm_read_ms"] = round((time.monotonic() - t0) * 1000, 1)
        assert warm["metadata"]["cache_status"] == "hit"
        report["duration_seconds"] = round(time.monotonic() - start, 1)
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true", required=True)
    parser.add_argument("--mode", choices=["auto", "legacy"], default="auto")
    args = parser.parse_args()
    print(json.dumps(anyio.run(run, args.mode), ensure_ascii=False, indent=2))
