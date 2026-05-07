"""Local configuration for Gmail Inbox Helper."""

import os
from pathlib import Path
from dotenv import load_dotenv


# Load .env from project root
PROJECT_ROOT = Path(__file__).parent.parent
load_dotenv(PROJECT_ROOT / '.env')

# Token directory
TOKENS_DIR = PROJECT_ROOT / 'tokens'

# Processing limits
MAX_EMAILS_PER_PAGE = int(os.environ.get('MAX_EMAILS_PER_PAGE', '50'))
MAX_PAGES = int(os.environ.get('MAX_PAGES', '3'))

# Watcher interval in seconds (default: 6 hours)
CHECK_INTERVAL = int(os.environ.get('CHECK_INTERVAL', str(6 * 60 * 60)))


def _load_accounts():
    """Discover accounts from ACCOUNT_N_* environment variables."""
    accounts = []
    n = 1
    while True:
        name = os.environ.get(f'ACCOUNT_{n}_NAME')
        if not name:
            break
        accounts.append({
            'name': name,
            'email': os.environ.get(f'ACCOUNT_{n}_EMAIL', ''),
            'token_file': f'{n}.json',
            'marketing': os.environ.get(f'ACCOUNT_{n}_MARKETING', 'true').lower() == 'true',
            'jobapp': os.environ.get(f'ACCOUNT_{n}_JOBAPP', 'false').lower() == 'true',
            'general': os.environ.get(f'ACCOUNT_{n}_GENERAL', 'false').lower() == 'true',
        })
        n += 1
    return accounts


ACCOUNTS = _load_accounts()


def get_feature_toggles():
    """Return dict of {account_name: {marketing: bool, jobapp: bool}}."""
    return {
        account['name']: {
            'marketing': account['marketing'],
            'jobapp': account['jobapp'],
            'general': account['general'],
        }
        for account in ACCOUNTS
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
