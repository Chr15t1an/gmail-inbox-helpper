"""Gmail API service with automatic token refresh."""

import base64
import json
import os
import re
from typing import Dict, List, Optional, Any

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError


class GmailTokenExpiredError(Exception):
    """Raised when Gmail token is invalid or expired."""
    pass


class GmailService:
    def __init__(self, token_json: str):
        """
        Initialize Gmail service with token JSON.

        Args:
            token_json: JSON string containing OAuth tokens
        """
        self.token_data = json.loads(token_json)
        self.creds = self._create_credentials()
        self.service = build('gmail', 'v1', credentials=self.creds)

    def _create_credentials(self) -> Credentials:
        """Create and refresh credentials if needed."""
        creds = Credentials(
            token=self.token_data.get('token'),
            refresh_token=self.token_data.get('refresh_token'),
            token_uri='https://oauth2.googleapis.com/token',
            client_id=self.token_data.get('client_id'),
            client_secret=self.token_data.get('client_secret'),
            scopes=self.token_data.get('scopes', ['https://www.googleapis.com/auth/gmail.modify'])
        )

        # Refresh if expired
        if creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception as e:
                raise GmailTokenExpiredError(f"Token refresh failed: {e}")

        return creds

    def list_messages(
        self,
        max_results: int = 20,
        query: str = None,
        page_token: str = None,
        label_ids: List[str] = None
    ) -> Dict[str, Any]:
        """
        List messages from inbox.

        Returns:
            Dict with 'messages', 'nextPageToken', 'resultSizeEstimate'
        """
        try:
            params = {
                'userId': 'me',
                'maxResults': min(max_results, 100),
                'labelIds': label_ids or ['INBOX']
            }
            if query:
                params['q'] = query
            if page_token:
                params['pageToken'] = page_token

            response = self.service.users().messages().list(**params).execute()

            messages = []
            for msg in response.get('messages', []):
                full_msg = self.get_message(msg['id'])
                messages.append(full_msg)

            return {
                'messages': messages,
                'nextPageToken': response.get('nextPageToken'),
                'resultSizeEstimate': response.get('resultSizeEstimate', 0)
            }
        except HttpError as e:
            if e.resp.status == 401:
                raise GmailTokenExpiredError("Gmail authentication failed")
            raise

    def get_message(self, message_id: str) -> Dict[str, Any]:
        """Get a single message with full details."""
        try:
            msg = self.service.users().messages().get(
                userId='me',
                id=message_id,
                format='full'
            ).execute()
            return self._format_message(msg)
        except HttpError as e:
            if e.resp.status == 401:
                raise GmailTokenExpiredError("Gmail authentication failed")
            raise

    def archive_message(self, message_id: str) -> bool:
        """Archive a message (remove from INBOX)."""
        try:
            self.service.users().messages().modify(
                userId='me',
                id=message_id,
                body={'removeLabelIds': ['INBOX']}
            ).execute()
            return True
        except HttpError as e:
            if e.resp.status == 401:
                raise GmailTokenExpiredError("Gmail authentication failed")
            raise

    def add_labels(self, message_id: str, label_ids: List[str]) -> bool:
        """Add labels to a message."""
        try:
            self.service.users().messages().modify(
                userId='me',
                id=message_id,
                body={'addLabelIds': label_ids}
            ).execute()
            return True
        except HttpError as e:
            if e.resp.status == 401:
                raise GmailTokenExpiredError("Gmail authentication failed")
            raise

    def list_labels(self) -> List[Dict[str, str]]:
        """List all labels."""
        try:
            response = self.service.users().labels().list(userId='me').execute()
            return [
                {'id': label['id'], 'name': label['name'], 'type': label.get('type')}
                for label in response.get('labels', [])
            ]
        except HttpError as e:
            if e.resp.status == 401:
                raise GmailTokenExpiredError("Gmail authentication failed")
            raise

    def find_label_by_name(self, name: str) -> Optional[Dict[str, str]]:
        """Find a label by name."""
        labels = self.list_labels()
        for label in labels:
            if label['name'] == name:
                return label
        return None

    def create_label(self, name: str) -> Dict[str, str]:
        """Create a new label."""
        try:
            label = self.service.users().labels().create(
                userId='me',
                body={
                    'name': name,
                    'labelListVisibility': 'labelShow',
                    'messageListVisibility': 'show'
                }
            ).execute()
            return {'id': label['id'], 'name': label['name'], 'type': label.get('type')}
        except HttpError as e:
            if e.resp.status == 401:
                raise GmailTokenExpiredError("Gmail authentication failed")
            raise

    def get_or_create_label(self, name: str) -> Dict[str, Any]:
        """Get existing label or create if not exists."""
        existing = self.find_label_by_name(name)
        if existing:
            return {'labelId': existing['id'], 'created': False}

        created = self.create_label(name)
        return {'labelId': created['id'], 'created': True}

    def _format_message(self, msg: Dict) -> Dict[str, Any]:
        """Format raw Gmail message to clean structure."""
        headers = {h['name']: h['value'] for h in msg['payload'].get('headers', [])}

        body = self._extract_body(msg['payload'])

        return {
            'id': msg['id'],
            'threadId': msg['threadId'],
            'labelIds': msg.get('labelIds', []),
            'snippet': self._sanitize_utf8(msg.get('snippet', '')),
            'from': self._sanitize_utf8(headers.get('From', '')),
            'to': self._sanitize_utf8(headers.get('To', '')),
            'subject': self._sanitize_utf8(headers.get('Subject', '')),
            'date': headers.get('Date', ''),
            'body': body,
            'isUnread': 'UNREAD' in msg.get('labelIds', []),
        }

    def _extract_body(self, payload: Dict) -> Optional[str]:
        """Extract body content from email payload."""
        # Try direct body
        if payload.get('body', {}).get('data'):
            decoded = base64.urlsafe_b64decode(payload['body']['data']).decode('utf-8', errors='replace')
            return self._sanitize_utf8(decoded)

        # Search parts for text/plain or text/html
        for part in payload.get('parts', []):
            if part.get('mimeType') == 'text/plain' and part.get('body', {}).get('data'):
                decoded = base64.urlsafe_b64decode(part['body']['data']).decode('utf-8', errors='replace')
                return self._sanitize_utf8(decoded)

        # Fallback to text/html
        for part in payload.get('parts', []):
            if part.get('mimeType') == 'text/html' and part.get('body', {}).get('data'):
                decoded = base64.urlsafe_b64decode(part['body']['data']).decode('utf-8', errors='replace')
                return self._sanitize_utf8(decoded)

        return None

    def _sanitize_utf8(self, text: Optional[str]) -> str:
        """Sanitize string to valid UTF-8."""
        if not text:
            return ''
        # Remove control characters except newlines and tabs
        return re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', '', text)
