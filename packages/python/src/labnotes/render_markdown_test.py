from labnotes.render_markdown import render_markdown


def test_renders_tables_and_escapes_raw_html() -> None:
    html = render_markdown("| a |\n| - |\n| 1 |\n\n<script>x</script>\n")

    assert "<table>" in html
    assert "<script>" not in html


def test_curls_quotes() -> None:
    assert render_markdown('"quoted"') == "<p>\u201cquoted\u201d</p>\n"
