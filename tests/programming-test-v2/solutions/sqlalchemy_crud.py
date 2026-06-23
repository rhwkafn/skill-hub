"""
SQLAlchemy CRUD Module

Complete Create / Read / Update / Delete operations using SQLAlchemy 2.0
ORM style.  Includes a User model, session management, and full CRUD API.
"""

from __future__ import annotations

import os
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Generator, Optional

from sqlalchemy import (
    Column,
    DateTime,
    Integer,
    String,
    create_engine,
    select,
    update,
    delete,
)
from sqlalchemy.orm import Session, DeclarativeBase, sessionmaker

# ---------------------------------------------------------------------------
# Engine & Session setup
# ---------------------------------------------------------------------------

DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///app.db")

engine = create_engine(DATABASE_URL, echo=False, future=True)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False, future=True)


# ---------------------------------------------------------------------------
# Base model
# ---------------------------------------------------------------------------

class Base(DeclarativeBase):
    """Declarative base for all ORM models."""
    pass


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class User(Base):
    __tablename__ = "users"

    id: int = Column(Integer, primary_key=True, autoincrement=True)
    username: str = Column(String(80), unique=True, nullable=False, index=True)
    email: str = Column(String(120), unique=True, nullable=False, index=True)
    created_at: datetime = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    def __repr__(self) -> str:
        return f"<User id={self.id} username={self.username!r}>"

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "username": self.username,
            "email": self.email,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


# ---------------------------------------------------------------------------
# Session helper
# ---------------------------------------------------------------------------

def init_db() -> None:
    """Create all tables (idempotent)."""
    Base.metadata.create_all(engine)


@contextmanager
def get_session() -> Generator[Session, None, None]:
    """Context manager that yields a session and handles commit / rollback."""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


# ---------------------------------------------------------------------------
# CREATE
# ---------------------------------------------------------------------------

def create_user(username: str, email: str) -> User:
    """
    Create a new user.

    Args:
        username: Unique username.
        email: Unique email address.

    Returns:
        The newly created User instance.

    Raises:
        IntegrityError: If username or email already exists.
    """
    with get_session() as session:
        user = User(username=username, email=email)
        session.add(user)
        session.flush()       # populate user.id before commit
        session.refresh(user)  # ensure all server defaults are loaded
        return user


def create_users_batch(users_data: list[dict[str, str]]) -> list[User]:
    """
    Bulk-create users.

    Args:
        users_data: List of dicts with 'username' and 'email' keys.

    Returns:
        List of created User instances.
    """
    with get_session() as session:
        users = [User(**data) for data in users_data]
        session.add_all(users)
        session.flush()
        for u in users:
            session.refresh(u)
        return users


# ---------------------------------------------------------------------------
# READ
# ---------------------------------------------------------------------------

def get_user_by_id(user_id: int) -> Optional[User]:
    """Fetch a single user by primary key."""
    with get_session() as session:
        return session.get(User, user_id)


def get_user_by_username(username: str) -> Optional[User]:
    """Fetch a single user by username."""
    with get_session() as session:
        stmt = select(User).where(User.username == username)
        return session.execute(stmt).scalar_one_or_none()


def get_user_by_email(email: str) -> Optional[User]:
    """Fetch a single user by email."""
    with get_session() as session:
        stmt = select(User).where(User.email == email)
        return session.execute(stmt).scalar_one_or_none()


def list_users(
    offset: int = 0,
    limit: int = 100,
    order_by: str = "id",
) -> list[User]:
    """
    List users with pagination.

    Args:
        offset: Number of records to skip.
        limit: Max records to return.
        order_by: Column name to sort by (default 'id').

    Returns:
        List of User instances.
    """
    with get_session() as session:
        col = getattr(User, order_by, User.id)
        stmt = select(User).order_by(col).offset(offset).limit(limit)
        return list(session.execute(stmt).scalars().all())


def count_users() -> int:
    """Return total number of users."""
    from sqlalchemy import func

    with get_session() as session:
        stmt = select(func.count()).select_from(User)
        return session.execute(stmt).scalar_one()


# ---------------------------------------------------------------------------
# UPDATE
# ---------------------------------------------------------------------------

def update_user(user_id: int, **kwargs: Any) -> Optional[User]:
    """
    Update a user's fields.

    Args:
        user_id: Primary key of the user to update.
        **kwargs: Fields to update (e.g., username='new_name', email='a@b.com').

    Returns:
        Updated User instance, or None if not found.
    """
    allowed = {"username", "email"}
    filtered = {k: v for k, v in kwargs.items() if k in allowed}
    if not filtered:
        raise ValueError("No valid fields to update (allowed: username, email)")

    with get_session() as session:
        stmt = update(User).where(User.id == user_id).values(**filtered)
        result = session.execute(stmt)
        if result.rowcount == 0:
            return None
        session.flush()
        return session.get(User, user_id)


def update_user_by_username(username: str, **kwargs: Any) -> Optional[User]:
    """Update a user found by username."""
    allowed = {"username", "email"}
    filtered = {k: v for k, v in kwargs.items() if k in allowed}
    if not filtered:
        raise ValueError("No valid fields to update")

    with get_session() as session:
        stmt = update(User).where(User.username == username).values(**filtered)
        result = session.execute(stmt)
        if result.rowcount == 0:
            return None
        session.flush()
        return session.execute(
            select(User).where(User.username == filtered.get("username", username))
        ).scalar_one_or_none()


# ---------------------------------------------------------------------------
# DELETE
# ---------------------------------------------------------------------------

def delete_user(user_id: int) -> bool:
    """
    Delete a user by ID.

    Args:
        user_id: Primary key.

    Returns:
        True if a row was deleted, False if not found.
    """
    with get_session() as session:
        stmt = delete(User).where(User.id == user_id)
        result = session.execute(stmt)
        return result.rowcount > 0


def delete_user_by_username(username: str) -> bool:
    """Delete a user by username."""
    with get_session() as session:
        stmt = delete(User).where(User.username == username)
        result = session.execute(stmt)
        return result.rowcount > 0


def delete_all_users() -> int:
    """
    Delete all users.

    Returns:
        Number of rows deleted.
    """
    with get_session() as session:
        result = session.execute(delete(User))
        return result.rowcount


# ---------------------------------------------------------------------------
# Demo / self-test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("=== SQLAlchemy CRUD Demo ===\n")

    # Use an in-memory database for the demo
    engine = create_engine("sqlite:///:memory:", echo=False, future=True)
    SessionLocal.configure(bind=engine)
    init_db()

    # CREATE
    alice = create_user("alice", "alice@example.com")
    print(f"Created: {alice}")
    bob = create_user("bob", "bob@example.com")
    print(f"Created: {bob}")

    # READ
    found = get_user_by_username("alice")
    print(f"Found by username: {found}, as dict: {found.to_dict()}")

    by_id = get_user_by_id(bob.id)
    print(f"Found by id: {by_id}")

    all_users = list_users()
    print(f"All users: {all_users}")
    print(f"Total count: {count_users()}")

    # UPDATE
    updated = update_user(alice.id, email="alice_new@example.com")
    print(f"Updated alice email: {updated.to_dict()}")

    # DELETE
    deleted = delete_user(bob.id)
    print(f"Deleted bob: {deleted}")
    print(f"Users remaining: {count_users()}")

    # Batch create
    batch = create_users_batch([
        {"username": "charlie", "email": "charlie@example.com"},
        {"username": "diana", "email": "diana@example.com"},
    ])
    print(f"Batch created: {batch}")
    print(f"Final count: {count_users()}")

    print("\nAll checks passed!")
