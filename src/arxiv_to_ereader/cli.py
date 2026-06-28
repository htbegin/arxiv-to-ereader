"""Command-line interface for arxiv2epub."""

import asyncio
import re
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from arxiv_to_ereader import __version__
from arxiv_to_ereader.epub_converter import convert_to_epub
from arxiv_to_ereader.fetcher import (
    ArxivFetchError,
    ArxivHTMLNotAvailable,
    fetch_paper,
    fetch_papers_batch,
    normalize_arxiv_id,
)
from arxiv_to_ereader.parser import parse_paper


def sanitize_filename(title: str, max_length: int = 80) -> str:
    """Convert a paper title to a safe filename."""
    filename = title.replace(":", "-")
    filename = filename.replace("/", "-").replace("\\", "-")
    filename = re.sub(r'[<>"|?*\x00-\x1f]', "", filename)
    filename = re.sub(r"[\s]+", "_", filename)
    filename = re.sub(r"[-]+", "-", filename)
    filename = re.sub(r"[_]+", "_", filename)
    filename = re.sub(r"[-_]{2,}", "_", filename)
    filename = filename.strip("_-")
    if len(filename) > max_length:
        filename = filename[:max_length].rsplit("_", 1)[0].strip("_-")
    return filename or "paper"


app = typer.Typer(
    name="arxiv2epub",
    help="Convert arXiv HTML papers to EPUB.",
    add_completion=False,
)
console = Console()


def version_callback(value: bool) -> None:
    """Print version and exit."""
    if value:
        console.print(f"arxiv2epub version {__version__}")
        raise typer.Exit()


@app.command()
def convert(
    papers: Annotated[
        list[str],
        typer.Argument(
            help="arXiv paper IDs or URLs (for example: 2402.08954 or https://arxiv.org/abs/2402.08954)"
        ),
    ],
    output: Annotated[
        Path | None,
        typer.Option(
            "--output",
            "-o",
            help="Output directory for EPUB files",
        ),
    ] = None,
    no_images: Annotated[
        bool,
        typer.Option(
            "--no-images",
            help="Do not download and package paper images",
        ),
    ] = False,
    use_id: Annotated[
        bool,
        typer.Option(
            "--use-id",
            help="Use arXiv ID for filename instead of paper title",
        ),
    ] = False,
    version: Annotated[
        bool | None,
        typer.Option(
            "--version",
            "-v",
            callback=version_callback,
            is_eager=True,
            help="Show version and exit",
        ),
    ] = None,
) -> None:
    """Convert arXiv papers to EPUB 3."""
    if output:
        output.mkdir(parents=True, exist_ok=True)

    if len(papers) == 1:
        _convert_single(papers[0], output, not no_images, use_id)
    else:
        _convert_batch(papers, output, not no_images, use_id)


def _output_path(paper_id: str, title: str, output_dir: Path | None, use_id: bool) -> Path:
    filename = paper_id.replace("/", "_") if use_id else sanitize_filename(title)
    return (output_dir / f"{filename}.epub") if output_dir else Path(f"{filename}.epub")


def _convert_single(
    paper_input: str,
    output_dir: Path | None,
    download_images: bool,
    use_id: bool,
) -> None:
    """Convert a single paper."""
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        try:
            paper_id = normalize_arxiv_id(paper_input)
        except ValueError as e:
            console.print(f"[red]Error:[/red] {e}")
            raise typer.Exit(1)

        task = progress.add_task(f"Fetching {paper_id}...", total=None)

        try:
            _, html = fetch_paper(paper_input)
        except ArxivHTMLNotAvailable as e:
            progress.stop()
            console.print(f"[yellow]Warning:[/yellow] {e}")
            raise typer.Exit(1)
        except ArxivFetchError as e:
            progress.stop()
            console.print(f"[red]Error:[/red] {e}")
            raise typer.Exit(1)

        progress.update(task, description=f"Parsing {paper_id}...")
        paper = parse_paper(html, paper_id)

        progress.update(task, description=f"Writing EPUB for {paper_id}...")
        epub_path = convert_to_epub(
            paper,
            output_path=_output_path(paper_id, paper.title, output_dir, use_id),
            download_images=download_images,
        )

        progress.stop()

    console.print(f"[green]Success![/green] Created: {epub_path}")
    console.print(f"  Title: {paper.title}")
    console.print(f"  Authors: {', '.join(paper.authors)}")


def _convert_batch(
    paper_inputs: list[str],
    output_dir: Path | None,
    download_images: bool,
    use_id: bool,
) -> None:
    """Convert multiple papers."""
    console.print(f"Converting {len(paper_inputs)} papers to EPUB...")

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        progress.add_task("Fetching papers...", total=None)
        results = asyncio.run(fetch_papers_batch(paper_inputs))
        progress.stop()

    success_count = 0
    error_count = 0

    for paper_id, result in results:
        if isinstance(result, Exception):
            console.print(f"[red]Error[/red] {paper_id}: {result}")
            error_count += 1
            continue

        console.print(f"[dim]Processing {paper_id}...[/dim]")

        try:
            paper = parse_paper(result, paper_id)
            epub_path = convert_to_epub(
                paper,
                output_path=_output_path(paper_id, paper.title, output_dir, use_id),
                download_images=download_images,
            )
            console.print(f"[green]Created:[/green] {epub_path}")
            success_count += 1
        except Exception as e:
            console.print(f"[red]Error[/red] converting {paper_id}: {e}")
            error_count += 1

    console.print()
    console.print(f"[bold]Summary:[/bold] {success_count} succeeded, {error_count} failed")


if __name__ == "__main__":
    app()
