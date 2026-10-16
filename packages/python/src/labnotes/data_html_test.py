from labnotes.data_html import data_html


def test_prefers_html_then_svg_then_png_then_text() -> None:
    assert data_html({"text/html": "<b>t</b>", "text/plain": "t"}) == "<b>t</b>"
    assert data_html({"image/svg+xml": "<svg/>", "image/png": "AA"}) == "<svg/>"
    assert data_html({"image/png": "AA", "text/plain": "x"}) == (
        '<img alt="" src="data:image/png;base64,AA">'
    )
    assert data_html({"text/plain": "1 < 2"}) == "<pre>1 &lt; 2</pre>"
    assert data_html({}) == "<pre></pre>"
