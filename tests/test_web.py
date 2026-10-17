"""Template helpers in lattice.kernel.web."""


def test_links_url_encode_row_values():
    from lattice.kernel.web import fmt, fmt_url
    row = {"id": 7, "subject": "Q&A #2 + more"}
    assert fmt_url("/inbox?q={subject}", row) == "/inbox?q=Q%26A%20%232%20%2B%20more"
    assert fmt("{subject}", row) == "Q&A #2 + more"


def test_js_filter_escapes_values_for_alpine_attributes():
    from lattice.kernel.web import env
    out = env.from_string('<b @click="run({{ k|js }})">').render(k="a'); alert(1); ('")
    assert out == '<b @click="run(&#34;a&#39;); alert(1); (&#39;&#34;)">'
