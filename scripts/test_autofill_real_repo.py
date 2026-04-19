from __future__ import annotations

import argparse
import asyncio
import json
import os
from pathlib import Path
import sys
from typing import Any

import httpx


def _ensure_backend_root_on_path() -> None:
    backend_root = Path(__file__).resolve().parent.parent
    backend_root_str = str(backend_root)
    if backend_root_str not in sys.path:
        sys.path.insert(0, backend_root_str)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Test Career Engine project autofill against a real GitHub repository."
    )
    parser.add_argument(
        "--repo-url",
        required=True,
        help="GitHub repository URL, for example: https://github.com/fastapi/fastapi",
    )
    parser.add_argument(
        "--mode",
        choices=["api", "service"],
        default="api",
        help="api: call running backend endpoint; service: call service function directly",
    )
    parser.add_argument(
        "--base-url",
        default="http://localhost:8000",
        help="Backend base URL when mode=api",
    )
    parser.add_argument(
        "--session-cookie",
        default=os.getenv("CE_SESSION", ""),
        help="Session cookie value for authenticated endpoint calls (or set CE_SESSION env var)",
    )
    parser.add_argument(
        "--cookie-name",
        default=os.getenv("SESSION_COOKIE_NAME", "ce_session"),
        help="Session cookie name used by the backend",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=90.0,
        help="Request timeout in seconds",
    )
    return parser.parse_args()


def _print_json(payload: Any) -> None:
    print(json.dumps(payload, indent=2, ensure_ascii=True))


def _run_api_mode(args: argparse.Namespace) -> int:
    if not args.session_cookie:
        print(
            "Missing session cookie. Pass --session-cookie or set CE_SESSION in your shell.",
            file=sys.stderr,
        )
        return 2

    base_url = args.base_url.rstrip("/")
    endpoint = f"{base_url}/api/v1/projects/autofill"
    cookies = {args.cookie_name: args.session_cookie}

    try:
        with httpx.Client(timeout=args.timeout, cookies=cookies) as client:
            response = client.post(endpoint, json={"github_url": args.repo_url})
    except httpx.RequestError as exc:
        print(f"Request error: {exc}", file=sys.stderr)
        return 2

    print(f"Status: {response.status_code}")
    try:
        payload = response.json()
    except ValueError:
        print(response.text)
        return 1 if response.status_code >= 400 else 0

    _print_json(payload)
    return 1 if response.status_code >= 400 else 0


async def _run_service_mode(args: argparse.Namespace) -> int:
    _ensure_backend_root_on_path()

    from app.core.config import get_settings
    from app.services.project_autofill import autofill_project_from_github

    settings = get_settings()

    try:
        payload = await autofill_project_from_github(args.repo_url, settings)
    except Exception as exc:  # noqa: BLE001
        print(f"Service error: {exc}", file=sys.stderr)
        return 2

    _print_json(payload)
    return 0


def main() -> int:
    args = _parse_args()

    if args.mode == "api":
        return _run_api_mode(args)

    return asyncio.run(_run_service_mode(args))


if __name__ == "__main__":
    raise SystemExit(main())
