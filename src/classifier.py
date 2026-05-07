"""Email classification using OpenAI GPT-4o-mini."""

import os
from typing import Dict
from openai import OpenAI


class EmailClassifier:
    def __init__(self):
        api_key = os.environ.get('OPENAI_API_KEY')
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable not set")
        self.client = OpenAI(api_key=api_key)

    def classify_marketing(self, email: Dict) -> str:
        """
        Classify email as MARKETING or PERSONAL.

        Args:
            email: Dict with 'from', 'subject', 'snippet', 'body' keys

        Returns:
            'MARKETING' or 'PERSONAL'
        """
        from_addr = email.get('from', 'Unknown sender')
        subject = email.get('subject', 'No subject')
        snippet = email.get('snippet', '')
        body = (email.get('body') or '')[:500]  # First 500 chars

        prompt = f"""Classify this email:

From: {from_addr}
Subject: {subject}
Preview: {snippet}

Body excerpt:
{body}

Is this a MARKETING email or a PERSONAL email?"""

        try:
            response = self.client.chat.completions.create(
                model='gpt-4o-mini',
                messages=[
                    {
                        'role': 'system',
                        'content': (
                            'You are an email classifier. Classify emails as either MARKETING or PERSONAL. '
                            'Marketing emails include newsletters, promotions, advertisements, product updates, '
                            'and automated notifications from businesses. Personal emails are from real people '
                            'you might know or important transactional emails (receipts, confirmations, etc.). '
                            'Respond with only one word: MARKETING or PERSONAL.'
                        )
                    },
                    {'role': 'user', 'content': prompt}
                ],
                max_tokens=10,
                temperature=0
            )

            result = response.choices[0].message.content.strip().upper()
            return 'MARKETING' if 'MARKETING' in result else 'PERSONAL'

        except Exception as e:
            print(f"Classification error: {e}")
            return 'PERSONAL'  # Default to personal on error (don't archive)

    def classify_general(self, email: Dict) -> str:
        """
        Classify email into general categories.

        Returns one of: RECEIPT, COLD_OUTREACH, NOTIFICATION, NEEDS_ATTENTION, OTHER
        """
        from_addr = email.get('from', 'Unknown sender')
        subject = email.get('subject', 'No subject')
        snippet = email.get('snippet', '')
        body = (email.get('body') or '')[:500]

        prompt = f"""Classify this email into one category:

From: {from_addr}
Subject: {subject}
Preview: {snippet}

Body excerpt:
{body}

Respond with ONLY one of these categories:
- RECEIPT (order confirmations, payment receipts, invoices, shipping notifications)
- COLD_OUTREACH (unsolicited sales, partnership proposals, recruitment spam, cold emails from strangers)
- NOTIFICATION (automated alerts, social media notifications, service updates, account activity)
- NEEDS_ATTENTION (emails requiring a response or action from a real person you know or do business with)
- OTHER (anything that doesn't clearly fit the above categories)"""

        try:
            response = self.client.chat.completions.create(
                model='gpt-4o-mini',
                messages=[
                    {
                        'role': 'system',
                        'content': (
                            'You are an email classifier. Classify emails into exactly one category. '
                            'When uncertain, choose NEEDS_ATTENTION or OTHER — never classify as '
                            'RECEIPT, COLD_OUTREACH, or NOTIFICATION unless you are confident. '
                            'The cost of missing an important email is much higher than leaving a '
                            'junk email in the inbox. Respond with only the category name.'
                        )
                    },
                    {'role': 'user', 'content': prompt}
                ],
                max_tokens=10,
                temperature=0
            )

            result = response.choices[0].message.content.strip().upper()

            for category in ['RECEIPT', 'COLD_OUTREACH', 'NOTIFICATION', 'NEEDS_ATTENTION']:
                if category in result:
                    return category
            return 'OTHER'

        except Exception as e:
            print(f"General classification error: {e}")
            return 'OTHER'  # Default to OTHER on error (don't archive)

    def classify_job_application(self, email: Dict) -> Dict[str, bool]:
        """
        Classify if email is job-related and needs follow-up.

        Args:
            email: Dict with 'from', 'subject', 'snippet' keys

        Returns:
            Dict with 'is_job_related' and 'needs_followup' booleans
        """
        from_addr = email.get('from', '')
        subject = email.get('subject', '')
        snippet = email.get('snippet', '')

        prompt = f"""You are an email classifier. Analyze this email and determine:
1. Is it related to job applications, job hunting, or employment opportunities?
2. Does it require follow-up action from the recipient?

JOB-RELATED emails include:
- Application confirmations
- Interview invitations or scheduling
- Rejection letters
- Assessment or coding test requests
- Recruiter outreach
- Job offer communications
- Follow-up requests from employers

NOT job-related:
- Marketing emails, newsletters
- Social media notifications
- Personal correspondence
- Shopping/order confirmations
- Account notifications

NEEDS FOLLOW-UP (if job-related):
- Interview invitations (need to confirm/schedule)
- Assessment or coding test requests
- Requests for additional information
- Action items or next steps required
- Questions that need answers

DOES NOT NEED FOLLOW-UP:
- Simple application confirmations ("We received your application")
- Rejection letters
- Automated "no reply needed" messages
- Status updates with no action required

Email:
From: {from_addr}
Subject: {subject}
Preview: {snippet}

Respond with ONLY one of these exact formats:
- NOT_JOB_RELATED
- JOB_RELATED:NO_FOLLOWUP
- JOB_RELATED:NEEDS_FOLLOWUP"""

        try:
            response = self.client.chat.completions.create(
                model='gpt-4o-mini',
                messages=[{'role': 'user', 'content': prompt}],
                max_tokens=30,
                temperature=0
            )

            content = response.choices[0].message.content.strip().upper()

            if 'NOT_JOB_RELATED' in content:
                return {'is_job_related': False, 'needs_followup': False}
            elif 'NEEDS_FOLLOWUP' in content:
                return {'is_job_related': True, 'needs_followup': True}
            elif 'JOB_RELATED' in content:
                return {'is_job_related': True, 'needs_followup': False}
            else:
                return {'is_job_related': False, 'needs_followup': False}

        except Exception as e:
            print(f"Classification error: {e}")
            return {'is_job_related': False, 'needs_followup': False}
