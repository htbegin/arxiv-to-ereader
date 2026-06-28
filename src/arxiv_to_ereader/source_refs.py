"""Reference fallback extraction from arXiv source archives."""

from __future__ import annotations

import io
import re
import tarfile
from html import escape

import httpx


def _strip_tex(value: str) -> str:
    value = value.replace("\n", " ")
    value = re.sub(r"\\[a-zA-Z]+\*?(?:\[[^\]]*\])?(?:\{([^{}]*)\})?", r"\1", value)
    value = re.sub(r"[{}]", "", value)
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def _split_bib_entries(text: str) -> list[str]:
    entries: list[str] = []
    pos = 0
    while True:
        start = text.find("@", pos)
        if start == -1:
            break

        brace = text.find("{", start)
        if brace == -1:
            break

        depth = 0
        end = brace
        while end < len(text):
            char = text[end]
            if char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    entries.append(text[start : end + 1])
                    pos = end + 1
                    break
            end += 1
        else:
            break

    return entries


def _parse_bib_fields(entry: str) -> dict[str, str]:
    first_brace = entry.find("{")
    if first_brace == -1:
        return {}

    body = entry[first_brace + 1 : -1]
    comma = body.find(",")
    if comma == -1:
        return {}

    fields: dict[str, str] = {}
    pos = comma + 1
    while pos < len(body):
        match = re.search(r"([A-Za-z][A-Za-z0-9_-]*)\s*=", body[pos:])
        if not match:
            break

        key = match.group(1).lower()
        value_start = pos + match.end()
        while value_start < len(body) and body[value_start].isspace():
            value_start += 1

        if value_start >= len(body):
            break

        if body[value_start] == "{":
            depth = 0
            value_end = value_start
            while value_end < len(body):
                char = body[value_end]
                if char == "{":
                    depth += 1
                elif char == "}":
                    depth -= 1
                    if depth == 0:
                        fields[key] = _strip_tex(body[value_start + 1 : value_end])
                        pos = value_end + 1
                        break
                value_end += 1
            else:
                break
        elif body[value_start] == '"':
            value_end = value_start + 1
            while value_end < len(body):
                if body[value_end] == '"' and body[value_end - 1] != "\\":
                    fields[key] = _strip_tex(body[value_start + 1 : value_end])
                    pos = value_end + 1
                    break
                value_end += 1
            else:
                break
        else:
            value_end = body.find(",", value_start)
            if value_end == -1:
                value_end = len(body)
            fields[key] = _strip_tex(body[value_start:value_end])
            pos = value_end + 1

    return fields


def _format_bib_entry(fields: dict[str, str]) -> str | None:
    title = fields.get("title")
    if not title:
        return None

    parts = []
    if fields.get("author"):
        parts.append(fields["author"].replace(" and ", "; "))
    parts.append(title)

    venue = fields.get("journal") or fields.get("booktitle") or fields.get("publisher")
    if venue:
        parts.append(venue)
    if fields.get("year"):
        parts.append(fields["year"])
    if fields.get("doi"):
        parts.append(f"doi:{fields['doi']}")
    if fields.get("url"):
        parts.append(fields["url"])

    return ". ".join(part for part in parts if part)


def _bib_to_html(text: str) -> str | None:
    items = []
    for entry in _split_bib_entries(text):
        formatted = _format_bib_entry(_parse_bib_fields(entry))
        if formatted:
            items.append(f'<li class="ltx_bibitem">{escape(formatted)}</li>')

    if not items:
        return None

    return (
        '<section class="ltx_bibliography" id="bib">'
        '<h2 class="ltx_title ltx_title_bibliography">References</h2>'
        f'<ul class="ltx_biblist">{"".join(items)}</ul>'
        "</section>"
    )


def _bbl_to_html(text: str) -> str | None:
    bibitems = re.split(r"\\bibitem(?:\[[^\]]*\])?\{[^}]+\}", text)
    items = []
    for item in bibitems[1:]:
        item = item.split("\\end{thebibliography}", 1)[0]
        item = _strip_tex(item)
        if item:
            items.append(f'<li class="ltx_bibitem">{escape(item)}</li>')

    if not items:
        return None

    return (
        '<section class="ltx_bibliography" id="bib">'
        '<h2 class="ltx_title ltx_title_bibliography">References</h2>'
        f'<ul class="ltx_biblist">{"".join(items)}</ul>'
        "</section>"
    )


def _read_archive_texts(content: bytes) -> tuple[list[str], list[str]]:
    bbl_texts: list[str] = []
    bib_texts: list[str] = []
    with tarfile.open(fileobj=io.BytesIO(content), mode="r:*") as archive:
        for member in archive.getmembers():
            lower = member.name.lower()
            if not member.isfile() or not (lower.endswith(".bbl") or lower.endswith(".bib")):
                continue
            extracted = archive.extractfile(member)
            if not extracted:
                continue
            text = extracted.read().decode("utf-8", "replace")
            if lower.endswith(".bbl"):
                bbl_texts.append(text)
            else:
                bib_texts.append(text)
    return bbl_texts, bib_texts


def fetch_source_references_html(arxiv_id: str, timeout: float = 30.0) -> str | None:
    """Fetch references from arXiv source when HTML bibliography is empty."""
    url = f"https://arxiv.org/src/{arxiv_id}"
    try:
        response = httpx.get(url, follow_redirects=True, timeout=timeout)
        response.raise_for_status()
    except Exception:
        return None

    try:
        bbl_texts, bib_texts = _read_archive_texts(response.content)
    except tarfile.TarError:
        return None

    for text in bbl_texts:
        html = _bbl_to_html(text)
        if html:
            return html

    for text in bib_texts:
        html = _bib_to_html(text)
        if html:
            return html

    return None
