"""
tools/google_auth.py — Google OAuth2 credential management.
Handles initial browser auth flow and automatic token refresh.

Setup (one-time):
  1. Google Cloud Console → New project → Enable Gmail API + Google Calendar API
  2. Credentials → Create OAuth 2.0 Client ID → Desktop app type
  3. Download → save as credentials.json at GOOGLE_CREDENTIALS_PATH
  4. CRITICAL: OAuth consent screen → Publish app → "In Production" mode
     Testing mode tokens expire every 7 days and require manual re-auth.
  5. First run opens a browser window. Authorize → token.json saved automatically.
     All subsequent runs load from token.json with silent refresh.
"""

from pathlib import Path

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build


SCOPES = [
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/calendar",
]


def get_credentials(credentials_path: Path, token_path: Path) -> Credentials:
    """Load or refresh OAuth2 credentials. Triggers browser flow on first use."""
    creds = None

    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not credentials_path.exists():
                raise FileNotFoundError(
                    f"Google credentials.json not found at {credentials_path}.\n"
                    "  → Go to Google Cloud Console → Credentials → Create OAuth 2.0 Client ID\n"
                    "  → Download and save as credentials.json at that path."
                )
            flow = InstalledAppFlow.from_client_secrets_file(str(credentials_path), SCOPES)
            creds = flow.run_local_server(port=0)

        token_path.write_text(creds.to_json())

    return creds


def build_gmail(credentials_path: Path, token_path: Path):
    """Return authenticated Gmail service. Sync — use asyncio.to_thread() from async contexts."""
    creds = get_credentials(credentials_path, token_path)
    return build("gmail", "v1", credentials=creds, cache_discovery=False)


def build_calendar(credentials_path: Path, token_path: Path):
    """Return authenticated Calendar service. Sync — use asyncio.to_thread() from async contexts."""
    creds = get_credentials(credentials_path, token_path)
    return build("calendar", "v3", credentials=creds, cache_discovery=False)


def google_configured(credentials_path: Path) -> bool:
    """Quick check — returns False if credentials.json is missing."""
    return credentials_path.exists()


if __name__ == "__main__":
    import sys
    from pathlib import Path

    # Paths match what config.py expects
    creds_path = Path(__file__).parent.parent / "credentials.json"
    token_path = Path(__file__).parent.parent / "token.json"

    if not creds_path.exists():
        print(f"\nERROR: credentials.json not found at {creds_path}")
        print("\nTo get it:")
        print("  1. Go to https://console.cloud.google.com/")
        print("  2. Create a project (or select existing)")
        print("  3. Enable Gmail API + Google Calendar API")
        print("  4. Credentials → Create OAuth 2.0 Client ID → Desktop app")
        print("  5. Download JSON → rename to credentials.json")
        print(f"  6. Move it to: {creds_path}")
        sys.exit(1)

    print(f"Found credentials.json. Opening browser for authorization...")
    print("(A browser window will open — log in with your Google account)\n")

    try:
        creds = get_credentials(creds_path, token_path)
        print(f"\nAuthorization successful.")
        print(f"token.json saved to: {token_path}")
        print("\nTAMARA (Gmail) and HELEN (Calendar) are now active.")
        print("Restart BOWEN to apply.\n")
    except Exception as e:
        print(f"\nAuth failed: {e}")
        sys.exit(1)
