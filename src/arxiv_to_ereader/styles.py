"""EPUB stylesheet for arXiv HTML content."""


def get_epub_stylesheet() -> str:
    """Return CSS suitable for EPUB readers."""
    return """
body {
    font-family: serif;
    line-height: 1.45;
    color: #111;
    background: #fff;
}

h1, h2, h3, h4, h5, h6 {
    font-family: sans-serif;
    line-height: 1.25;
    page-break-after: avoid;
    break-after: avoid;
}

p {
    margin: 0 0 0.75em 0;
}

a {
    color: #0645ad;
}

.cover {
    text-align: center;
    margin: 2em 0 3em;
}

.cover h1 {
    font-size: 1.7em;
}

.authors {
    font-style: italic;
}

.paper-id,
.date {
    color: #555;
}

.abstract {
    margin: 1.5em 0;
    padding: 0.75em;
    border-left: 0.25em solid #777;
    background: #f7f7f7;
}

img {
    max-width: 100%;
    height: auto;
    display: block;
    margin: 1em auto;
}

figure {
    margin: 1.25em 0;
    text-align: center;
    page-break-inside: avoid;
    break-inside: avoid;
}

figcaption,
.ltx_caption {
    font-size: 0.9em;
    font-style: italic;
    margin-top: 0.5em;
}

table {
    width: 100%;
    border-collapse: collapse;
    margin: 1em 0;
}

th,
td {
    border: 1px solid #777;
    padding: 0.25em 0.4em;
}

.table-wrapper {
    overflow-x: auto;
    margin: 1em 0;
}

.ltx_tabular {
    display: table;
    border-collapse: collapse;
    margin: 0.75em auto;
}

.ltx_tr {
    display: table-row;
}

.ltx_td,
.ltx_th {
    display: table-cell;
    padding: 0.25em 0.4em;
    vertical-align: middle;
}

.ltx_border_t { border-top: 1px solid #444; }
.ltx_border_b { border-bottom: 1px solid #444; }
.ltx_border_l { border-left: 1px solid #444; }
.ltx_border_r { border-right: 1px solid #444; }
.ltx_border_tt { border-top: 2px solid #000; }
.ltx_border_bb { border-bottom: 2px solid #000; }

math {
    font-size: 1em;
}

math[display="block"],
.math-block {
    display: block;
    text-align: center;
    margin: 1em 0;
}

table.ltx_equation,
table.ltx_eqn_table {
    border: none;
}

table.ltx_equation td,
table.ltx_eqn_table td {
    border: none;
}

.theorem-like,
.ltx_theorem,
.ltx_lemma,
.ltx_definition,
.ltx_corollary,
.ltx_proposition,
.ltx_remark,
.ltx_example {
    margin: 1em 0;
    padding: 0.75em;
    border-left: 0.25em solid #777;
    background: #f7f7f7;
}

.ltx_proof {
    margin: 0.75em 0;
    padding-left: 0.75em;
    border-left: 0.15em solid #999;
}

pre,
code,
.code-block,
.ltx_listing,
.ltx_verbatim {
    font-family: monospace;
    background: #f5f5f5;
}

pre,
.code-block,
.ltx_listing,
.ltx_verbatim {
    padding: 0.75em;
    white-space: pre-wrap;
    word-wrap: break-word;
}

.footnotes-section {
    border-top: 1px solid #ccc;
    margin-top: 2em;
    padding-top: 1em;
    font-size: 0.9em;
}

.footnote-ref {
    text-decoration: none;
}

.ltx_bibitem {
    margin-bottom: 0.75em;
    padding-left: 2em;
    text-indent: -2em;
}

.algorithm-block {
    margin: 1em 0;
    padding: 0.75em;
    border: 1px solid #999;
    background: #f5f5f5;
}

.algorithm-title {
    font-weight: bold;
    border-bottom: 1px solid #ccc;
    margin-bottom: 0.5em;
    padding-bottom: 0.4em;
}
"""
