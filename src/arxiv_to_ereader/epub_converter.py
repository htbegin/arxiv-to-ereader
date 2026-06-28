"""Convert parsed arXiv papers to EPUB 3."""

from __future__ import annotations

import mimetypes
import re
import uuid
import zipfile
from dataclasses import dataclass
from datetime import UTC, datetime
from html import escape
from pathlib import Path
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup

from arxiv_to_ereader.parser import Paper
from arxiv_to_ereader.source_refs import citation_target_id
from arxiv_to_ereader.styles import get_epub_stylesheet


@dataclass(frozen=True)
class EpubAsset:
    """A packaged EPUB asset."""

    href: str
    media_type: str
    content: bytes


def _xml(text: str | None) -> str:
    return escape(text or "", quote=True)


def _safe_id(value: str, prefix: str = "item") -> str:
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "-", value).strip("-._")
    if not safe or not re.match(r"^[A-Za-z_]", safe):
        safe = f"{prefix}-{safe}" if safe else prefix
    return safe


def _safe_filename(value: str, fallback: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "-", value).strip("-._")
    return safe or fallback


def _media_type_for_url(url: str, content_type: str | None = None) -> tuple[str, str]:
    media_type = (content_type or "").split(";", 1)[0].strip().lower()
    if not media_type or "/" not in media_type:
        media_type = mimetypes.guess_type(urlparse(url).path)[0] or "image/png"

    extension = mimetypes.guess_extension(media_type) or Path(urlparse(url).path).suffix or ".png"
    if extension == ".jpe":
        extension = ".jpg"
    return media_type, extension


def _download_asset(url: str, timeout: float = 30.0) -> tuple[bytes, str] | None:
    try:
        with httpx.Client(timeout=timeout, follow_redirects=True) as client:
            response = client.get(url)
            response.raise_for_status()
            media_type, _ = _media_type_for_url(url, response.headers.get("content-type"))
            return response.content, media_type
    except httpx.HTTPError:
        return None


def _build_image_assets(
    paper: Paper,
    download_images: bool,
) -> tuple[dict[str, str], list[EpubAsset]]:
    if not download_images:
        return {}, []

    src_map: dict[str, str] = {}
    assets: list[EpubAsset] = []
    used_names: set[str] = set()

    for index, (original_src, absolute_url) in enumerate(paper.all_images.items(), start=1):
        result = _download_asset(absolute_url)
        if not result:
            continue

        content, media_type = result
        _, extension = _media_type_for_url(absolute_url, media_type)
        stem = Path(urlparse(absolute_url).path).stem
        filename = _safe_filename(stem, f"image-{index}") + extension
        while filename in used_names:
            filename = f"{Path(filename).stem}-{index}{Path(filename).suffix}"
        used_names.add(filename)

        href = f"images/{filename}"
        assets.append(EpubAsset(href=href, media_type=media_type, content=content))
        src_map[original_src] = href
        src_map[absolute_url] = href

    return src_map, assets


def _section_filename(section_id: str, index: int) -> str:
    return f"section-{index:03d}-{_safe_filename(section_id, f'section-{index}')}.xhtml"


def _scan_ids(html: str) -> set[str]:
    soup = BeautifulSoup(html, "lxml")
    return {tag["id"] for tag in soup.find_all(id=True)}


def _build_href_map(paper: Paper, section_files: dict[str, str]) -> dict[str, str]:
    href_map: dict[str, str] = {}
    for section in paper.sections:
        filename = section_files[section.id]
        href_map[section.id] = filename
        for element_id in _scan_ids(section.content):
            href_map[element_id] = filename

    if paper.references_html:
        href_map["references"] = "references.xhtml"
        for element_id in _scan_ids(paper.references_html):
            href_map[element_id] = "references.xhtml"

    for footnote in paper.footnotes:
        href_map[footnote.id] = "notes.xhtml"

    return href_map


