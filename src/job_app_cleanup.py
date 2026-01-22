#!/usr/bin/env python3
"""
Job application email cleanup script.
Classifies job-related emails and applies appropriate labels.

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

    print(f"Starting job application cleanup for {account_name}")

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

    # Get or create labels
    try:
        job_app_label = gmail.get_or_create_label('Job Application')
        followup_label = gmail.get_or_create_label('Needs Follow-up')
        job_app_label_id = job_app_label['labelId']
        followup_label_id = followup_label['labelId']

        # Get AI Assist label ID to skip marketing emails
        ai_assist = gmail.find_label_by_name('AI Assist')
        ai_assist_label_id = ai_assist['id'] if ai_assist else None
    except Exception as e:
        print(f"ERROR: Failed to get/create labels: {e}")
        sys.exit(1)

    # Process emails
    processed = 0
    skipped = 0
    job_related_found = 0
    needs_followup_found = 0
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
            already_processed = db.get_processed_job_app_ids(account_name, email_ids)

            for email in emails:
                # Skip already processed
                if email['id'] in already_processed:
                    skipped += 1
                    continue

                # Skip if has AI Assist label (already processed as marketing)
                if ai_assist_label_id and ai_assist_label_id in email.get('labelIds', []):
                    skipped += 1
                    continue

                try:
                    # Classify
                    classification = classifier.classify_job_application(email)

                    # Record in database
                    db.record_job_app_processed(
                        account_name,
                        email['id'],
                        classification['is_job_related'],
                        classification['needs_followup'] if classification['is_job_related'] else None
                    )

                    processed += 1

                    if not classification['is_job_related']:
                        continue

                    # Apply "Job Application" label
                    gmail.add_labels(email['id'], [job_app_label_id])
                    job_related_found += 1

                    if classification['needs_followup']:
                        # Add "Needs Follow-up" label, keep in inbox
                        gmail.add_labels(email['id'], [followup_label_id])
                        needs_followup_found += 1
                        print(f"  [JOB:FOLLOWUP] {email.get('subject', 'No subject')[:50]}")
                    else:
                        # Archive (remove from inbox)
                        gmail.archive_message(email['id'])
                        print(f"  [JOB:ARCHIVED] {email.get('subject', 'No subject')[:50]}")

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

    print(f"\nCompleted: {processed} processed, {skipped} skipped")
    print(f"Job-related: {job_related_found}, Needs follow-up: {needs_followup_found}")


if __name__ == '__main__':
    main()
