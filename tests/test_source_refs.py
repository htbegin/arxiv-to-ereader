"""Tests for source archive reference fallback."""

import io
import tarfile

import respx
from httpx import Response

from arxiv_to_ereader.source_refs import fetch_source_references_html


def _tar_gz(files: dict[str, str]) -> bytes:
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as archive:
        for name, text in files.items():
            data = text.encode()
            info = tarfile.TarInfo(name)
            info.size = len(data)
            archive.addfile(info, io.BytesIO(data))
    return buffer.getvalue()


class TestSourceReferences:
    @respx.mock
    def test_fetches_bib_references(self) -> None:
        archive = _tar_gz(
            {
                "references.bib": """
                @inproceedings{key,
                  author = {Ada Lovelace and Alan Turing},
                  title = {Computing Engines},
                  booktitle = {Proceedings of Tests},
                  year = {2024}
                }
                """
            }
        )
        respx.get("https://arxiv.org/src/2605.03375").mock(
            return_value=Response(200, content=archive)
        )

        html = fetch_source_references_html("2605.03375")

        assert html is not None
        assert "Computing Engines" in html
        assert "Ada Lovelace; Alan Turing" in html

    @respx.mock
    def test_returns_none_on_missing_source(self) -> None:
        respx.get("https://arxiv.org/src/2605.03375").mock(return_value=Response(404))

        assert fetch_source_references_html("2605.03375") is None
