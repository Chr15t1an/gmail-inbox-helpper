"""Rule-based email filters for obvious senders — no API calls needed."""

from typing import Dict, Optional, Tuple


def apply_rules(email: Dict, account_email: str) -> Optional[Tuple[str, str, str]]:
    """
    Try rule-based classification on an email.

    Args:
        email: Dict with 'from', 'subject', etc.
        account_email: The email address of the account being processed.

    Returns:
        Tuple of (classification, action, rule_name) or None if no rule matched.
        action is one of: 'label_and_archive', 'archive'
        classification is the category string to record.
    """
    from_addr = (email.get('from') or '').lower()
    subject = (email.get('subject') or '').lower()

    # Facebook Messenger notifications
    if '@facebookmail.com' in from_addr:
        return ('NOTIFICATION', 'label_and_archive', 'facebook_messenger')

    # GitHub notifications
    if 'noreply@github.com' in from_addr:
        return ('NOTIFICATION', 'label_and_archive_github', 'github_notification')

    # GitLab notifications
    if 'gitlab@mg.gitlab.com' in from_addr:
        return ('NOTIFICATION', 'label_and_archive', 'gitlab_notification')

    # Google security alerts for OTHER accounts (not this one)
    if 'no-reply@accounts.google.com' in from_addr and 'security alert' in subject:
        # Only archive if the alert is for a different email address
        if account_email.lower() not in subject:
            return ('NOTIFICATION', 'archive', 'google_security_other')

    return None
