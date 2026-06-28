"""arxiv2epub: Convert arXiv HTML papers to EPUB."""

__version__ = "0.1.0"

from arxiv_to_ereader.epub_converter import convert_to_epub
from arxiv_to_ereader.fetcher import fetch_paper, normalize_arxiv_id
from arxiv_to_ereader.parser import Paper, parse_paper

__all__ = [
    "__version__",
    "convert_to_epub",
    "fetch_paper",
    "normalize_arxiv_id",
    "Paper",
    "parse_paper",
]
