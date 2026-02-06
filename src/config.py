"""Local configuration for Gmail Inbox Helper."""

import json
import os
from pathlib import Path
from dotenv import load_dotenv


# Load .env from project root
PROJECT_ROOT = Path(__file__).parent.parent
load_dotenv(PROJECT_ROOT / '.env')


# Account definitions
ACCOUNTS = [
    {'name': 'conveyour', 'email': 'christianc@conveyour.com', 'token_file': 'conveyour.json'},
    {'name': 'chri5tian', 'email': 'hello@chri5tian.com', 'token_file': 'chri5tian.json'},
    {'name': 'campbell', 'email': 'campbellchristian36@gmail.com', 'token_file': 'campbell.json'},
]

# Feature toggles (read from .env, default to current GitHub Variable values)
ENABLE_MARKETING_CONVEYOUR = os.environ.get('ENABLE_MARKETING_CONVEYOUR', 'true').lower() == 'true'
ENABLE_MARKETING_CHRI5TIAN = os.environ.get('ENABLE_MARKETING_CHRI5TIAN', 'true').lower() == 'true'
ENABLE_MARKETING_CAMPBELL = os.environ.get('ENABLE_MARKETING_CAMPBELL', 'true').lower() == 'true'
ENABLE_JOBAPP_CONVEYOUR = os.environ.get('ENABLE_JOBAPP_CONVEYOUR', 'false').lower() == 'true'
ENABLE_JOBAPP_CHRI5TIAN = os.environ.get('ENABLE_JOBAPP_CHRI5TIAN', 'true').lower() == 'true'
ENABLE_JOBAPP_CAMPBELL = os.environ.get('ENABLE_JOBAPP_CAMPBELL', 'false').lower() == 'true'

# Processing limits
MAX_EMAILS_PER_PAGE = int(os.environ.get('MAX_EMAILS_PER_PAGE', '50'))
MAX_PAGES = int(os.environ.get('MAX_PAGES', '3'))

# Watcher interval in seconds (default: 6 hours)
CHECK_INTERVAL = int(os.environ.get('CHECK_INTERVAL', str(6 * 60 * 60)))

# Token directory
TOKENS_DIR = PROJECT_ROOT / 'tokens'


def get_feature_toggles():
    """Return dict of {account_name: {marketing: bool, jobapp: bool}}."""
    return {
        'conveyour': {
            'marketing': ENABLE_MARKETING_CONVEYOUR,
            'jobapp': ENABLE_JOBAPP_CONVEYOUR,
        },
        'chri5tian': {
            'marketing': ENABLE_MARKETING_CHRI5TIAN,
            'jobapp': ENABLE_JOBAPP_CHRI5TIAN,
        },
        'campbell': {
            'marketing': ENABLE_MARKETING_CAMPBELL,
            'jobapp': ENABLE_JOBAPP_CAMPBELL,
        },
    }


def load_token(account_name: str) -> str:
    """Load token JSON string from tokens/ directory.

    Returns the JSON string (same format GmailService expects).
    Raises FileNotFoundError if token file missing.
    """
    for account in ACCOUNTS:
        if account['name'] == account_name:
            token_path = TOKENS_DIR / account['token_file']
            if not token_path.exists():
                raise FileNotFoundError(
                    f"Token file not found: {token_path}\n"
                    f"Run: python scripts/generate_token.py\n"
                    f"Then save output to: {token_path}"
                )
            return token_path.read_text()

    raise ValueError(f"Unknown account: {account_name}")
