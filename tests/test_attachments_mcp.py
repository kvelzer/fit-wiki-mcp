import io
import json
import shutil
import sys
from pathlib import Path

import anyio
import pytest
from mcp import Client
from mcp.client.stdio import StdioServerParameters
from PIL import Image, ImageDraw, ImageFont

from fitwiki_mcp.errors import WikiError
from fitwiki_mcp.server import create_server


def pdf_bytes(text="Synthetic SQL algebra 123"):
    stream = f"BT /F1 20 Tf 50 740 Td ({text}) Tj ET".encode()
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        f"<< /Length {len(stream)} >>\nstream\n".encode() + stream + b"\nendstream",
    ]
    output = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for i, obj in enumerate(objects, 1):
        offsets.append(len(output))
        output.extend(f"{i} 0 obj\n".encode() + obj + b"\nendobj\n")
    xref = len(output)
    output.extend(f"xref\n0 {len(offsets)}\n0000000000 65535 f \n".encode())
    for offset in offsets[1:]:
        output.extend(f"{offset:010} 00000 n \n".encode())
    output.extend(
        f"trailer\n<< /Size {len(offsets)} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF".encode()
    )
    return bytes(output)


def image_bytes():
    image = Image.new("RGB", (1200, 400), "white")
    font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 50)
    ImageDraw.Draw(image).text((40, 130), "Synthetic SQL algebra 123", font=font, fill="black")
    out = io.BytesIO()
    image.save(out, "PNG")
    return out.getvalue()


@pytest.mark.skipif(
    not shutil.which("pdftotext"), reason="Poppler is an optional system dependency"
)
def test_pdf_native_text_image_and_transcription_versioning(service):
    service.client.media = pdf_bytes()
    aid = "škola:předměty:bi-test:sample.pdf"
    material = service.attachments.download(aid)
    read = service.attachments.read(aid, mode="native")
    assert "Synthetic SQL algebra" in read["text"] and read["page_count"] == 1
    meta, data, mime = service.attachments.material_image(aid)
    assert mime == "image/jpeg" and data.startswith(b"\xff\xd8") and meta["height"] <= 2000
    saved = service.attachments.save_transcription(
        aid, 1, "Synthetic equation $x^2+1=2$.", material["source_hash"]
    )
    assert not saved["verified"]
    assert service.attachments.read(aid)["method"] == "client_transcription"
    assert service.search("equation", "BI-TEST")["ocr_indexed_pages"] == 1
    with pytest.raises(WikiError, match="SOURCE_CHANGED"):
        service.attachments.save_transcription(aid, 1, "old result", "0" * 64)
    service.client.media = pdf_bytes("Replaced material")
    service.attachments.download(aid, refresh=True)
    assert service.attachments.search_transcriptions("equation", "škola")[1] == 0


@pytest.mark.skipif(not shutil.which("tesseract"), reason="Tesseract is optional")
def test_real_local_printed_ocr_and_invalid_crop(service):
    service.client.media = image_bytes()
    aid = "škola:předměty:bi-test:scan.png"
    result = service.attachments.read(aid)
    assert result["method"] == "local_ocr"
    assert "algebra 123" in result["text"]
    assert any("handwriting" in warning for warning in result["warnings"])
    with pytest.raises(WikiError, match="INVALID_ARGUMENT"):
        service.attachments.material_image(aid, region=[1, 0, 0, 1])


def test_download_private_atomic_and_refuses_symlinks(service, tmp_path):
    service.client.media = b"not-an-executable-fixture"
    aid = "škola:předměty:bi-test:archive.zip"
    result = service.attachments.download(aid)
    path = Path(result["local_path"])
    assert path.stat().st_mode & 0o777 == 0o600
    assert path.parent.stat().st_mode & 0o777 == 0o700
    assert not list(path.parent.glob(".download-*"))
    path.unlink()
    path.symlink_to(tmp_path / "outside")
    with pytest.raises(WikiError, match="STORAGE_ERROR"):
        service.attachments.download(aid)


