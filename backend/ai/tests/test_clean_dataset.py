from ai.management.commands.clean_dataset import _dedupe_key, _normalize, _unescape_newlines


def test_normalize_collapses_whitespace_and_lowercases():
    assert _normalize("  Can't   Connect\nto VPN  ") == "can't connect to vpn"


def test_normalize_handles_none():
    assert _normalize(None) == ""


def test_dedupe_key_ignores_whitespace_and_case_differences():
    row_a = {"subject": "VPN Down", "body": "Can't connect to the VPN."}
    row_b = {"subject": "vpn down", "body": "can't   connect to the vpn."}
    assert _dedupe_key(row_a) == _dedupe_key(row_b)


def test_dedupe_key_differs_for_different_content():
    row_a = {"subject": "VPN Down", "body": "Can't connect."}
    row_b = {"subject": "Wifi Down", "body": "Can't connect."}
    assert _dedupe_key(row_a) != _dedupe_key(row_b)


def test_unescape_newlines_converts_literal_backslash_n():
    assert _unescape_newlines("line one\\nline two") == "line one\nline two"


def test_unescape_newlines_handles_none():
    assert _unescape_newlines(None) == ""
