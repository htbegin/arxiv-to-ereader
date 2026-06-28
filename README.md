# arxiv2epub

Convert arXiv HTML papers to EPUB 3.

This project reuses the arXiv HTML fetch/parser pipeline from `arxiv-to-ereader`, then packages the parsed paper as an EPUB instead of rendering a PDF.

## Install

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
```

For development:

```bash
python -m pip install -e ".[dev]"
```

## Usage

```bash
arxiv2epub 2402.08954
arxiv2epub https://arxiv.org/abs/2402.08954 -o ./epubs
arxiv2epub 2402.08954 2401.12345 -o ./epubs --use-id
arxiv2epub 2402.08954 --no-images
```

The converter fetches the official arXiv HTML page from:

```text
https://arxiv.org/html/{arxiv_id}
```

## What It Handles

- arXiv IDs and arXiv abs/html/pdf URLs
- title, authors, abstract, sections, references, and footnotes
- LaTeXML tables, including span-based `.ltx_tabular` structures
- same-paper reference links rewritten across EPUB chapter files
- images packaged under `EPUB/images/`
- MathML preserved in XHTML for EPUB 3 readers

## Development

```bash
python -m pip install -e ".[dev]"
python -m pytest
python -m ruff check src tests
```

No `uv` workflow is required.
