"""
Run this script once to generate fresh Gmail OAuth tokens and save them to your .env file.

Usage:
    python generate_gmail_tokens.py

It will open a browser window asking you to log in with Google and grant Gmail access.
On success, it writes GMAIL_TOKEN and GMAIL_REFRESH_TOKEN into your .env file.
"""

import os
import re
from pathlib import Path
from google_auth_oauthlib.flow import InstalledAppFlow
from dotenv import load_dotenv

# Gmail send scope
SCOPES = ["https://www.googleapis.com/auth/gmail.send"]

ENV_FILE = Path(__file__).parent / ".env"


def update_env(key: str, value: str):
    """Insert or update a key=value line in the .env file."""
    content = ENV_FILE.read_text() if ENV_FILE.exists() else ""
    pattern = re.compile(rf"^{re.escape(key)}=.*$", re.MULTILINE)
    new_line = f"{key}={value}"
    if pattern.search(content):
        content = pattern.sub(new_line, content)
    else:
        content = content.rstrip("\n") + f"\n{new_line}\n"
    ENV_FILE.write_text(content)
    print(f"  ✓ {key} updated in .env")


def main():
    load_dotenv(ENV_FILE)

    client_id = os.environ.get("GMAIL_CLIENT_ID")
    client_secret = os.environ.get("GMAIL_CLIENT_SECRET")

    if not client_id or not client_secret:
        print("ERROR: GMAIL_CLIENT_ID and GMAIL_CLIENT_SECRET must be set in your .env file first.")
        print("Get these from Google Cloud Console → APIs & Services → Credentials → your OAuth 2.0 Client ID.")
        return

    # Build the client config dict (same format as a downloaded credentials JSON)
    client_config = {
        "installed": {
            "client_id": client_id,
            "client_secret": client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": ["urn:ietf:wg:oauth:2.0:oob", "http://localhost"],
        }
    }

    print("\n=== Gmail OAuth Token Generator ===")
    print("A browser window will open. Log in with the Gmail account you want to send from.")
    print("After granting access, come back here.\n")

    flow = InstalledAppFlow.from_client_config(client_config, scopes=SCOPES)
    creds = flow.run_local_server(port=0, prompt="consent", access_type="offline")

    print("\nTokens received. Saving to .env ...\n")
    update_env("GMAIL_TOKEN", creds.token)
    update_env("GMAIL_REFRESH_TOKEN", creds.refresh_token)

    print("\nDone! Your .env file now has fresh Gmail tokens.")
    print("Restart your backend server and try sending the email again.")


if __name__ == "__main__":
    main()
