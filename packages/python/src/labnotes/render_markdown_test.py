from labnotes.render_markdown import render_markdown


def test_renders_tables_and_escapes_raw_html() -> None:
    html = render_markdown("| a |\n| - |\n| 1 |\n\n<script>x</script>\n")

    assert "<table>" in html
    assert "<script>" not in html


def test_curls_quotes() -> None:
    assert render_markdown('"quoted"') == "<p>\u201cquoted\u201d</p>\n"


def test_python_blocks_become_runnable_cells_with_saved_output() -> None:
    html = render_markdown(
        "```python\na\n```\n\n```js\nb\n```\n\n```python\nc\n```\n",
        ["<pre>out</pre>"],
    )

    assert html.count('<button type="button" class="run">Run</button>') == 2
    assert '<div class="cell" data-block="0">' in html
    assert '<div class="cell" data-block="1">' in html
    assert '<output class="cell-output"><pre>out</pre></output>' in html
    assert '<output class="cell-output"></output>' in html
    assert '<pre><code class="language-js">b\n</code></pre>' in html


def test_numbers_cells_per_document() -> None:
    render_markdown("```python\na\n```\n")

    assert 'data-block="0"' in render_markdown("```python\nz\n```\n")
