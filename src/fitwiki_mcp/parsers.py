"""DokuWiki XHTML parsers with preserved heading structure and resolved links."""

import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Tag
from markdownify import MarkdownConverter

from .errors import WikiError
from .urls import classify_link, identity


class Converter(MarkdownConverter):
    def convert_span(self, el, text, parent_tags):
        # Preserve rendered math alternatives when the template provides them.
        if el.has_attr("data-tex"):
            return f"${el['data-tex']}$"
        return text


def content_root(html: str) -> tuple[BeautifulSoup, Tag]:
    soup = BeautifulSoup(html, "html.parser")
    root = soup.select_one(
        ".dokuwiki .page, .dokuwiki div.page, div.page, main article, article, main, .dokuwiki"
    )
    if root is None:
        # DokuWiki XHTML export uses body > div.dokuwiki; never silently parse arbitrary login body.
        raise WikiError("PARSE_ERROR", "Main DokuWiki content container was not found.")
    for element in root.select(
        "script, style, form, .editbutton_section, .secedit, .dw__toc, .toc, .page-tools, .navbar"
    ):
        element.decompose()
    return soup, root


def link_item(href: str, title: str, base: str) -> dict | None:
    item = classify_link(href, base)
    if item:
        item["title"] = title.strip() or item.get("id", href)
    return item


def parse_courses(html: str, base: str) -> list[dict]:
    _, root = content_root(html)
    courses = {}
    prefix = "škola:předměty:"
    for link in root.select("a[href]"):
        item = link_item(link["href"], link.get_text(" ", strip=True), base)
        if not item or item["kind"] != "page" or not item["id"].startswith(prefix):
            continue
        tail = item["id"][len(prefix) :]
        parts = tail.split(":")
        if len(parts) > 1 and not (len(parts) == 2 and parts[1] == "obsah"):
            continue
        # Codes are discovered, never guessed from arbitrary input.
        if not re.fullmatch(r"[a-z]{1,5}-[\w.-]+", parts[0], re.I):
            continue
        course = {
            "course_id": item["id"],
            "code": parts[0].upper(),
            "title": item["title"],
            "source_url": item["url"],
        }
        courses[item["id"]] = course
    if not courses:
        raise WikiError(
            "PARSE_ERROR", "The wiki course catalog contained no recognized course links."
        )
    return sorted(courses.values(), key=lambda c: (c["code"], c["course_id"]))


def parse_page(html: str, base: str, ident: str) -> dict:
    _, root = content_root(html)
    heading = root.find(re.compile(r"^h[1-6]$"))
    title = heading.get_text(" ", strip=True) if heading else ident.split(":")[-1]
    sections, links, stack, seen = [], [], [], set()
    for element in root.descendants:
        if not isinstance(element, Tag):
            continue
        if re.fullmatch(r"h[1-6]", element.name or ""):
            level = int(element.name[1])
            anchor = element.get("id") or f"section-{len(sections) + 1}"
            # Heading IDs may live in an inner anchor in some templates.
            section = {
                "section_id": anchor,
                "title": element.get_text(" ", strip=True),
                "level": level,
                "parent": None,
            }
            while stack and stack[-1][0] >= level:
                stack.pop()
            section["parent"] = stack[-1][1] if stack else None
            stack.append((level, anchor))
            sections.append(section)
        if element.name == "a" and element.get("href"):
            item = link_item(element["href"], element.get_text(" ", strip=True), base)
            if item:
                key = (item["kind"], item.get("id", item["url"]), stack[-1][1] if stack else None)
                if key not in seen:
                    item["section_id"] = stack[-1][1] if stack else None
                    links.append(item)
                    seen.add(key)
            element["href"] = urljoin(base, element["href"])
        if element.name == "img" and element.get("src"):
            source = urljoin(base, element["src"])
            item = link_item(source, element.get("alt", ""), base)
            if item and item["kind"] == "attachment":
                key = ("attachment", item["id"], stack[-1][1] if stack else None)
                if key not in seen:
                    item["section_id"] = stack[-1][1] if stack else None
                    links.append(item)
                    seen.add(key)
            element["src"] = source
    markdown = (
        Converter(heading_style="ATX", bullets="-", code_language="").convert(str(root)).strip()
    )
    if not markdown:
        raise WikiError("PARSE_ERROR", "The wiki page had no readable content.")
    warnings = []
    if root.select("img"):
        warnings.append(
            "Images may contain additional text or formulas; use get_material_image/read_attachment."
        )
    if root.select(".math, .mathjax, .katex, math"):
        warnings.append("Check rendered mathematics against the original page.")
    return {
        "page_id": ident,
        "title": title,
        "source_url": base,
        "markdown": markdown,
        "sections": sections,
        "links": links,
        "warnings": warnings,
        "revision": None,
    }


def section_markdown(markdown: str, sections: list[dict], section_id: str) -> str:
    target = next((section for section in sections if section["section_id"] == section_id), None)
    if target is None:
        raise WikiError("NOT_FOUND", "The requested section does not exist on this page.")
    ordinal = next(i for i, section in enumerate(sections) if section["section_id"] == section_id)
    lines = markdown.splitlines()
    positions, fence = [], None
    for index, line in enumerate(lines):
        marker = re.match(r"^\s*(`{3,}|~{3,})", line)
        if marker:
            char = marker[1][0]
            if fence is None:
                fence = char
            elif fence == char:
                fence = None
            continue
        match = re.match(r"^(#{1,6})\s+", line) if fence is None else None
        if match:
            positions.append((index, len(match[1])))
    if ordinal >= len(positions):
        raise WikiError(
            "PARSE_ERROR", "Could not locate the requested section in converted content."
        )
    start, level = positions[ordinal]
    end = next(
        (index for index, other_level in positions[ordinal + 1 :] if other_level <= level),
        len(lines),
    )
    return "\n".join(lines[start:end])


def parse_search(html: str, base: str, scope: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    container = soup.select_one(".search_fulltextresult")
    if container is None:
        if soup.select_one(".nothing"):
            return []
        raise WikiError("PARSE_ERROR", "Fulltext results container was not found.")
    results, seen = [], set()
    for element in container.select(".search_fullpage_result"):
        link = element.select_one("a.wikilink1[href], .search_snippet + a[href], a[href]")
        if link is None:
            continue
        item = link_item(link["href"], link.get_text(" ", strip=True), base)
        if not item or item["kind"] != "page":
            continue
        ident = identity(item["id"])
        if not (ident == scope or ident.startswith(scope + ":")) or ident in seen:
            continue
        snippet = element.select_one(".search_snippet")
        results.append(
            {
                "page_id": ident,
                "title": item["title"],
                "source_url": item["url"],
                "snippet": snippet.get_text(" ", strip=True)[:1200] if snippet else "",
                "origin": "wiki_fulltext",
            }
        )
        seen.add(ident)
    return results
