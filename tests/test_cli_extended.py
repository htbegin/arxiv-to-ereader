"""Extended CLI tests with mocked HTTP."""

import tempfile
import zipfile
from pathlib import Path

import respx
from httpx import Response
from typer.testing import CliRunner

from arxiv_to_ereader.cli import app

runner = CliRunner()

SAMPLE_HTML = """
<!DOCTYPE html>
<html>
<head><title>Test Paper</title></head>
<body>
<article class="ltx_document">
    <h1 class="ltx_title ltx_title_document">Test Paper Title</h1>
    <div class="ltx_authors">
        <span class="ltx_personname">Test Author</span>
    </div>
    <div class="ltx_abstract"><p>Test abstract.</p></div>
    <section class="ltx_section" id="S1">
        <h2 class="ltx_title ltx_title_section">1 Introduction</h2>
        <div class="ltx_para">
            <p>Test content with <a class="ltx_ref" href="#S2">a ref</a>.</p>
        </div>
    </section>
    <section class="ltx_section" id="S2">
        <h2 class="ltx_title ltx_title_section">2 Results</h2>
        <figure class="ltx_figure" id="fig1">
            <img src="/html/2402.08954/figure1.png" alt="Figure"/>
            <figcaption class="ltx_caption">Figure 1.</figcaption>
        </figure>
    </section>
</article>
</body>
</html>
"""


class TestCLIConversion:
    """Tests for actual CLI conversion with mocked HTTP."""

    @respx.mock
    def test_convert_single_paper_success(self) -> None:
        paper_id = "2402.08954"
        respx.get(f"https://arxiv.org/html/{paper_id}").mock(
            return_value=Response(200, text=SAMPLE_HTML)
        )
        respx.get(f"https://arxiv.org/src/{paper_id}").mock(return_value=Response(404))

        with tempfile.TemporaryDirectory() as tmpdir:
            result = runner.invoke(app, [paper_id, "-o", tmpdir, "--no-images"])

            assert result.exit_code == 0
            assert "Success" in result.stdout
            assert "Test Paper Title" in result.stdout

            epub_files = list(Path(tmpdir).glob("*.epub"))
            assert len(epub_files) == 1

            with zipfile.ZipFile(epub_files[0]) as epub:
                names = set(epub.namelist())
                assert "mimetype" in names
                assert "META-INF/container.xml" in names
                assert "EPUB/content.opf" in names
                assert "EPUB/nav.xhtml" in names

    @respx.mock
    def test_convert_single_paper_not_found(self) -> None:
        paper_id = "0000.00000"
        respx.get(f"https://arxiv.org/html/{paper_id}").mock(return_value=Response(404))

        result = runner.invoke(app, [paper_id])

        assert result.exit_code == 1
        assert "not available" in result.stdout.lower()

    @respx.mock
    def test_convert_from_url(self) -> None:
        paper_id = "2402.08954"
        url = f"https://arxiv.org/abs/{paper_id}"
        respx.get(f"https://arxiv.org/html/{paper_id}").mock(
            return_value=Response(200, text=SAMPLE_HTML)
        )
        respx.get(f"https://arxiv.org/src/{paper_id}").mock(return_value=Response(404))

        with tempfile.TemporaryDirectory() as tmpdir:
            result = runner.invoke(app, [url, "-o", tmpdir, "--no-images"])

            assert result.exit_code == 0
            assert "Success" in result.stdout


class TestCLIBatchConversion:
    """Tests for batch conversion via CLI."""

    @respx.mock
    def test_batch_convert_multiple_papers(self) -> None:
        papers = ["2402.08954", "1234.56789"]

        for paper_id in papers:
            respx.get(f"https://arxiv.org/html/{paper_id}").mock(
                return_value=Response(200, text=SAMPLE_HTML)
            )
            respx.get(f"https://arxiv.org/src/{paper_id}").mock(return_value=Response(404))

        with tempfile.TemporaryDirectory() as tmpdir:
            result = runner.invoke(app, [*papers, "-o", tmpdir, "--no-images", "--use-id"])

            assert result.exit_code == 0
            assert "2 succeeded" in result.stdout
            assert len(list(Path(tmpdir).glob("*.epub"))) == 2

    @respx.mock
    def test_batch_convert_partial_failure(self) -> None:
        respx.get("https://arxiv.org/html/2402.08954").mock(
            return_value=Response(200, text=SAMPLE_HTML)
        )
        respx.get("https://arxiv.org/src/2402.08954").mock(return_value=Response(404))
        respx.get("https://arxiv.org/html/0000.00000").mock(return_value=Response(404))

        with tempfile.TemporaryDirectory() as tmpdir:
            result = runner.invoke(
                app,
                ["2402.08954", "0000.00000", "-o", tmpdir, "--no-images"],
            )

            assert result.exit_code == 0
            assert "1 succeeded" in result.stdout
            assert "1 failed" in result.stdout
