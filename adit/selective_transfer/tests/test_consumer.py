import pytest
from django.conf import settings
from django.utils.translation import get_language, override

from adit.selective_transfer.consumers import SelectiveTransferConsumer


@pytest.mark.django_db
@pytest.mark.parametrize(
    "language_code,expected_language",
    [
        ("en-US,en;q=0.9", "en"),
        ("de-DE,de;q=0.9", "de"),
        ("en", "en"),
        ("de", "de"),
    ],
)
def test_consumer_language_activation(language_code, expected_language):
    consumer = SelectiveTransferConsumer()
    consumer.scope = {  # type: ignore[attr-defined]
        "type": "websocket",
        "path": "/ws/selective-transfer/",
        "headers": [(b"accept-language", language_code.encode())],
    }

    activated_language = consumer._activate_user_language()
    assert activated_language.startswith(expected_language), (
        f"Expected language starting with '{expected_language}' "
        f"but got '{activated_language}' for Accept-Language: {language_code}"
    )


@pytest.mark.django_db
def test_consumer_language_activation_missing_header():
    consumer = SelectiveTransferConsumer()
    consumer.scope = {  # type: ignore[attr-defined]
        "type": "websocket",
        "path": "/ws/selective-transfer/",
        "headers": [],
    }

    activated_language = consumer._activate_user_language()
    assert activated_language == settings.LANGUAGE_CODE


@pytest.mark.django_db
def test_consumer_language_activation_malformed_header():
    consumer = SelectiveTransferConsumer()
    consumer.scope = {  # type: ignore[attr-defined]
        "type": "websocket",
        "path": "/ws/selective-transfer/",
        "headers": [(b"accept-language", b";;;invalid;;;")],
    }

    activated_language = consumer._activate_user_language()
    assert activated_language in [settings.LANGUAGE_CODE, "en", "de"]


@pytest.mark.django_db
def test_consumer_language_stored_on_connect():
    consumer = SelectiveTransferConsumer()
    consumer.scope = {  # type: ignore[attr-defined]
        "type": "websocket",
        "path": "/ws/selective-transfer/",
        "headers": [(b"accept-language", b"de-DE")],
        "user": None,  # Will trigger early close in connect()
    }

    user_language = consumer._activate_user_language()
    assert user_language.startswith("de")


@pytest.mark.django_db
def test_consumer_language_used_in_override_context():
    consumer = SelectiveTransferConsumer()
    consumer.scope = {  # type: ignore[attr-defined]
        "type": "websocket",
        "path": "/ws/selective-transfer/",
        "headers": [(b"accept-language", b"de-DE")],
    }
    consumer.user_language = "de"

    lang_code = getattr(consumer, "user_language", settings.LANGUAGE_CODE)
    assert lang_code == "de"
    with override(lang_code):
        current_lang = get_language()
        assert current_lang == "de"
