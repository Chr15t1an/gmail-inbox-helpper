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

    # Google security alerts for OTHER accounts (not this one).
    # Google puts the affected address in the BODY, not the subject ("Security alert" /
    # "A new sign-in on Mac OS hello@…"). Until 2026-09-07 this checked the subject only and
    # archived alerts about the very account being processed. Check everything we have, and
    # if we have nothing beyond the subject, do not fire — keeping a stray alert is cheap.
    if 'no-reply@accounts.google.com' in from_addr and 'security alert' in subject:
        haystack = ' '.join(
            (email.get(k) or '') for k in ('subject', 'snippet', 'body')
        ).lower()
        has_text = bool((email.get('snippet') or email.get('body') or '').strip())
        if has_text and account_email.lower() not in haystack:
            return ('NOTIFICATION', 'archive', 'google_security_other')

    return None
