"""Password hashing plus the admin CLI for creating accounts.

Threadline has no self-serve signup — an admin creates each teammate's
account ahead of time.

Usage:
    python -m app.auth teammate@example.com "Teammate Name"
"""

import argparse
import getpass
import sys

import bcrypt

from app import db


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode(), password_hash.encode())


def _main() -> None:
    parser = argparse.ArgumentParser(description="Create a Threadline account.")
    parser.add_argument("email")
    parser.add_argument("name")
    args = parser.parse_args()

    db.init_db()
    if db.get_user_by_email(args.email) is not None:
        sys.exit(f"A user with email '{args.email}' already exists.")

    password = getpass.getpass("Password: ")
    confirm = getpass.getpass("Confirm password: ")
    if password != confirm:
        sys.exit("Passwords didn't match.")
    if not password:
        sys.exit("Password is required.")

    user = db.create_user(args.email, hash_password(password), args.name)
    print(f"Created user {user['name']} <{user['email']}> ({user['id']})")


if __name__ == "__main__":
    _main()
