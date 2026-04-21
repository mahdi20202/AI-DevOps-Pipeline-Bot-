from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db
from app.schemas.auth import LoginResponse, RefreshResponse, UserProfile
from app.services.auth_service import AuthService, AuthenticationError

router = APIRouter()
settings = get_settings()


def _set_auth_cookies(response: Response, *, access_token: str, refresh_token: str) -> None:
    common = {
        'httponly': True,
        'secure': settings.cookie_secure,
        'samesite': 'lax',
        'domain': settings.cookie_domain,
        'path': '/',
    }
    response.set_cookie('access_token', access_token, max_age=settings.access_token_expire_minutes * 60, **common)
    response.set_cookie('refresh_token', refresh_token, max_age=settings.refresh_token_expire_minutes * 60, **common)


@router.post('/login', response_model=LoginResponse)
def login(response: Response, form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    auth_service = AuthService(db)
    try:
        access_token, refresh_token, profile = auth_service.authenticate_user(form_data.username, form_data.password)
    except AuthenticationError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc
    _set_auth_cookies(response, access_token=access_token, refresh_token=refresh_token)
    return LoginResponse(access_token=access_token, user=profile)


@router.post('/refresh', response_model=RefreshResponse)
def refresh_session(response: Response, db: Session = Depends(get_db), refresh_token: str | None = Cookie(default=None)):
    if not refresh_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Refresh token missing')
    try:
        access_token = AuthService(db).refresh_access_token(refresh_token)
    except AuthenticationError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc
    response.set_cookie(
        'access_token', access_token, max_age=settings.access_token_expire_minutes * 60,
        httponly=True, secure=settings.cookie_secure, samesite='lax', domain=settings.cookie_domain, path='/'
    )
    return RefreshResponse(access_token=access_token)


@router.get('/me', response_model=UserProfile)
def me(access_token: str | None = Cookie(default=None), db: Session = Depends(get_db)):
    if not access_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Session missing')
    try:
        user = AuthService(db).get_user_from_access_token(access_token)
    except AuthenticationError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc
    return AuthService.to_profile(user)


@router.post('/logout')
def logout(response: Response):
    response.delete_cookie('access_token', path='/', domain=settings.cookie_domain)
    response.delete_cookie('refresh_token', path='/', domain=settings.cookie_domain)
    return {'message': 'Logged out'}
