"""Gets the refresh token that lets the server send email as one Gmail account.

Run once, on your own computer, from backend/:

    uv run python -m backend.scripts.gmail_sender_token

It opens Google's sign-in page. Sign in as the account emails should come
from and allow "Send email on your behalf". The token is printed here; put it
in GMAIL_SENDER_REFRESH_TOKEN wherever the API runs. Nothing is saved.

Needs GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET (in .env.local). It borrows
the local "Connect Gmail" redirect URI, which that client already lists, so the
local API must not be running on port 8000 meanwhile.
"""

import secrets
import sys
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlencode, urlparse

import httpx

from backend.core.config import get_settings
from backend.core.email import GOOGLE_TOKEN_URL

PORT = 8000
REDIRECT_URI = f"http://localhost:{PORT}/api/v1/inbox/gmail/callback"
SCOPE = "https://www.googleapis.com/auth/gmail.send"


def _wait_for_code(state: str) -> str:
    """Serves one request: the browser coming back from Google with a code."""
    found: dict[str, str] = {}

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802 (the name http.server calls)
            query = parse_qs(urlparse(self.path).query)
            ok = query.get("state", [""])[0] == state and "code" in query
            if ok:
                found["code"] = query["code"][0]
            self.send_response(200 if ok else 400)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(
                b"Done. You can close this tab and go back to the terminal."
                if ok
                else b"Sign-in did not finish. Run the command again."
            )

        def log_message(self, *_: object) -> None:
            return

    with HTTPServer(("localhost", PORT), Handler) as server:
        server.handle_request()
    if "code" not in found:
        sys.exit("Google did not send a sign-in code back. Run the command again.")
    return found["code"]


def main() -> None:
    settings = get_settings()
    if not settings.google_client_id or not settings.google_client_secret:
        sys.exit("Set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET in .env.local first.")

    state = secrets.token_urlsafe(16)
    url = "https://accounts.google.com/o/oauth2/v2/auth?" + urlencode(
        {
            "client_id": settings.google_client_id,
            "redirect_uri": REDIRECT_URI,
            "response_type": "code",
            "scope": SCOPE,
            # "offline" + "consent" make Google hand out a refresh token every time.
            "access_type": "offline",
            "prompt": "consent",
            "state": state,
        }
    )
    print("Opening Google sign-in. If no browser opens, visit:\n\n" + url + "\n")
    webbrowser.open(url)
    code = _wait_for_code(state)

    response = httpx.post(
        GOOGLE_TOKEN_URL,
        data={
            "client_id": settings.google_client_id,
            "client_secret": settings.google_client_secret,
            "code": code,
            "redirect_uri": REDIRECT_URI,
            "grant_type": "authorization_code",
        },
        timeout=15,
    )
    if response.status_code != 200:
        sys.exit(f"Google refused the code: {response.text}")
    token = response.json().get("refresh_token")
    if not token:
        sys.exit("Google sent no refresh token. Run the command again.")
    print("Set this on Railway (and in .env.local to send from here):\n")
    print(f"GMAIL_SENDER_REFRESH_TOKEN={token}\n")


if __name__ == "__main__":
    main()
