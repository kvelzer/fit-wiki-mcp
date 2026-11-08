"""DokuWiki XHTML parsers with preserved heading structure and resolved links."""

import re
from urllib.parse import parse_qs, urljoin, urlsplit

from bs4 import BeautifulSoup, Tag
from markdownify import MarkdownConverter

from .errors import WikiError
from .urls import classify_link, identity, namespace_url, same_origin


class Converter(MarkdownConverter):
    def convert_span(self, el, text, parent_tags):
        # Preserve rendered math alternatives when the template provides them.
        if el.has_attr("data-tex"):
            return f"${el['data-tex']}$"
        return text


def content_root(html: str) -> tuple[BeautifulSoup, Tag]:
    soup = BeautifulSoup(html, "html.parser")
    # CSS selector unions return document order, not the requested priority.
    root = next(
        (
            match
            for selector in (
                ".dokuwiki .page",
                "div.page",
                "main article",
                "article",
                "main",
                ".dokuwiki",
            )
            if (match := soup.select_one(selector)) is not None
        ),
        None,
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
            element["href"] = (
                item["url"]
                if item and item["kind"] == "external"
                else urljoin(base, element["href"])
            )
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


def parse_comments(html: str, base: str, ident: str) -> dict:
    """Read the discussion plugin from the normal page; XHTML exports omit it."""
    content_root(html)  # A changed/login/error layout must not look like an empty discussion.
    soup = BeautifulSoup(html, "html.parser")
    wrapper = soup.select_one("#comment_wrapper, .comment_wrapper, #discussion__comments")
    if wrapper is None:
        if soup.select_one(".hentry .comment_head, .hentry .comment_body"):
            raise WikiError("PARSE_ERROR", "Unrecognized wiki discussion container.")
        return {"page_id": ident, "source_url": base, "discussion_available": False, "items": []}
    entries = wrapper.select(".hentry")
    by_node, comments, seen_ids = {}, [], set()
    for entry in entries:
        header = next(
            (h for h in entry.select(".comment_head") if h.find_parent(class_="hentry") is entry),
            None,
        )
        body = next(
            (b for b in entry.select(".comment_body") if b.find_parent(class_="hentry") is entry),
            None,
        )
        if header is None or body is None:
            raise WikiError("PARSE_ERROR", "A discussion comment is missing its header or body.")
        anchor = header.select_one('[id^="comment_"], [name^="comment_"]')
        cid = (anchor.get("id") or anchor.get("name")) if anchor else entry.get("id")
        if not cid or not re.fullmatch(r"[\w-]{1,200}", cid) or cid in seen_ids:
            raise WikiError(
                "PARSE_ERROR", "A discussion comment has a missing or duplicate identifier."
            )
        parent_id = None
        for ancestor in entry.parents:
            if ancestor is wrapper:
                break
            if id(ancestor) in by_node:
                parent_id = by_node[id(ancestor)]
                break
            if "comment_replies" in ancestor.get("class", []):
                previous = ancestor.find_previous_sibling(class_="hentry")
                if previous is not None and id(previous) in by_node:
                    parent_id = by_node[id(previous)]
                    break
        by_node[id(entry)] = cid
        seen_ids.add(cid)
        author = header.select_one(".fn")
        published = header.select_one(".published, time")
        timestamp = (
            (
                published.get("datetime")
                or published.get("title")
                or published.get_text(" ", strip=True)
            )
            if published
            else None
        )
        # Copy the body: removing controls must not alter the reply hierarchy used above.
        clean = BeautifulSoup(str(body), "html.parser")
        for control in clean.select(
            "script, style, form, .comment_buttons, .hiddenHead, .hiddenElements"
        ):
            control.decompose()
        links, attachments, seen = [], [], set()
        for element in clean.select("a[href], img[src]"):
            attr = "href" if element.name == "a" else "src"
            nested_image = element.find("img") if element.name == "a" else None
            title = element.get_text(" ", strip=True) or element.get("alt", "")
            if not title and nested_image:
                title = nested_image.get("alt", "")
            item = link_item(element[attr], title, base)
            if item:
                key = (item["kind"], item.get("id", item["url"]))
                if key not in seen:
                    links.append(item)
                    if item["kind"] == "attachment":
                        attachments.append(
                            {
                                "attachment_id": item["id"],
                                "source_url": item["url"],
                                "title": item["title"],
                            }
                        )
                    seen.add(key)
            element[attr] = item["url"] if item else urljoin(base, element[attr])
        markdown = Converter(heading_style="ATX", bullets="-").convert(str(clean)).strip()
        comments.append(
            {
                "comment_id": cid,
                "parent_id": parent_id,
                "author": author.get_text(" ", strip=True) if author else None,
                "published_at": timestamp,
                "source_url": base + "#" + cid,
                "markdown": markdown,
                "links": links,
                "attachments": attachments,
            }
        )
    return {"page_id": ident, "source_url": base, "discussion_available": True, "items": comments}


def parse_namespace(html: str, namespace: str) -> list[dict]:
    """Parse a single authenticated AJAX index fragment without recursively expanding it."""
    soup = BeautifulSoup(html, "html.parser")
    if not html.strip():
        return []
    nodes = soup.select("a.idx_dir[href], a.wikilink1[href]")
    if not nodes or soup.select_one("html, form, script, .dokuwiki"):
        raise WikiError("PARSE_ERROR", "Expected a namespace index fragment.")
    results, seen = [], set()
    for link in nodes:
        href = urljoin("https://fit-wiki.cz/", link["href"])
        if not same_origin(href):
            continue
        title = link.get_text(" ", strip=True)
        if "idx_dir" in link.get("class", []):
            raw = parse_qs(urlsplit(href).query).get("idx", [""])[0]
            try:
                ident = identity(raw)
            except WikiError:
                continue
            if ident.rpartition(":")[0] != namespace:
                continue
            item = {
                "kind": "namespace",
                "namespace_id": ident,
                "source_url": namespace_url(ident),
                "title": title or ident,
            }
        else:
            parsed = classify_link(href)
            if not parsed or parsed["kind"] != "page":
                continue
            ident = parsed["id"]
            item = {
                "kind": "page",
                "page_id": ident,
                "source_url": parsed["url"],
                "title": title or ident,
            }
        if ident.rpartition(":")[0] != namespace:
            continue
        key = (item["kind"], ident)
        if key not in seen:
            results.append(item)
            seen.add(key)
    if not results:
        raise WikiError(
            "PARSE_ERROR",
            "Index fragment did not contain direct children of the requested namespace.",
        )
    return results
