#!/usr/bin/env python3
"""General inbox cleanup — rule-based filters first, then AI classification for the rest."""

import logging
from typing import Dict, Any

from gmail_service import GmailService, GmailTokenExpiredError
from classifier import EmailClassifier
from database import Database
from rule_filters import apply_rules

logger = logging.getLogger(__name__)

# Maps classification to (label_name_to_apply, should_archive)
CLASSIFICATION_ACTIONS = {
    'RECEIPT': ('Receipts', True),
    'COLD_OUTREACH': ('AI Assist', True),
    'NOTIFICATION': (None, True),
    'NEEDS_ATTENTION': ('Needs Attention', False),
    'OTHER': (None, False),
}


def run_general_cleanup(
    gmail: GmailService,
    classifier: EmailClassifier,
    db: Database,
    account_name: str,
    account_email: str,
    max_emails: int = 50,
    max_pages: int = 3,
) -> Dict[str, Any]:
    """
    Run general inbox cleanup for a single account.

    Returns dict with processing stats.
    """
    result = {
        'processed': 0, 'skipped': 0,
        'rule_filtered': 0, 'ai_classified': 0,
        'archived': 0, 'error': None,
    }

    # Look up labels
    try:
        ai_assist_label_id = gmail.get_or_create_label('AI Assist')['labelId']
        needs_attention_label_id = gmail.get_or_create_label('Needs Attention')['labelId']
        receipts_label_id = gmail.get_or_create_label('Receipts')['labelId']

        # Optional labels — find if they exist, don't create
        airbnb_label = gmail.find_label_by_name('AirBnb')
        airbnb_label_id = airbnb_label['id'] if airbnb_label else None

        github_label = gmail.find_label_by_name('github')
        github_label_id = github_label['id'] if github_label else None
    except Exception as e:
        logger.error(f"[{account_name}] Failed to get/create labels: {e}")
        result['error'] = str(e)
        return result

    label_id_map = {
        'AI Assist': ai_assist_label_id,
        'Needs Attention': needs_attention_label_id,
        'Receipts': receipts_label_id,
        'github': github_label_id,
    }

    page_token = None
    pages_processed = 0

    try:
        while pages_processed < max_pages:
            response = gmail.list_messages(
                max_results=max_emails,
                page_token=page_token,
                label_ids=['INBOX']
            )

            emails = response['messages']
            page_token = response.get('nextPageToken')
            pages_processed += 1

            if not emails:
                logger.info(f"[{account_name}] No more emails to process (page {pages_processed})")
                break

            logger.info(f"[{account_name}] General cleanup page {pages_processed}: {len(emails)} emails")

            email_ids = [e['id'] for e in emails]
            already_processed = set(db.get_processed_general_ids(account_name, email_ids))

            for email in emails:
                if email['id'] in already_processed:
                    result['skipped'] += 1
                    continue

                # Skip if already has "AI Assist" label
                if ai_assist_label_id in email.get('labelIds', []):
                    result['skipped'] += 1
                    continue

                try:
                    # Try rule-based filter first
                    rule_result = apply_rules(email, account_email)

                    if rule_result:
                        classification, action, rule_name = rule_result
                        result['rule_filtered'] += 1
                        _apply_action(gmail, email, classification, action, label_id_map, airbnb_label_id)
                        db.record_general_processed(account_name, email['id'], classification, rule_name)
                        logger.info(f"[{account_name}]   [RULE:{rule_name}] {email.get('subject', 'No subject')[:60]}")
                    else:
                        # AI classification
                        classification = classifier.classify_general(email)
                        result['ai_classified'] += 1

                        label_name, should_archive = CLASSIFICATION_ACTIONS.get(classification, (None, False))

                        if label_name and label_id_map.get(label_name):
                            gmail.add_labels(email['id'], [label_id_map[label_name]])

                        # Airbnb label for any Airbnb emails
                        if airbnb_label_id and _is_airbnb(email):
                            gmail.add_labels(email['id'], [airbnb_label_id])

                        if should_archive:
                            gmail.archive_message(email['id'])
                            result['archived'] += 1
                            logger.info(f"[{account_name}]   [AI:{classification}] {email.get('subject', 'No subject')[:60]}")
                        else:
                            logger.info(f"[{account_name}]   [AI:{classification}:KEPT] {email.get('subject', 'No subject')[:60]}")

                        db.record_general_processed(account_name, email['id'], classification)

                    result['processed'] += 1

                except GmailTokenExpiredError:
                    raise
                except Exception as e:
                    logger.error(f"[{account_name}]   Error processing {email['id']}: {e}")

            if not page_token:
                break

    except GmailTokenExpiredError as e:
        logger.error(f"[{account_name}] Gmail token expired during general cleanup: {e}")
        result['error'] = f"Token expired: {e}"

    return result


def _apply_action(gmail, email, classification, action, label_id_map, airbnb_label_id):
    """Apply the action from a rule-based match."""
    if action == 'label_and_archive':
        if label_id_map.get('AI Assist'):
            gmail.add_labels(email['id'], [label_id_map['AI Assist']])
        gmail.archive_message(email['id'])
    elif action == 'label_and_archive_github':
        if label_id_map.get('github'):
            gmail.add_labels(email['id'], [label_id_map['github']])
        gmail.archive_message(email['id'])
    elif action == 'archive':
        gmail.archive_message(email['id'])

    # Airbnb label for any Airbnb emails regardless
    if airbnb_label_id and _is_airbnb(email):
        gmail.add_labels(email['id'], [airbnb_label_id])


def _is_airbnb(email):
    """Check if email is from Airbnb."""
    from_addr = (email.get('from') or '').lower()
    return 'airbnb' in from_addr
