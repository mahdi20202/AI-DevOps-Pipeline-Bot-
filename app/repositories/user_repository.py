from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.models.user import User


class UserRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_email(self, email: str) -> User | None:
        return self.db.query(User).filter(User.email == email).first()

    def create(self, *, email: str, hashed_password: str, full_name: str = 'User', role: str = 'viewer') -> User:
        user = User(email=email, hashed_password=hashed_password, full_name=full_name, role=role)
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    def record_failed_login(self, user: User, *, max_attempts: int, lockout_minutes: int) -> None:
        user.failed_login_attempts += 1
        if user.failed_login_attempts >= max_attempts:
            user.locked_until = datetime.now(UTC) + timedelta(minutes=lockout_minutes)
        self.db.add(user)
        self.db.commit()

    def reset_login_state(self, user: User) -> None:
        user.failed_login_attempts = 0
        user.locked_until = None
        user.last_login_at = datetime.now(UTC)
        self.db.add(user)
        self.db.commit()
