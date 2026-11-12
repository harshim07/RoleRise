from datetime import datetime, timedelta, timezone
import os
import jwt
from pwdlib import PasswordHash

password_hash = PasswordHash.recommended()
ALGORITHM = "HS256"

def create_access_token(user_id: int, token_version: int = 0):
    secret = os.getenv("JWT_SECRET", "")
    if len(secret) < 32:
        raise RuntimeError("JWT_SECRET must be set to at least 32 characters")
    return jwt.encode({"sub": str(user_id), "ver": token_version, "exp": datetime.now(timezone.utc) + timedelta(hours=12)}, secret, algorithm=ALGORITHM)

def decode_access_token(token: str):
    secret = os.getenv("JWT_SECRET", "")
    if len(secret) < 32:
        raise RuntimeError("JWT_SECRET must be set to at least 32 characters")
    return jwt.decode(token, secret, algorithms=[ALGORITHM])
