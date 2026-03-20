import os
from typing import Dict, Optional, Any
from datetime import datetime, timedelta, timezone
import jwt
import bcrypt

SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY: raise ValueError("SECRET_KEY env variable not set. Insecure, aborting.")

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 60))

#BYCRTPY SETUP
#pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def verify_password(plain_password: str,hashed_password: str)-> bool: # verification: compares password to hashed password
    """verifies plain text against hashed version using bcrypt"""
    password_bytes = plain_password.encode('utf-8')
    hash_bytes = hashed_password.encode('utf-8')
    return bcrypt.checkpw(password_bytes, hash_bytes)

def get_password_hash(password: str)->str:
    password_bytes = password.encode('utf-8')
    salt = bcrypt.gensalt()
    hashed_password = bcrypt.hashpw(password_bytes, salt)
    return hashed_password.decode('utf-8') 

#JWT MANAGEMENT

def create_access_token(user_id: str, username: str, role: str)->str: #creates standard JWT token
    now = datetime.now(timezone.utc)
    expire = now + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    payload={
        "sub": user_id,
        "username": username,
        "role": role,
        "iat": now,
        "exp": expire,
        "aud": "ball-api"

    }

    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

def decode_access_token(token:str)->Optional[Dict[str, Any]]:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=ALGORITHM, audience="ball-api")
        return {"valid": True, "payload": payload}
    except jwt.ExpiredSignatureError:
        return {"valid": False, "error": "token_expired"}
    except jwt.InvalidTokenError:
        return {"valid": False, "error": "token_invalid_or_forged"}




