"""Database service for tracking processed emails using Cloudflare D1."""

import os
import json
from typing import List, Optional
import urllib.request
import urllib.error


class Database:
    """Cloudflare D1 database client using REST API."""

    def __init__(self):
        self.account_id = os.environ.get('CF_ACCOUNT_ID')
        self.database_id = os.environ.get('CF_D1_DATABASE_ID')
        self.api_token = os.environ.get('CF_API_TOKEN')

        if not all([self.account_id, self.database_id, self.api_token]):
            raise ValueError(
                "CF_ACCOUNT_ID, CF_D1_DATABASE_ID, and CF_API_TOKEN environment variables required"
            )

        self.base_url = f"https://api.cloudflare.com/client/v4/accounts/{self.account_id}/d1/database/{self.database_id}/query"

    def _execute(self, sql: str, params: List = None) -> dict:
        """Execute a SQL query against D1."""
        payload = {"sql": sql}
        if params:
            payload["params"] = params

        data = json.dumps(payload).encode('utf-8')
        headers = {
            'Authorization': f'Bearer {self.api_token}',
            'Content-Type': 'application/json',
        }

        req = urllib.request.Request(self.base_url, data=data, headers=headers, method='POST')

        try:
            with urllib.request.urlopen(req) as response:
                result = json.loads(response.read().decode('utf-8'))
                if not result.get('success'):
                    errors = result.get('errors', [])
                    raise Exception(f"D1 query failed: {errors}")
                return result
        except urllib.error.HTTPError as e:
            error_body = e.read().decode('utf-8')
            raise Exception(f"D1 API error ({e.code}): {error_body}")

    def close(self):
        """No-op for REST API client."""
        pass

    # Marketing emails
    def get_processed_marketing_ids(self, account_name: str, email_ids: List[str]) -> List[str]:
        """Get IDs of emails that have already been processed."""
        if not email_ids:
            return []

        # D1 doesn't support arrays, so we use IN with placeholders
        placeholders = ','.join(['?' for _ in email_ids])
        sql = f"""
            SELECT email_id FROM processed_emails
            WHERE account_name = ? AND email_id IN ({placeholders})
        """
        params = [account_name] + email_ids

        result = self._execute(sql, params)
        rows = result.get('result', [{}])[0].get('results', [])
        return [row['email_id'] for row in rows]

    def record_marketing_processed(self, account_name: str, email_id: str, classification: str):
        """Record a processed marketing email."""
        sql = """
            INSERT INTO processed_emails (account_name, email_id, classification)
            VALUES (?, ?, ?)
            ON CONFLICT (account_name, email_id) DO NOTHING
        """
        self._execute(sql, [account_name, email_id, classification])

    # Job application emails
    def get_processed_job_app_ids(self, account_name: str, email_ids: List[str]) -> List[str]:
        """Get IDs of job app emails that have already been processed."""
        if not email_ids:
            return []

        placeholders = ','.join(['?' for _ in email_ids])
        sql = f"""
            SELECT email_id FROM job_application_emails
            WHERE account_name = ? AND email_id IN ({placeholders})
        """
        params = [account_name] + email_ids

        result = self._execute(sql, params)
        rows = result.get('result', [{}])[0].get('results', [])
        return [row['email_id'] for row in rows]

    def record_job_app_processed(
        self,
        account_name: str,
        email_id: str,
        is_job_related: bool,
        needs_followup: Optional[bool]
    ):
        """Record a processed job application email."""
        sql = """
            INSERT INTO job_application_emails
            (account_name, email_id, is_job_related, needs_followup)
            VALUES (?, ?, ?, ?)
            ON CONFLICT (account_name, email_id) DO NOTHING
        """
        self._execute(sql, [
            account_name,
            email_id,
            1 if is_job_related else 0,
            1 if needs_followup else (0 if needs_followup is False else None)
        ])
