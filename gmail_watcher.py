#!/usr/bin/env python3
"""Gmail Inbox Helper — macOS menu bar watcher."""

import logging
import os
import subprocess
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

import rumps

# Add src/ to path so we can import project modules
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT / 'src'))

from config import (
    ACCOUNTS, CHECK_INTERVAL, MAX_EMAILS_PER_PAGE, MAX_PAGES,
    get_feature_toggles, load_token,
)
from gmail_service import GmailService, GmailTokenExpiredError
from classifier import EmailClassifier
from database import Database

# Logging setup
LOG_FILE = PROJECT_ROOT / 'watcher.log'

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler(),
    ]
)
logger = logging.getLogger(__name__)


class GmailWatcher(rumps.App):
    def __init__(self):
        super(GmailWatcher, self).__init__("Gmail", quit_button=None)
        self.title = "\U0001F4EC"  # 📬

        self.status_item = rumps.MenuItem("Status: Idle")
        self.last_run_item = rumps.MenuItem("Last Run: Never")
        self.next_run_item = rumps.MenuItem("Next Run: Calculating...")

        self.menu = [
            self.status_item,
            self.last_run_item,
            self.next_run_item,
            None,
            rumps.MenuItem("Run Now", callback=self.run_now),
            rumps.MenuItem("View Logs", callback=self.view_logs),
            None,
            rumps.MenuItem("Quit", callback=self.quit_app),
        ]

        self.running = True
        self.is_processing = False
        self.next_run_time = None

        self.start_polling()

    def start_polling(self):
        thread = threading.Thread(target=self.poll_loop, daemon=True)
        thread.start()

    def poll_loop(self):
        # Run immediately on start
        self.run_cleanup()

        while self.running:
            self.next_run_time = time.time() + CHECK_INTERVAL
            self.update_next_run()

            # Sleep in 60s chunks for responsive shutdown
            remaining = CHECK_INTERVAL
            while remaining > 0 and self.running:
                time.sleep(min(60, remaining))
                remaining -= 60
                self.update_next_run()

            if self.running:
                self.run_cleanup()

    def run_now(self, _):
        if self.is_processing:
            rumps.alert("Already Running", "A cleanup cycle is already in progress.")
            return
        thread = threading.Thread(target=self.run_cleanup, daemon=True)
        thread.start()

    def run_cleanup(self):
        if self.is_processing:
            return
        self.is_processing = True
        self.title = "\U0001F504"  # 🔄
        self.status_item.title = "Status: Running..."

        logger.info("=" * 60)
        logger.info("Starting cleanup cycle")
        logger.info("=" * 60)

        toggles = get_feature_toggles()
        db = Database()
        has_errors = False

        try:
            classifier = EmailClassifier()
        except Exception as e:
            logger.error(f"Failed to initialize classifier: {e}")
            self.title = "\u274C"  # ❌
            self.status_item.title = "Status: Error (classifier)"
            self.is_processing = False
            return

        for account in ACCOUNTS:
            name = account['name']
            account_toggles = toggles.get(name, {})

            # Load token
            try:
                token_json = load_token(name)
            except FileNotFoundError as e:
                logger.warning(f"[{name}] Skipping — no token file: {e}")
                continue

            # Init Gmail service
            try:
                gmail = GmailService(token_json)
            except GmailTokenExpiredError as e:
                logger.error(f"[{name}] Token expired: {e}")
                has_errors = True
                continue
            except Exception as e:
                logger.error(f"[{name}] Failed to init Gmail service: {e}")
                has_errors = True
                continue

            # Validate token before processing
            try:
                gmail.validate_token()
                logger.info(f"[{name}] Token validated")
            except GmailTokenExpiredError as e:
                logger.error(f"[{name}] Token validation failed — skipping: {e}")
                has_errors = True
                continue
            except Exception as e:
                logger.error(f"[{name}] Token validation error — skipping: {e}")
                has_errors = True
                continue

            # Marketing cleanup
            if account_toggles.get('marketing', False):
                logger.info(f"[{name}] Running marketing cleanup...")
                from marketing_cleanup import run_marketing_cleanup
                result = run_marketing_cleanup(
                    gmail, classifier, db, name,
                    max_emails=MAX_EMAILS_PER_PAGE, max_pages=MAX_PAGES,
                )
                logger.info(
                    f"[{name}] Marketing: {result['processed']} processed, "
                    f"{result['skipped']} skipped, {result['marketing_found']} marketing archived"
                )
                if result.get('error'):
                    has_errors = True
            else:
                logger.info(f"[{name}] Marketing cleanup disabled")

            # Job app cleanup
            if account_toggles.get('jobapp', False):
                logger.info(f"[{name}] Running job app cleanup...")
                from job_app_cleanup import run_job_app_cleanup
                result = run_job_app_cleanup(
                    gmail, classifier, db, name,
                    max_emails=MAX_EMAILS_PER_PAGE, max_pages=MAX_PAGES,
                )
                logger.info(
                    f"[{name}] Job apps: {result['processed']} processed, "
                    f"{result['skipped']} skipped, {result['job_related_found']} job-related, "
                    f"{result['needs_followup_found']} need follow-up"
                )
                if result.get('error'):
                    has_errors = True
            else:
                logger.info(f"[{name}] Job app cleanup disabled")

        db.close()

        now = datetime.now()
        self.last_run_item.title = f"Last Run: {now.strftime('%m/%d %H:%M')}"

        if has_errors:
            self.title = "\u26A0\uFE0F"  # ⚠️
            self.status_item.title = "Status: Completed with errors"
        else:
            self.title = "\U0001F4EC"  # 📬
            self.status_item.title = "Status: Idle"

        logger.info("Cleanup cycle complete")
        logger.info("=" * 60)
        self.is_processing = False

    def update_next_run(self):
        if self.next_run_time:
            remaining = self.next_run_time - time.time()
            if remaining > 0:
                hours = int(remaining // 3600)
                minutes = int((remaining % 3600) // 60)
                if hours > 0:
                    self.next_run_item.title = f"Next Run: {hours}h {minutes}m"
                else:
                    self.next_run_item.title = f"Next Run: {minutes}m"
            else:
                self.next_run_item.title = "Next Run: Now"

    def view_logs(self, _):
        subprocess.run(['open', str(LOG_FILE)])

    def quit_app(self, _):
        logger.info("Quitting Gmail Watcher")
        self.running = False
        rumps.quit_application()


def main():
    logger.info("Starting Gmail Inbox Helper watcher")
    app = GmailWatcher()
    app.run()


if __name__ == '__main__':
    main()
