"""Local development only (scripts/dev.sh start): makes sure the test
accounts exist, with the passwords dev.sh prints. Each run resets their
password and role so what dev.sh shows always works.

Usage: uv run python -m app.db.dev_users <admin_user> <admin_pw> <user> <user_pw>
"""

import asyncio
import sys

from sqlalchemy import select

from app.db.session import async_session_maker, init_db
from app.models.enums import UserRole
from app.models.user import User
from app.services.auth import hash_password, normalize_username


async def ensure(accounts: list[tuple[str, str, UserRole]]) -> None:
    await init_db()
    async with async_session_maker() as db:
        for name, password, role in accounts:
            username = normalize_username(name)
            user = (await db.execute(select(User).where(User.username == username))).scalar_one_or_none()
            if user is None:
                user = User(username=username, password_hash="")
            user.password_hash = hash_password(password)
            user.role = role
            user.is_active = True
            db.add(user)
        await db.commit()


if __name__ == "__main__":
    admin, admin_pw, plain, plain_pw = sys.argv[1:5]
    asyncio.run(ensure([(admin, admin_pw, UserRole.ADMIN), (plain, plain_pw, UserRole.USER)]))
