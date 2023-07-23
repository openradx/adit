from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password


def hash_token(token_string: str) -> str:
    return make_password(token_string, settings.TOKEN_AUTHENTICATION_SALT)


def verify_token(token_string: str, token_hashed: str) -> bool:
    return check_password(token_string, token_hashed)
