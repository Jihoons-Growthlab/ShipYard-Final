"""비밀번호(Argon2id), JWT(HS256), TOTP(RFC 6238)."""
import base64
import hashlib
import hmac
import struct
import time
import uuid

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

from . import config

_ph = PasswordHasher()  # argon2id


def hash_password(pw: str) -> str:
    return _ph.hash(pw)


def verify_password(hashed: str, pw: str) -> bool:
    try:
        return _ph.verify(hashed, pw)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def create_token(sub: str, stage: str, ttl: int, lid: int | None = None) -> str:
    now = int(time.time())
    payload = {"sub": sub, "stage": stage, "iat": now, "exp": now + ttl, "jti": uuid.uuid4().hex}
    if lid is not None:
        payload["lid"] = lid
    return jwt.encode(payload, config.app_secret(), algorithm="HS256")


def decode_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, config.app_secret(), algorithms=["HS256"], options={"require": ["sub", "exp", "jti"]})
    except jwt.PyJWTError:
        return None


STEP = 30


def current_step(now: float | None = None) -> int:
    return int((time.time() if now is None else now) // STEP)


def totp_at(secret: str, step: int) -> str:
    s = secret.strip().replace(" ", "").upper()
    key = base64.b32decode(s + "=" * (-len(s) % 8))
    h = hmac.new(key, struct.pack(">Q", step), hashlib.sha1).digest()
    o = h[-1] & 0x0F
    code = (struct.unpack(">I", h[o:o + 4])[0] & 0x7FFFFFFF) % 1_000_000
    return f"{code:06d}"


def match_totp(secret: str, code: str, now: float | None = None) -> int | None:
    """±1 step 안에서 맞는 step을 돌려준다."""
    if not (isinstance(code, str) and len(code) == 6 and code.isdigit()):
        return None
    cur = current_step(now)
    for step in (cur - 1, cur, cur + 1):
        if hmac.compare_digest(totp_at(secret, step), code):
            return step
    return None
