#!/usr/bin/env python3
"""
Marketing email cleanup script.
Classifies emails as MARKETING/PERSONAL, labels and archives marketing emails.

Environment variables:
    GMAIL_TOKEN: JSON string with OAuth tokens
    OPENAI_API_KEY: OpenAI API key
    CF_ACCOUNT_ID: Cloudflare account ID
    CF_D1_DATABASE_ID: Cloudflare D1 database ID
    CF_API_TOKEN: Cloudflare API token
    ACCOUNT_NAME: Account identifier (e.g., 'conveyour')
    MAX_EMAILS_PER_PAGE: Max emails per page (default: 50)
    MAX_PAGES: Max pages to process (default: 3)
"""

import os
import sys

from gmail_service import GmailService, GmailTokenExpiredError
from classifier import EmailClassifier
from database import Database


def main():
    # Configuration
    account_name = os.environ.get('ACCOUNT_NAME')
    gmail_token = os.environ.get('GMAIL_TOKEN')
    max_emails = int(os.environ.get('MAX_EMAILS_PER_PAGE', 50))
    max_pages = int(os.environ.get('MAX_PAGES', 3))

    if not account_name or not gmail_token:
        print("ERROR: ACCOUNT_NAME and GMAIL_TOKEN are required")
        sys.exit(1)

    print(f"Starting marketing cleanup for {account_name}")

    # Initialize services
    try:
        gmail = GmailService(gmail_token)
        classifier = EmailClassifier()
        db = Database()
    except GmailTokenExpiredError as e:
        print(f"ERROR: Gmail token expired for {account_name}: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"ERROR: Failed to initialize services: {e}")
        sys.exit(1)

    # Get or create "AI Assist" label
    try:
        label_result = gmail.get_or_create_label('AI Assist')
        ai_assist_label_id = label_result['labelId']
        if label_result['created']:
            print(f"Created 'AI Assist' label: {ai_assist_label_id}")
    except Exception as e:
        print(f"ERROR: Failed to get/create label: {e}")
        sys.exit(1)

    # Process emails
    processed = 0
    skipped = 0
    marketing_found = 0
    page_token = None
    pages_processed = 0

    try:
        while pages_processed < max_pages:
            result = gmail.list_messages(
                max_results=max_emails,
                page_token=page_token,
                label_ids=['INBOX']
            )

            emails = result['messages']
            page_token = result.get('nextPageToken')
            pages_processed += 1

            if not emails:
                print(f"No more emails to process (page {pages_processed})")
                break

            print(f"Processing page {pages_processed}: {len(emails)} emails")

            # Get already processed IDs
            email_ids = [e['id'] for e in emails]
            already_processed = db.get_processed_marketing_ids(account_name, email_ids)

            for email in emails:
                if email['id'] in already_processed:
                    skipped += 1
                    continue

                try:
                    # Classify
                    classification = classifier.classify_marketing(email)

                    # Record in database
                    db.record_marketing_processed(account_name, email['id'], classification)

                    if classification == 'MARKETING':
                        marketing_found += 1

                        # Add label
                        gmail.add_labels(email['id'], [ai_assist_label_id])

                        # Archive
                        gmail.archive_message(email['id'])

                        print(f"  [MARKETING] {email.get('subject', 'No subject')[:50]}")

                    processed += 1

                except GmailTokenExpiredError:
                    raise
                except Exception as e:
                    print(f"  Error processing {email['id']}: {e}")

            if not page_token:
                break

    except GmailTokenExpiredError as e:
        print(f"ERROR: Gmail token expired during processing: {e}")
        sys.exit(1)
    finally:
        db.close()

    print(f"\nCompleted: {processed} processed, {skipped} skipped, {marketing_found} marketing found")


if __name__ == '__main__':
    main()
