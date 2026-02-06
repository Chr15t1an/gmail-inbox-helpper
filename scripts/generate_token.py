#!/usr/bin/env python3
"""
One-time OAuth token generation for Gmail accounts.
Run this locally for each account, then save the output to tokens/N.json.

Usage:
    python scripts/generate_token.py

Prerequisites:
    1. Create a Google Cloud project
    2. Enable Gmail API
    3. Create OAuth 2.0 credentials (Desktop app)
    4. Download credentials.json to this directory
"""

import json
import os
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ['https://www.googleapis.com/auth/gmail.modify']

def main():
    # Check for credentials file
    creds_file = os.path.join(os.path.dirname(__file__), 'credentials.json')
    if not os.path.exists(creds_file):
        print("ERROR: credentials.json not found!")
        print("Download it from Google Cloud Console -> APIs & Services -> Credentials")
        return

    print("Starting OAuth flow...")
    print("A browser window will open. Sign in with the Gmail account you want to connect.")
    print()

    flow = InstalledAppFlow.from_client_secrets_file(creds_file, SCOPES)
    creds = flow.run_local_server(port=0)

    token_data = {
        'token': creds.token,
        'refresh_token': creds.refresh_token,
        'token_uri': creds.token_uri,
        'client_id': creds.client_id,
        'client_secret': creds.client_secret,
        'scopes': list(creds.scopes),
    }

    print("\n" + "=" * 60)
    print("SUCCESS! Save the following JSON to tokens/N.json")
    print("(where N matches the account number in your .env)")
    print("=" * 60)
    print()
    print(json.dumps(token_data, indent=2))
    print()
    print("=" * 60)
    print("Example: tokens/1.json, tokens/2.json, etc.")
    print("See TOKEN-REFRESH-RUNBOOK.md for details.")
    print("=" * 60)

if __name__ == '__main__':
    main()
