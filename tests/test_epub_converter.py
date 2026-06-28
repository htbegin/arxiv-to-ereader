"""Tests for EPUB conversion."""

import tempfile
import zipfile
from pathlib import Path

import respx
from httpx import Response

from arxiv_to_ereader.epub_converter import convert_to_epub
from arxiv_to_ereader.parser import Footnote, Paper, Section


def sample_paper() -> Paper:
    return Paper(
        id="2402.08954",
        title="A Sample Paper",
        authors=["John Doe", "Jane Smith"],
        abstract="This is the abstract.",
        sections=[
            Section(
                id="S1",
                title="Introduction",
                level=1,
                content='<div><p>See <a class="ltx_ref" href="#S2">Section 2</a>.</p></div>',
            ),
            Section(
                id="S2",
                title="Results",
                level=1,
                content='<div><p id="p1">Results.</p><img src="figure1.png" alt="Figure"/></div>',
            ),
        ],
        footnotes=[Footnote(id="fn-1", index=1, content="A note.")],
        references_html='<section id="bib"><ul><li id="bib1">A reference.</li></ul></section>',
        all_images={"figure1.png": "https://arxiv.org/html/2402.08954/figure1.png"},
    )


class TestConvertToEpub:
    def test_creates_valid_epub_zip(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = convert_to_epub(
                sample_paper(),
                Path(tmpdir) / "paper.epub",
                download_images=False,
            )

            assert path.exists()
            with zipfile.ZipFile(path) as epub:
                names = epub.namelist()
                assert names[0] == "mimetype"
                assert epub.read("mimetype") == b"application/epub+zip"
                assert "META-INF/container.xml" in names
                assert "EPUB/content.opf" in names
                assert "EPUB/nav.xhtml" in names
                assert "EPUB/cover.xhtml" in names
                assert any(name.startswith("EPUB/section-") for name in names)

    def test_rewrites_cross_section_links(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = convert_to_epub(
                sample_paper(),
                Path(tmpdir) / "paper.epub",
                download_images=False,
            )

            with zipfile.ZipFile(path) as epub:
                section_one = epub.read("EPUB/section-001-S1.xhtml").decode()
                assert 'href="section-002-S2.xhtml#S2"' in section_one

    def test_rewrites_missing_citation_spans_to_reference_links(self) -> None:
        paper = sample_paper()
        paper.sections[0].content = (
            '<p>Reuse is slow '
            '(<span class="ltx_ref ltx_missing_citation ltx_ref_self">flashgen</span>).</p>'
        )
        paper.references_html = (
            '<section id="bib"><ul>'
            '<li class="ltx_bibitem" id="bib-flashgen">FlashGen reference.</li>'
            "</ul></section>"
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            path = convert_to_epub(
                paper,
                Path(tmpdir) / "paper.epub",
                download_images=False,
            )

            with zipfile.ZipFile(path) as epub:
                section_one = epub.read("EPUB/section-001-S1.xhtml").decode()
                assert 'href="references.xhtml#bib-flashgen"' in section_one
                assert '>flashgen</a>' in section_one

    @respx.mock
    def test_packages_images(self) -> None:
        respx.get("https://arxiv.org/html/2402.08954/figure1.png").mock(
            return_value=Response(
                200,
                content=b"\x89PNG\r\n\x1a\n fake png",
                headers={"content-type": "image/png"},
            )
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            path = convert_to_epub(
                sample_paper(),
                Path(tmpdir) / "paper.epub",
                download_images=True,
            )

            with zipfile.ZipFile(path) as epub:
                names = set(epub.namelist())
                assert "EPUB/images/figure1.png" in names
                section_two = epub.read("EPUB/section-002-S2.xhtml").decode()
                assert 'src="images/figure1.png"' in section_two
