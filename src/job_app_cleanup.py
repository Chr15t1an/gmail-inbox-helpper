#!/usr/bin/env python3
"""Job application email cleanup — classifies job-related emails and applies labels."""

import logging
from typing import Dict, Any

from gmail_service import GmailService, GmailTokenExpiredError
from classifier import EmailClassifier
from database import Database

logger = logging.getLogger(__name__)


def run_job_app_cleanup(
    gmail: GmailService,
    classifier: EmailClassifier,
    db: Database,
    account_name: str,
    max_emails: int = 50,
    max_pages: int = 3,
) -> Dict[str, Any]:
    """
    Run job application email cleanup for a single account.

    Returns dict with keys: processed, skipped, job_related_found, needs_followup_found, error
    """
    result = {
        'processed': 0, 'skipped': 0,
        'job_related_found': 0, 'needs_followup_found': 0,
        'error': None
    }

    # Get or create labels
    try:
        job_app_label = gmail.get_or_create_label('Job Application')
        followup_label = gmail.get_or_create_label('Needs Follow-up')
        job_app_label_id = job_app_label['labelId']
        followup_label_id = followup_label['labelId']

        ai_assist = gmail.find_label_by_name('AI Assist')
        ai_assist_label_id = ai_assist['id'] if ai_assist else None
    except Exception as e:
        logger.error(f"[{account_name}] Failed to get/create labels: {e}")
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
            already_processed = db.get_processed_job_app_ids(account_name, email_ids)

            for email in emails:
                if email['id'] in already_processed:
                    result['skipped'] += 1
                    continue

                if ai_assist_label_id and ai_assist_label_id in email.get('labelIds', []):
                    result['skipped'] += 1
                    continue

                try:
                    classification = classifier.classify_job_application(email)

                    db.record_job_app_processed(
                        account_name,
                        email['id'],
                        classification['is_job_related'],
                        classification['needs_followup'] if classification['is_job_related'] else None
                    )

                    result['processed'] += 1

                    if not classification['is_job_related']:
                        continue

                    gmail.add_labels(email['id'], [job_app_label_id])
                    result['job_related_found'] += 1

                    if classification['needs_followup']:
                        gmail.add_labels(email['id'], [followup_label_id])
                        result['needs_followup_found'] += 1
                        logger.info(f"[{account_name}]   [JOB:FOLLOWUP] {email.get('subject', 'No subject')[:60]}")
                    else:
                        gmail.archive_message(email['id'])
                        logger.info(f"[{account_name}]   [JOB:ARCHIVED] {email.get('subject', 'No subject')[:60]}")

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
