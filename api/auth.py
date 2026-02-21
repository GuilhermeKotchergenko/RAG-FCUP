"""
api/auth.py

Magic Link authentication logic:
  - POST /auth/send  → validates @fc.up.pt, generates JWT, sends (or simulates) email
  - GET  /auth/verify → validates JWT, creates DB user/session, sets cookie
"""

import hashlib
import os
from datetime import UTC, datetime, timedelta
from typing import Annotated

from dotenv import load_dotenv
from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, status
from jose import JWTError, jwt
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.db.models import MagicToken, User
from api.db.session import get_db

load_dotenv()

router = APIRouter(prefix="/auth", tags=["auth"])

SECRET_KEY = os.getenv("SECRET_KEY", "change-this-in-production")
ALGORITHM = "HS256"
TTL_MINUTES = int(os.getenv("MAGIC_LINK_TTL_MINUTES", "15"))
ALLOWED_DOMAIN = os.getenv("ALLOWED_EMAIL_DOMAIN", "fc.up.pt")
APP_URL = os.getenv("APP_URL", "http://localhost:8000")
SIMULATE_EMAIL = os.getenv("SIMULATE_EMAIL", "true").lower() == "true"


# ── Schemas ───────────────────────────────────────────────────────────────────


class SendRequest(BaseModel):
    email: EmailStr


class SendResponse(BaseModel):
    message: str
    # In simulation mode only, return the link directly
    magic_link: str | None = None


# ── Helpers ───────────────────────────────────────────────────────────────────


def _validate_domain(email: str) -> None:
    domain = email.split("@")[-1].lower()
    if domain != ALLOWED_DOMAIN:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Apenas e-mails @{ALLOWED_DOMAIN} são permitidos.",
        )


def _create_token(email: str) -> str:
    expire = datetime.now(UTC) + timedelta(minutes=TTL_MINUTES)
    payload = {"sub": email, "exp": expire, "type": "magic_link"}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


async def _send_or_simulate(email: str, link: str) -> None:
    if SIMULATE_EMAIL:
        print("\n" + "=" * 60)
        print(f"[Magic Link SIMULADO] Para: {email}")
        print(f"Link: {link}")
        print("=" * 60 + "\n")
        return

    import aiosmtplib
    from email.message import EmailMessage

    msg = EmailMessage()
    msg["From"] = os.getenv("EMAIL_FROM", "noreply@fc.up.pt")
    msg["To"] = email
    msg["Subject"] = "O teu link de acesso ao Assistente FCUP"
    msg.set_content(
        f"Olá!\n\nClica no link abaixo para acederes ao Assistente FCUP "
        f"(válido por {TTL_MINUTES} minutos):\n\n{link}\n\n"
        "Se não pediste este acesso, ignora este email."
    )

    await aiosmtplib.send(
        msg,
        hostname=os.getenv("SMTP_HOST"),
        port=int(os.getenv("SMTP_PORT", "587")),
        username=os.getenv("SMTP_USER"),
        password=os.getenv("SMTP_PASSWORD"),
        start_tls=True,
    )


# ── Routes ────────────────────────────────────────────────────────────────────


@router.post("/send", response_model=SendResponse)
async def send_magic_link(
    body: SendRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> SendResponse:
    """Generate and (simulate) send a Magic Link to the given @fc.up.pt email."""
    _validate_domain(body.email)

    token = _create_token(body.email)
    token_hash = _hash_token(token)
    expires_at = datetime.now(UTC) + timedelta(minutes=TTL_MINUTES)

    db.add(
        MagicToken(
            token_hash=token_hash,
            email=body.email,
            expires_at=expires_at,
        )
    )
    await db.commit()

    link = f"{APP_URL}/api/auth/verify?token={token}"
    await _send_or_simulate(body.email, link)

    return SendResponse(
        message="Link de acesso enviado! Verifica o teu email.",
        magic_link=link if SIMULATE_EMAIL else None,
    )


@router.get("/verify")
async def verify_magic_link(
    token: str,
    response: Response,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Validate a Magic Link token, create the user session, and set a session cookie."""
    # 1. Decode JWT
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload["sub"]
        if payload.get("type") != "magic_link":
            raise JWTError("wrong type")
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token inválido ou expirado.")

    _validate_domain(email)

    # 2. Check DB token (one-time use)
    token_hash = _hash_token(token)
    result = await db.execute(select(MagicToken).where(MagicToken.token_hash == token_hash))
    db_token = result.scalar_one_or_none()

    if db_token is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token não encontrado.")
    if db_token.used:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token já utilizado.")
    if datetime.now(UTC) > db_token.expires_at:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expirado.")

    # 3. Mark token as used
    db_token.used = True

    # 4. Upsert user
    result = await db.execute(select(User).where(User.email == email))
    if result.scalar_one_or_none() is None:
        db.add(User(email=email))
    await db.commit()

    # 5. Issue session cookie (simple signed JWT for now)
    session_token = jwt.encode(
        {"sub": email, "type": "session"},
        SECRET_KEY,
        algorithm=ALGORITHM,
    )
    response.set_cookie(
        key="fcup_session",
        value=session_token,
        httponly=True,
        samesite="lax",
        max_age=86400 * 7,  # 7 days
    )

    return {"message": f"Autenticado com sucesso! Bem-vindo, {email}.", "email": email}


@router.get("/me")
async def get_me(fcup_session: Annotated[str | None, Cookie()] = None) -> dict:
    """Return the current user from the session cookie."""
    if not fcup_session:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Não autenticado.")
    try:
        payload = jwt.decode(fcup_session, SECRET_KEY, algorithms=[ALGORITHM])
        return {"email": payload["sub"]}
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Sessão inválida.")


@router.post("/logout")
async def logout(response: Response) -> dict:
    response.delete_cookie("fcup_session")
    return {"message": "Sessão terminada."}