def _rewrite_fragment(
    html: str,
    current_file: str,
    href_map: dict[str, str],
    image_map: dict[str, str],
    drop_unresolved_images: bool = True,
) -> str:
    soup = BeautifulSoup(html, "lxml")
    root = soup.body or soup

    for img in root.find_all("img"):
        src = img.get("src", "")
        if src in image_map:
            img["src"] = image_map[src]
        elif src.startswith("data:"):
            continue
        elif drop_unresolved_images:
            img.decompose()

    for citation in root.select(".ltx_missing_citation"):
        if citation.find_parent("a"):
            continue

        key = citation.get_text(strip=True)
        target_id = citation_target_id(key)
        target_file = href_map.get(target_id)
        if not key or not target_file:
            continue

        link = soup.new_tag(
            "a",
            href=f"#{target_id}" if target_file == current_file else f"{target_file}#{target_id}",
        )
        classes = citation.get("class", [])
        link["class"] = [*classes, "citation-link"]
        link.string = key
        citation.replace_with(link)

    for link in root.find_all("a", href=True):
        href = link["href"]
        if href.startswith("#"):
            target_id = href[1:]
            target_file = href_map.get(target_id)
            if target_file:
                link["href"] = (
                    f"#{target_id}" if target_file == current_file else f"{target_file}#{target_id}"
                )
        elif "arxiv.org/html/" in href and "#" in href:
            target_id = href.split("#", 1)[1]
            target_file = href_map.get(target_id)
            if target_file:
                link["href"] = (
                    f"#{target_id}" if target_file == current_file else f"{target_file}#{target_id}"
                )

    return "".join(str(child) for child in root.contents)


def _xhtml_document(title: str, body: str, css_href: str = "style.css") -> str:
    return f"""<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml"
      xmlns:epub="http://www.idpf.org/2007/ops"
      lang="en" xml:lang="en">
<head>
  <meta charset="utf-8"/>
  <title>{_xml(title)}</title>
  <link rel="stylesheet" type="text/css" href="{_xml(css_href)}"/>
</head>
<body>
{body}
</body>
</html>
"""


def _cover_document(paper: Paper) -> str:
    authors = ", ".join(paper.authors) if paper.authors else "Unknown"
    date = f'<p class="date">{_xml(paper.date)}</p>' if paper.date else ""
    abstract = ""
    if paper.abstract:
        abstract = f"""
<section class="abstract" id="abstract">
  <h2>Abstract</h2>
  <p>{_xml(paper.abstract)}</p>
</section>"""

    body = f"""
<section class="cover" id="cover">
  <h1>{_xml(paper.title)}</h1>
  <p class="authors">{_xml(authors)}</p>
  {date}
  <p class="paper-id">arXiv:{_xml(paper.id)}</p>
</section>
{abstract}
"""
    return _xhtml_document(paper.title, body)


def _section_document(
    paper: Paper,
    section_id: str,
    title: str,
    level: int,
    content: str,
    current_file: str,
    href_map: dict[str, str],
    image_map: dict[str, str],
) -> str:
    body_level = min(level + 1, 6)
    rewritten = _rewrite_fragment(content, current_file, href_map, image_map)
    body = f"""
<section id="{_xml(section_id)}">
  <h{body_level}>{_xml(title)}</h{body_level}>
  {rewritten}
</section>
"""
    return _xhtml_document(f"{paper.title} - {title}", body)


def _references_document(paper: Paper, href_map: dict[str, str], image_map: dict[str, str]) -> str:
    refs = _rewrite_fragment(paper.references_html or "", "references.xhtml", href_map, image_map)
    body = f"""
<section id="references" class="references">
  <h1>References</h1>
  {refs}
</section>
"""
    return _xhtml_document(f"{paper.title} - References", body)


def _notes_document(paper: Paper, href_map: dict[str, str]) -> str:
    items = []
    for footnote in paper.footnotes:
        content = _rewrite_fragment(footnote.content, "notes.xhtml", href_map, {})
        back_target = href_map.get(f"fnref-{footnote.index}", "cover.xhtml")
        items.append(
            f'<li id="{_xml(footnote.id)}">{content} '
            f'<a href="{_xml(back_target)}#fnref-{footnote.index}" class="footnote-back">^</a></li>'
        )

    body = f"""
<section id="notes" class="footnotes-section">
  <h1>Notes</h1>
  <ol>
    {"".join(items)}
  </ol>
</section>
"""
    return _xhtml_document(f"{paper.title} - Notes", body)


def _nav_document(paper: Paper, spine_items: list[tuple[str, str]]) -> str:
    items = "\n".join(
        f'    <li><a href="{_xml(href)}">{_xml(label)}</a></li>' for href, label in spine_items
    )
    return f"""<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml"
      xmlns:epub="http://www.idpf.org/2007/ops"
      lang="en" xml:lang="en">
<head>
  <meta charset="utf-8"/>
  <title>Table of Contents</title>
</head>
<body>
  <nav epub:type="toc" id="toc">
    <h1>Table of Contents</h1>
    <ol>
{items}
    </ol>
  </nav>
</body>
</html>
"""


def _container_xml() -> str:
    return """<?xml version="1.0" encoding="UTF-8"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles>
    <rootfile full-path="EPUB/content.opf" media-type="application/oebps-package+xml"/>
  </rootfiles>
</container>
"""


