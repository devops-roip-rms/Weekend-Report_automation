from __future__ import annotations

import argparse
import json
import os
from getpass import getpass
from pathlib import Path
from typing import Any

from app.auth import hash_password

PROJECT_ROOT = Path(__file__).resolve().parents[1]

DEFAULT_USERS_FILE = PROJECT_ROOT / "deploy" / "docker" / "secrets" / "local-users.json"


def _read_database(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {
            "users": {},
        }

    try:
        payload = json.loads(
            path.read_text(
                encoding="utf-8",
            )
        )
    except json.JSONDecodeError as exc:
        raise SystemExit(f"ERROR: {path} is not valid JSON: {exc}") from exc

    if not isinstance(payload, dict):
        raise SystemExit(f"ERROR: {path} must contain a JSON object")

    users = payload.get("users")

    if not isinstance(users, dict):
        raise SystemExit(f"ERROR: {path} must contain a 'users' object")

    return payload


def _write_database(
    path: Path,
    payload: dict[str, Any],
) -> None:
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    temporary = path.with_suffix(path.suffix + ".tmp")

    temporary.write_text(
        json.dumps(
            payload,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    os.replace(
        temporary,
        path,
    )

    try:
        os.chmod(
            path,
            0o600,
        )
    except OSError:
        # Windows ACLs do not map directly to POSIX chmod semantics.
        pass


def _validate_username(username: str) -> str:
    username = username.strip()

    if not username:
        raise SystemExit("ERROR: username must not be empty")

    if "," in username:
        raise SystemExit("ERROR: username must not contain a comma")

    if "\n" in username or "\r" in username:
        raise SystemExit("ERROR: username contains an invalid newline")

    return username


def add_user(
    path: Path,
    username: str,
) -> None:
    username = _validate_username(username)

    password = getpass(f"Password for {username}: ")

    if not password:
        raise SystemExit("ERROR: password must not be empty")

    confirmation = getpass("Confirm password: ")

    if password != confirmation:
        raise SystemExit("ERROR: passwords do not match")

    payload = _read_database(path)
    users = payload["users"]

    replacing = username in users

    users[username] = hash_password(password)

    _write_database(
        path,
        payload,
    )

    action = "updated" if replacing else "added"

    print(f"User {username!r} {action} in {path}")

    print("Make sure the same username is present in WEEKEND_REPORT_AUTHORIZED_REVIEWERS.")


def remove_user(
    path: Path,
    username: str,
) -> None:
    username = _validate_username(username)

    payload = _read_database(path)
    users = payload["users"]

    if username not in users:
        raise SystemExit(f"ERROR: user {username!r} does not exist")

    del users[username]

    _write_database(
        path,
        payload,
    )

    print(f"User {username!r} removed from {path}")


def list_users(path: Path) -> None:
    payload = _read_database(path)

    users = sorted(payload["users"].keys())

    if not users:
        print("No local users configured.")
        return

    for username in users:
        print(username)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Manage Weekend Report local-login users. "
            "Passwords are stored only as PBKDF2-SHA256 hashes."
        )
    )

    parser.add_argument(
        "--file",
        type=Path,
        default=DEFAULT_USERS_FILE,
        help=(f"Path to local-users.json (default: {DEFAULT_USERS_FILE})"),
    )

    subparsers = parser.add_subparsers(
        dest="command",
        required=True,
    )

    add_parser = subparsers.add_parser(
        "add",
        help="Add a user or replace its password",
    )

    add_parser.add_argument(
        "username",
    )

    remove_parser = subparsers.add_parser(
        "remove",
        help="Remove a local user",
    )

    remove_parser.add_argument(
        "username",
    )

    subparsers.add_parser(
        "list",
        help="List configured usernames",
    )

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    path = args.file.resolve()

    if args.command == "add":
        add_user(
            path,
            args.username,
        )
        return

    if args.command == "remove":
        remove_user(
            path,
            args.username,
        )
        return

    if args.command == "list":
        list_users(path)
        return

    parser.error(f"unsupported command: {args.command}")


if __name__ == "__main__":
    main()
