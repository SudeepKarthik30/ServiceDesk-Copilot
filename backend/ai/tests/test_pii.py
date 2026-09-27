from ai.pii import mask_pii


def test_masks_email():
    assert mask_pii("contact me at jane.doe@example.com please") == "contact me at [EMAIL] please"


def test_masks_ip_address():
    assert mask_pii("server at 192.168.1.10 is down") == "server at [IP] is down"


def test_masks_phone_number():
    assert mask_pii("call +1 555-123-4567 now") == "call [PHONE] now"


def test_leaves_plain_text_unchanged():
    text = "My VPN keeps disconnecting every few minutes."
    assert mask_pii(text) == text


def test_handles_empty_and_none():
    assert mask_pii("") == ""
    assert mask_pii(None) is None
