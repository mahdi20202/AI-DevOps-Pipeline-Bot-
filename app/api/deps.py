from fastapi import Cookie, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.services.auth_service import AuthService, AuthenticationError


def _extract_token(authorization: str | None, access_token: str | None) -> str:
    if authorization and authorization.lower().startswith('bearer '):
        return authorization.split(' ', 1)[1]
    if access_token:
        return access_token
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Not authenticated')


def get_current_user_email(
    db: Session = Depends(get_db),
    authorization: str | None = Header(default=None),
    access_token: str | None = Cookie(default=None),
) -> str:
    token = _extract_token(authorization, access_token)
    try:
        user = AuthService(db).get_user_from_access_token(token)
    except AuthenticationError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc
    return user.email
