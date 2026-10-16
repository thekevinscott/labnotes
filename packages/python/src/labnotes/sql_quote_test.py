from labnotes.sql_quote import quote_identifier, quote_string


def test_quote_string_doubles_single_quotes() -> None:
    assert quote_string("it's") == "'it''s'"


def test_quote_identifier_doubles_double_quotes() -> None:
    assert quote_identifier('a"b') == '"a""b"'
