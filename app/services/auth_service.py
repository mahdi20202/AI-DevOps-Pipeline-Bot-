from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import create_access_token, create_refresh_token, decode_token, hash_password, verify_password
from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.schemas.auth import UserProfile


class AuthenticationError(Exception):
    pass


class AuthService:
    def __init__(self, db: Session):
        self.db = db
        self.users = UserRepository(db)
        self.settings = get_settings()

    def ensure_admin_user(self, email: str, password: str, full_name: str) -> None:
        if not self.users.get_by_email(email):
            self.users.create(email=email, hashed_password=hash_password(password), full_name=full_name, role='admin')

    def authenticate_user(self, email: str, password: str) -> tuple[str, str, UserProfile]:
        user = self.users.get_by_email(email)
        if not user:
            raise AuthenticationError('Invalid email or password')
        if user.locked_until and user.locked_until > datetime.now(UTC):
            raise AuthenticationError('Account temporarily locked due to repeated failed attempts')
        if not user.is_active:
            raise AuthenticationError('Account is inactive')
        if not verify_password(password, user.hashed_password):
            self.users.record_failed_login(
                user,
                max_attempts=self.settings.max_failed_logins,
                lockout_minutes=self.settings.lockout_minutes,
            )
            raise AuthenticationError('Invalid email or password')
        self.users.reset_login_state(user)
        return create_access_token(user.email), create_refresh_token(user.email), self.to_profile(user)

    def refresh_access_token(self, refresh_token: str) -> str:
        payload = decode_token(refresh_token, expected_type='refresh')
        subject = payload.get('sub')
        user = self.users.get_by_email(subject or '')
        if not user or not user.is_active:
            raise AuthenticationError('Unable to refresh session')
        return create_access_token(user.email)

    def get_user_from_access_token(self, access_token: str) -> User:
        payload = decode_token(access_token, expected_type='access')
        subject = payload.get('sub')
        user = self.users.get_by_email(subject or '')
        if not user or not user.is_active:
            raise AuthenticationError('Invalid session')
        return user

    @staticmethod
    def to_profile(user: User) -> UserProfile:
        return UserProfile(email=user.email, full_name=user.full_name, role=user.role, is_active=user.is_active)
