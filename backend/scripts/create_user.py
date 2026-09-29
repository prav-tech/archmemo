"""
Create a login account, or change an existing account's password.

Usage (from backend/):
    python scripts/create_user.py alice               # prompts for a password
    python scripts/create_user.py alice --update      # change alice's password

The first admin can also be created automatically at startup via ADMIN_USERNAME /
ADMIN_PASSWORD (see .env.example). Use this script for everyone after that.
"""

from __future__ import annotations

import argparse
import asyncio
import getpass
import sys
from pathlib import Path

# Add backend root to path so app imports work
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlmodel import SQLModel  # noqa: E402

from app.auth.service import create_user, set_password  # noqa: E402
from app.db import get_engine, session_scope  # noqa: E402
from app.models import user  # noqa: E402,F401  (registers the users table)


async def run(username: str, password: str, update: bool) -> None:
    async with get_engine().begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    async with session_scope() as session:
        if update:
            account = await set_password(session, username, password)
            print(f"Updated the password for {account.username!r}.")
        else:
            account = await create_user(session, username, password)
            print(f"Created user {account.username!r}.")


def main() -> int:
    parser = argparse.ArgumentParser(description="Create or update an ArchMemory login account")
    parser.add_argument("username")
    parser.add_argument("--update", action="store_true", help="change the password of an existing user")
    args = parser.parse_args()

    password = getpass.getpass("Password: ")
    if password != getpass.getpass("Repeat password: "):
        print("Passwords do not match.", file=sys.stderr)
        return 1
    try:
        asyncio.run(run(args.username, password, args.update))
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
