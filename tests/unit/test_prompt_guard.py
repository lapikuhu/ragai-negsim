import pytest

from app.airag.prompt_guard.prompt_guard import contains_pii, ensemble_guard


@pytest.mark.parametrize(
    "text",
    [
        "Contact alex.smith+course@example.co.uk for the materials.",
        "Email learner_01@example.com.",
    ],
)
def test_contains_pii_detects_common_ascii_email_addresses(text):
    assert contains_pii(text) is True


@pytest.mark.parametrize(
    "text",
    [
        "Call me on +14155552671.",
        "Call me on +1 (415) 555-2671.",
        "The UK office number is +44 20 7946 0958.",
    ],
)
def test_contains_pii_detects_formatted_e164_phone_numbers(text):
    assert contains_pii(text) is True


@pytest.mark.parametrize(
    "text",
    [
        "Offer 250 euros by Friday at 10:00.",
        "Call 415-555-2671 after the session.",
        "Malformed email: a..b@example.com",
        "Malformed email: a@example",
        "Malformed email: a@-example.com",
        'Quoted email: "alex"@example.com',
        "Unicode email: alex@ex\u00e4mple.com",
        "Malformed phone: +01234567890",
        "Malformed phone: +1234567",
        "Malformed phone: +1234567890123456",
        "Malformed phone: +44/20/7946/0958",
        "Malformed phone: +44.20.7946.0958",
    ],
)
def test_contains_pii_ignores_non_pii_and_malformed_candidates(text):
    assert contains_pii(text) is False


@pytest.mark.parametrize(
    "text",
    [
        "Please contact alex.smith+course@example.co.uk.",
        "Please contact me on +1 (415) 555-2671.",
    ],
)
def test_ensemble_guard_rejects_detected_pii(text):
    assert ensemble_guard(text) is True
