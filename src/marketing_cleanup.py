#!/usr/bin/env python3
"""Marketing email cleanup — classifies emails as MARKETING/PERSONAL, labels and archives marketing."""

import logging
from typing import Dict, Any

from gmail_service import GmailService, GmailTokenExpiredError
from classifier import EmailClassifier
from database import Database

logger = logging.getLogger(__name__)


def run_marketing_cleanup(
    gmail: GmailService,
    classifier: EmailClassifier,
    db: Database,
    account_name: str,
    max_emails: int = 50,
    max_pages: int = 3,
) -> Dict[str, Any]:
    """
    Run marketing email cleanup for a single account.

    Returns dict with keys: processed, skipped, marketing_found, error
    """
    result = {'processed': 0, 'skipped': 0, 'marketing_found': 0, 'error': None}

    # Get or create "AI Assist" label
    try:
        label_result = gmail.get_or_create_label('AI Assist')
        ai_assist_label_id = label_result['labelId']
        if label_result['created']:
            logger.info(f"[{account_name}] Created 'AI Assist' label: {ai_assist_label_id}")
    except Exception as e:
        logger.error(f"[{account_name}] Failed to get/create label: {e}")
        result['error'] = str(e)
        return result

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

            logger.info(f"[{account_name}] Processing page {pages_processed}: {len(emails)} emails")

            email_ids = [e['id'] for e in emails]
            already_processed = db.get_processed_marketing_ids(account_name, email_ids)

            for email in emails:
                if email['id'] in already_processed:
                    result['skipped'] += 1
                    continue

                try:
                    classification = classifier.classify_marketing(email)
                    db.record_marketing_processed(account_name, email['id'], classification)

                    if classification == 'MARKETING':
                        result['marketing_found'] += 1
                        gmail.add_labels(email['id'], [ai_assist_label_id])
                        gmail.archive_message(email['id'])
                        logger.info(f"[{account_name}]   [MARKETING] {email.get('subject', 'No subject')[:60]}")

                    result['processed'] += 1

                except GmailTokenExpiredError:
                    raise
                except Exception as e:
                    logger.error(f"[{account_name}]   Error processing {email['id']}: {e}")

            if not page_token:
                break

    except GmailTokenExpiredError as e:
        logger.error(f"[{account_name}] Gmail token expired during processing: {e}")
        result['error'] = f"Token expired: {e}"

    return result
