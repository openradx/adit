from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password


def hash_token(token_string: str) -> str:
    # We use a fixed salt to always generate the same hash for the same token string.
    # Rainbow attacks doesn't matter here as the token string itself is random.
    return make_password(token_string, settings.TOKEN_AUTHENTICATION_SALT)


def verify_token(token_string: str, token_hashed: str) -> bool:
    return check_password(token_string, token_hashed)