def test_mcp_tools_schema_errors_resources_and_real_image_blocks(service):
    service.client.media = image_bytes()

    async def scenario():
        async with Client(create_server(service=service)) as client:
            tools = (await client.list_tools()).tools
            assert len(tools) == 11
            assert all(t.output_schema for t in tools)
            result = await client.call_tool("list_courses", {"limit": 1})
            assert not result.is_error and result.structured_content["total"] == 3
            assert result.structured_content["next_cursor"]
            invalid = await client.call_tool("get_page", {"page_id": "https://evil.test/secret"})
            assert invalid.is_error and "INVALID_ARGUMENT" in invalid.content[0].text
            invalid_limit = await client.call_tool("list_courses", {"limit": 200})
            assert invalid_limit.is_error
            resource = await client.read_resource("fitwiki://courses")
            assert json.loads(resource.contents[0].text)["total"] == 3
            page = await client.read_resource("fitwiki://pages/škola%3Apředměty%3Abi-test")
            assert "SQL" in json.loads(page.contents[0].text)["markdown"]
            image = await client.call_tool(
                "get_material_image", {"attachment_id": "škola:předměty:bi-test:scan.png"}
            )
            assert not image.is_error
            assert any(
                block.type == "image" and block.mime_type == "image/jpeg" for block in image.content
            )
            digest = image.structured_content["source_hash"]
            saved = await client.call_tool(
                "save_transcription",
                {
                    "attachment_id": "škola:předměty:bi-test:scan.png",
                    "page": 1,
                    "text": "Synthetic client vision transcription",
                    "source_hash": digest,
                },
            )
            assert not saved.is_error and not saved.structured_content["verified"]

    anyio.run(scenario)


@pytest.mark.parametrize("mode", ["auto", "legacy"])
def test_real_stdio_discovery_and_secret_free_auth_error(tmp_path, mode):
    env_file = tmp_path / "empty.env"
    env_file.touch()

    async def scenario():
        params = StdioServerParameters(
            command=sys.executable,
            args=["-m", "fitwiki_mcp.server"],
            cwd=tmp_path,
            env={
                "FITWIKI_ENV_FILE": str(env_file),
                "FITWIKI_USERNAME": "",
                "FITWIKI_PASSWORD": "",
                "COURSES_USERNAME": "",
                "COURSES_PASSWORD": "",
                "FITWIKI_DATA_DIR": str(tmp_path / "data"),
            },
        )
        async with Client(params, mode=mode, read_timeout_seconds=15) as client:
            tools = (await client.list_tools()).tools
            assert len(tools) == 11
            result = await client.call_tool("list_courses")
            assert result.is_error
            assert json.loads(result.content[0].text)["error"]["code"] == "AUTH_REQUIRED"

    anyio.run(scenario)


@pytest.mark.skipif(not shutil.which("pdfinfo"), reason="Poppler required")
def test_crop_does_not_replace_full_transcription_and_shared_media_are_searchable(service):
    service.client.media = pdf_bytes()
    aid = "škola:předměty:common-exam.pdf"
    material = service.attachments.download(aid)
    service.cache.put("media_refs:" + aid, {"pages": ["škola:předměty:bi-test"]})
    service.attachments.save_transcription(
        aid, 1, "Complete original transcription", material["source_hash"]
    )
    service.attachments.save_transcription(
        aid, 1, "Partial cropped handwriting", material["source_hash"], partial=True
    )
    assert service.attachments.read(aid)["text"] == "Complete original transcription"
    records, _ = service.attachments.search_transcriptions("cropped", "škola:předměty:bi-test")
    assert records and records[0]["partial"]
    assert records[0]["source_pages"] == [
        "https://fit-wiki.cz/%C5%A1kola/p%C5%99edm%C4%9Bty/bi-test"
    ]


def test_private_storage_rejects_existing_public_directory_without_chmod(tmp_path):
    from fitwiki_mcp.cache import private_dir

    public = tmp_path / "public"
    public.mkdir(mode=0o755)
    with pytest.raises(WikiError, match="STORAGE_ERROR"):
        private_dir(public)
    assert public.stat().st_mode & 0o777 == 0o755


@pytest.mark.skipif(not shutil.which("pdftotext"), reason="Poppler required")
def test_explicit_native_read_does_not_masquerade_as_vision_cache(service):
    service.client.media = pdf_bytes()
    aid = "škola:předměty:bi-test:sample.pdf"
    original = service.attachments.download(aid)
    service.attachments.save_transcription(aid, 1, "Existing vision text", original["source_hash"])
    native = service.attachments.read(aid, mode="native")
    assert native["method"] == "native_text" and "Synthetic SQL" in native["text"]
    assert service.attachments.read(aid)["text"] == "Existing vision text"