def _content_opf(
    paper: Paper,
    manifest_docs: list[tuple[str, str]],
    assets: list[EpubAsset],
    spine_ids: list[str],
) -> str:
    modified = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    uid = f"urn:uuid:{uuid.uuid5(uuid.NAMESPACE_URL, 'arxiv:' + paper.id)}"
    authors = "\n".join(f"    <dc:creator>{_xml(author)}</dc:creator>" for author in paper.authors)

    docs = "\n".join(
        f'    <item id="{_xml(item_id)}" href="{_xml(href)}" media-type="application/xhtml+xml"/>'
        for item_id, href in manifest_docs
    )
    asset_items = "\n".join(
        f'    <item id="{_xml(_safe_id(asset.href, "asset"))}" '
        f'href="{_xml(asset.href)}" media-type="{_xml(asset.media_type)}"/>'
        for asset in assets
    )
    spine = "\n".join(f'    <itemref idref="{_xml(item_id)}"/>' for item_id in spine_ids)

    return f"""<?xml version="1.0" encoding="UTF-8"?>
<package xmlns="http://www.idpf.org/2007/opf" unique-identifier="pub-id" version="3.0">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dc:identifier id="pub-id">{_xml(uid)}</dc:identifier>
    <dc:title>{_xml(paper.title)}</dc:title>
{authors}
    <dc:language>en</dc:language>
    <dc:source>https://arxiv.org/abs/{_xml(paper.id)}</dc:source>
    <meta property="dcterms:modified">{modified}</meta>
  </metadata>
  <manifest>
    <item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>
    <item id="style" href="style.css" media-type="text/css"/>
{docs}
{asset_items}
  </manifest>
  <spine>
{spine}
  </spine>
</package>
"""


def convert_to_epub(
    paper: Paper,
    output_path: Path | str | None = None,
    download_images: bool = True,
) -> Path:
    """Convert a parsed arXiv paper to an EPUB 3 file."""
    if output_path is None:
        output_path = Path(f"{paper.id.replace('/', '_')}.epub")
    else:
        output_path = Path(output_path)
        if output_path.suffix.lower() != ".epub":
            output_path = output_path.with_suffix(".epub")

    output_path.parent.mkdir(parents=True, exist_ok=True)

    image_map, image_assets = _build_image_assets(paper, download_images)
    section_files = {
        section.id: _section_filename(section.id, index)
        for index, section in enumerate(paper.sections, start=1)
    }
    href_map = _build_href_map(paper, section_files)

    documents: list[tuple[str, str, str, str]] = []
    spine: list[tuple[str, str]] = []

    documents.append(("cover", "cover.xhtml", "Cover", _cover_document(paper)))
    spine.append(("cover.xhtml", "Cover"))

    for index, section in enumerate(paper.sections, start=1):
        item_id = f"section-{index:03d}"
        href = section_files[section.id]
        documents.append(
            (
                item_id,
                href,
                section.title,
                _section_document(
                    paper,
                    section.id,
                    section.title,
                    section.level,
                    section.content,
                    href,
                    href_map,
                    image_map,
                ),
            )
        )
        spine.append((href, section.title))

    if paper.references_html:
        documents.append(
            (
                "references",
                "references.xhtml",
                "References",
                _references_document(paper, href_map, image_map),
            )
        )
        spine.append(("references.xhtml", "References"))

    if paper.footnotes:
        documents.append(("notes", "notes.xhtml", "Notes", _notes_document(paper, href_map)))
        spine.append(("notes.xhtml", "Notes"))

    manifest_docs = [(item_id, href) for item_id, href, _, _ in documents]
    spine_ids = [item_id for item_id, _, _, _ in documents]

    with zipfile.ZipFile(output_path, "w") as epub:
        epub.writestr(
            zipfile.ZipInfo("mimetype"),
            "application/epub+zip",
            compress_type=zipfile.ZIP_STORED,
        )
        epub.writestr(
            "META-INF/container.xml",
            _container_xml(),
            compress_type=zipfile.ZIP_DEFLATED,
        )
        epub.writestr("EPUB/style.css", get_epub_stylesheet(), compress_type=zipfile.ZIP_DEFLATED)
        epub.writestr(
            "EPUB/nav.xhtml",
            _nav_document(paper, spine),
            compress_type=zipfile.ZIP_DEFLATED,
        )
        epub.writestr(
            "EPUB/content.opf",
            _content_opf(paper, manifest_docs, image_assets, spine_ids),
            compress_type=zipfile.ZIP_DEFLATED,
        )

        for _, href, _, content in documents:
            epub.writestr(f"EPUB/{href}", content, compress_type=zipfile.ZIP_DEFLATED)

        for asset in image_assets:
            epub.writestr(f"EPUB/{asset.href}", asset.content, compress_type=zipfile.ZIP_DEFLATED)

    return output_path
