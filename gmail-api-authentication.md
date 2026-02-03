# Gmail API Authentication for Automated Workflows

This document describes how Gmail API OAuth 2.0 authentication works, particularly for headless/automated environments like GitHub Actions.

## Table of Contents

1. [OAuth 2.0 Flow Overview](#oauth-20-flow-overview)
2. [Google Cloud Console Setup](#google-cloud-console-setup)
3. [Understanding credentials.json](#understanding-credentialsjson)
4. [Understanding token.json](#understanding-tokenjson)
5. [Obtaining Refresh Tokens](#obtaining-refresh-tokens)
6. [Token Refresh Patterns for Automated Environments](#token-refresh-patterns-for-automated-environments)
7. [Gmail API Scopes](#gmail-api-scopes)
8. [Storing Credentials in GitHub Actions](#storing-credentials-in-github-actions)
9. [Token Lifecycle and Expiration](#token-lifecycle-and-expiration)

---

## OAuth 2.0 Flow Overview

Gmail API uses OAuth 2.0 for authentication. The flow works as follows:

```
┌──────────────┐     ┌─────────────────────┐     ┌──────────────────┐
│  Your App    │────▶│  Google Auth Server │────▶│  User Consent    │
│              │     │                     │     │  Screen          │
└──────────────┘     └─────────────────────┘     └──────────────────┘
                              │                          │
                              ▼                          ▼
                     ┌─────────────────────┐     ┌──────────────────┐
                     │  Authorization Code │◀────│  User Grants     │
                     │                     │     │  Permission      │
                     └─────────────────────┘     └──────────────────┘
                              │
                              ▼
                     ┌─────────────────────┐
                     │  Exchange Code for  │
                     │  Access + Refresh   │
                     │  Tokens             │
                     └─────────────────────┘
                              │
                              ▼
                     ┌─────────────────────┐
                     │  Store Tokens       │
                     │  (token.json)       │
                     └─────────────────────┘
```

### Key Steps

1. **Redirect to Google**: Application redirects user to Google's authorization server with client ID, requested scopes, and redirect URI
2. **User Consent**: User sees the OAuth consent screen and grants permission
3. **Authorization Code**: Google redirects back to your app with an authorization code
4. **Token Exchange**: Application exchanges the authorization code for access and refresh tokens
5. **API Access**: Application uses the access token to call Gmail API
6. **Token Refresh**: When the access token expires, use the refresh token to obtain a new one

### Critical Parameters for Automated Access

To receive a refresh token (required for automated/headless operation), you must include:

- `access_type=offline` - Enables offline access so you can refresh tokens without user interaction
- `prompt=consent` - Forces the consent screen to appear and ensures a refresh token is returned

Without these parameters, you will only receive an access token that expires in 1 hour with no way to refresh it automatically.

---

## Google Cloud Console Setup

### Step 1: Create a Google Cloud Project

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Click the project dropdown in the top navigation
3. Select "New Project"
4. Enter a project name and create

### Step 2: Enable the Gmail API

1. Navigate to "APIs & Services" > "Library"
2. Search for "Gmail API"
3. Click on Gmail API and click "Enable"

### Step 3: Configure OAuth Consent Screen

1. Go to "APIs & Services" > "OAuth consent screen"
2. Select user type:
   - **Internal**: Only for Google Workspace users within your organization
   - **External**: For any Google account user
3. Fill in required fields:
   - App name
   - User support email
   - Developer contact email
4. Add scopes your application needs
5. Add test users (if using External type in Testing mode)

### Step 4: Create OAuth Client ID

1. Go to "APIs & Services" > "Credentials"
2. Click "Create Credentials" > "OAuth client ID"
3. Select application type:
   - **Desktop app**: For local scripts and CLI tools
   - **Web application**: For server-side applications
4. Enter a name for the credential
5. For web applications, add authorized redirect URIs
6. Click "Create"

### Step 5: Download Credentials

After creating the OAuth client ID:
1. Click the download button next to your credential
2. Save the file as `credentials.json`
3. Store this file securely - it contains your client secret

---

## Understanding credentials.json

The `credentials.json` file (also called `client_secret.json` or `client_secrets.json`) contains your OAuth 2.0 client configuration downloaded from Google Cloud Console.

### Structure for Desktop Applications

```json
{
  "installed": {
    "client_id": "123456789-abcdefg.apps.googleusercontent.com",
    "project_id": "your-project-id",
    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
    "token_uri": "https://oauth2.googleapis.com/token",
    "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
    "client_secret": "GOCSPX-xxxxxxxxxxxx",
    "redirect_uris": ["http://localhost"]
  }
}
```

### Structure for Web Applications

```json
{
  "web": {
    "client_id": "123456789-abcdefg.apps.googleusercontent.com",
    "project_id": "your-project-id",
    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
    "token_uri": "https://oauth2.googleapis.com/token",
    "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
    "client_secret": "GOCSPX-xxxxxxxxxxxx",
    "redirect_uris": ["https://yourapp.com/callback"]
  }
}
```

### Key Fields

| Field | Description |
|-------|-------------|
| `client_id` | Unique identifier for your application |
| `client_secret` | Secret key for your application (treat like a password) |
| `auth_uri` | Google's authorization endpoint |
| `token_uri` | Endpoint for exchanging codes for tokens |
| `redirect_uris` | Where Google sends users after authorization |

### Security Note

The `credentials.json` file should be treated as sensitive. Anyone with access to the client ID and secret can impersonate your application (though they still need user consent to access user data).

---

## Understanding token.json

The `token.json` file stores the user's access and refresh tokens after completing the OAuth flow. This file is created automatically when authorization completes for the first time.

### Structure

```json
{
  "token": "ya29.a0AfB_byC...",
  "refresh_token": "1//xEoDL4iW3cxlI7yDbSRFYNG01kVKM...",
  "token_uri": "https://oauth2.googleapis.com/token",
  "client_id": "123456789-abcdefg.apps.googleusercontent.com",
  "client_secret": "GOCSPX-xxxxxxxxxxxx",
  "scopes": [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.modify"
  ],
  "expiry": "2024-01-15T10:30:00.000000Z"
}
```

### Key Fields

| Field | Description |
|-------|-------------|
| `token` | The access token used to authenticate API requests (expires in ~1 hour) |
| `refresh_token` | Long-lived token used to obtain new access tokens without user interaction |
| `token_uri` | Endpoint for refreshing tokens |
| `client_id` | Your application's client ID |
| `client_secret` | Your application's client secret |
| `scopes` | The permissions granted by the user |
| `expiry` | Timestamp when the access token expires |

### Security Note

The `token.json` file contains everything needed to access the user's Gmail. It should be treated as highly sensitive and never committed to version control or exposed publicly.

---

## Obtaining Refresh Tokens

Refresh tokens are essential for automated/headless environments because they allow your application to obtain new access tokens without user interaction.

### Method 1: Using Google OAuth 2.0 Playground

1. Go to [OAuth 2.0 Playground](https://developers.google.com/oauthplayground/)
2. Click the gear icon in the upper right corner
3. Check "Use your own OAuth credentials"
4. Set "OAuth flow" to "Server-side"
5. Set "Access type" to "Offline"
6. Enter your Client ID and Client Secret
7. In the left panel, select Gmail API scopes needed
8. Click "Authorize APIs"
9. Grant permission when prompted
10. Click "Exchange authorization code for tokens"
11. Copy the refresh token from the response

**Important**: Add `https://developers.google.com/oauthplayground` to your OAuth client's authorized redirect URIs in Google Cloud Console.

### Method 2: Using Python Script (Local One-Time Setup)

```python
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = [
    'https://www.googleapis.com/auth/gmail.readonly',
    'https://www.googleapis.com/auth/gmail.modify'
]

flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
creds = flow.run_local_server(port=0)

# This output contains the refresh token
# Store this as your GMAIL_TOKEN secret
print(creds.to_json())
```

### Method 3: Manual Authorization URL

Construct an authorization URL with the required parameters:

```
https://accounts.google.com/o/oauth2/v2/auth?
  client_id=YOUR_CLIENT_ID&
  redirect_uri=YOUR_REDIRECT_URI&
  response_type=code&
  scope=https://www.googleapis.com/auth/gmail.readonly&
  access_type=offline&
  prompt=consent
```

After the user consents, exchange the authorization code for tokens:

```bash
curl -X POST https://oauth2.googleapis.com/token \
  -d "client_id=YOUR_CLIENT_ID" \
  -d "client_secret=YOUR_CLIENT_SECRET" \
  -d "code=AUTHORIZATION_CODE" \
  -d "grant_type=authorization_code" \
  -d "redirect_uri=YOUR_REDIRECT_URI"
```

---

## Token Refresh Patterns for Automated Environments

### How Token Refresh Works

When your access token expires (typically after 1 hour), you use the refresh token to obtain a new access token without user interaction.

### HTTP Request to Refresh Token

```bash
curl -X POST https://oauth2.googleapis.com/token \
  -d "client_id=YOUR_CLIENT_ID" \
  -d "client_secret=YOUR_CLIENT_SECRET" \
  -d "refresh_token=YOUR_REFRESH_TOKEN" \
  -d "grant_type=refresh_token"
```

### Response

```json
{
  "access_token": "ya29.a0AfB_byC...",
  "expires_in": 3599,
  "scope": "https://www.googleapis.com/auth/gmail.readonly",
  "token_type": "Bearer"
}
```

Note: The response typically does not include a new refresh token. Your existing refresh token remains valid.

### Python Pattern for GitHub Actions

```python
import os
import json
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

def get_gmail_service():
    """Initialize Gmail API client with automatic token refresh."""
    # Load token from environment variable (GitHub secret)
    token_data = json.loads(os.environ['GMAIL_TOKEN'])

    # Create credentials object
    creds = Credentials.from_authorized_user_info(token_data)

    # Check if token needs refresh
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        # Note: The refreshed token is only in memory
        # For long-running apps, you may want to persist the new token

    # Build and return the Gmail service
    return build('gmail', 'v1', credentials=creds)
```

### Handling Token Refresh in Stateless Environments

In GitHub Actions, each run starts fresh. The token refresh happens in memory and the new access token is used for that run only. This works because:

1. The refresh token stored in secrets remains valid
2. Each run creates a new access token using the refresh token
3. The access token is used for API calls during that run
4. When the run ends, the in-memory access token is discarded
5. The next run repeats the process

---

## Gmail API Scopes

Scopes define what permissions your application has. Choose the minimum scopes needed for your use case.

### Available Scopes

| Scope | Permission | Use Case |
|-------|------------|----------|
| `gmail.readonly` | View email messages and settings | Reading emails, searching inbox |
| `gmail.modify` | Read, compose, send emails; manage labels | Labeling, archiving, marking as read |
| `gmail.compose` | Create, read, update, delete drafts; send emails | Sending emails |
| `gmail.send` | Send emails only | Sending emails without reading |
| `gmail.insert` | Insert and import messages | Adding messages to mailbox |
| `gmail.labels` | Manage mailbox labels | Creating, editing, deleting labels |
| `gmail.settings.basic` | Manage basic settings and filters | Filters, forwarding settings |
| `gmail.settings.sharing` | Manage sensitive mail settings | Delegate access |
| `gmail.metadata` | View message metadata (not body) | Headers, labels, IDs only |
| `mail.google.com` | Full access to Gmail | Complete mailbox control |

### Scopes for Common Operations

**Reading emails (view only)**:
```
https://www.googleapis.com/auth/gmail.readonly
```

**Reading and labeling emails**:
```
https://www.googleapis.com/auth/gmail.modify
```

**Deleting emails permanently**:
```
https://mail.google.com/
```

**Managing labels only**:
```
https://www.googleapis.com/auth/gmail.labels
```

### Scope Categories and Verification

Google categorizes scopes into three levels:

1. **Non-sensitive**: Basic profile information (name, email)
2. **Sensitive**: Access to user data, requires verification
3. **Restricted**: Wide access to user data, requires security assessment

Most Gmail scopes are classified as **restricted**, which means:
- Apps in "Testing" mode have refresh tokens that expire in 7 days
- Production apps require OAuth verification by Google
- Apps that store restricted scope data on servers require annual security assessment

### Restricted Gmail Scopes (Require Verification)

- `https://mail.google.com/`
- `https://www.googleapis.com/auth/gmail.readonly`
- `https://www.googleapis.com/auth/gmail.modify`
- `https://www.googleapis.com/auth/gmail.compose`
- `https://www.googleapis.com/auth/gmail.insert`
- `https://www.googleapis.com/auth/gmail.metadata`

---

## Storing Credentials in GitHub Actions

### Repository Secrets

Store sensitive data as GitHub repository secrets:

1. Go to repository Settings > Secrets and variables > Actions
2. Click "New repository secret"
3. Add secrets for your credentials

### Recommended Secrets Structure

| Secret Name | Content |
|-------------|---------|
| `GMAIL_TOKEN` | Contents of token.json (minified JSON) |
| `GMAIL_CREDENTIALS` | Contents of credentials.json (optional, if needed) |

### Storing token.json as a Secret

Minify the token.json content to a single line before storing:

```bash
# Convert token.json to single line
cat token.json | jq -c .
```

Store the output as `GMAIL_TOKEN` secret.

### Using Secrets in Workflows

```yaml
jobs:
  classify:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Run script
        run: python src/main.py
        env:
          GMAIL_TOKEN: ${{ secrets.GMAIL_TOKEN }}
```

### In Your Python Code

```python
import os
import json
from google.oauth2.credentials import Credentials

def get_credentials():
    token_data = json.loads(os.environ['GMAIL_TOKEN'])
    return Credentials.from_authorized_user_info(token_data)
```

### Security Considerations

- Secrets are encrypted at rest in GitHub
- Secrets are automatically masked in workflow logs
- Secrets are not available to forked repositories by default
- Each line of a secret is masked independently in logs

---

## Token Lifecycle and Expiration

### Access Token Expiration

- **Lifetime**: Approximately 1 hour (3600 seconds)
- **After expiration**: Must be refreshed using the refresh token
- **Behavior**: API calls with expired token return 401 Unauthorized

### Refresh Token Expiration

Refresh tokens can expire or become invalid in these situations:

| Condition | Result |
|-----------|--------|
| **Testing mode** | Expires after 7 days |
| **Production mode** | Does not expire (unless revoked) |
| **User changes password** | Invalidated (for Gmail scopes) |
| **User revokes access** | Immediately invalid |
| **6 months of inactivity** | May be invalidated |
| **100+ refresh tokens issued** | Oldest tokens are invalidated |

### Avoiding 7-Day Expiration

If your app is in "Testing" mode on the OAuth consent screen:
1. Go to Google Cloud Console
2. Navigate to APIs & Services > OAuth consent screen
3. Click "Publish App" to move to production

**Note**: Publishing to production for external apps triggers the verification process for sensitive/restricted scopes.

### Handling Token Expiration in Code

```python
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google.auth.exceptions import RefreshError

def get_valid_credentials(token_data):
    creds = Credentials.from_authorized_user_info(token_data)

    if not creds.valid:
        if creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except RefreshError as e:
                # Refresh token is invalid
                # User needs to re-authorize
                raise Exception(
                    "Refresh token is invalid. User must re-authorize the application."
                ) from e
        else:
            raise Exception("No valid credentials or refresh token")

    return creds
```

### Monitoring Token Health

Signs that your refresh token may be invalid:
- API calls fail with 401 after token refresh
- `RefreshError` exceptions when calling `creds.refresh()`
- Error message mentions "Token has been expired or revoked"

---

## Summary: Key Points for Automated Workflows

1. **One-time setup required**: Generate refresh token locally or via OAuth Playground before deploying to GitHub Actions

2. **Use `access_type=offline`**: Required to receive a refresh token

3. **Use `prompt=consent`**: Ensures refresh token is returned (especially on re-authorization)

4. **Publish to production**: Move out of "Testing" mode to avoid 7-day token expiration

5. **Store tokens securely**: Use GitHub Secrets for all credential data

6. **Choose minimal scopes**: Request only the permissions your app needs

7. **Handle refresh failures**: Implement error handling for cases where refresh tokens become invalid

8. **Token refresh is automatic**: Google's Python libraries handle refresh automatically when you call `creds.refresh(Request())`

---

## Sources

- [Using OAuth 2.0 to Access Google APIs](https://developers.google.com/identity/protocols/oauth2)
- [Using OAuth 2.0 for Web Server Applications](https://developers.google.com/identity/protocols/oauth2/web-server)
- [Implement server-side authorization - Gmail API](https://developers.google.com/workspace/gmail/api/auth/web-server)
- [Choose Gmail API scopes](https://developers.google.com/workspace/gmail/api/auth/scopes)
- [Python quickstart - Gmail API](https://developers.google.com/gmail/api/quickstart/python)
- [Create access credentials - Google Workspace](https://developers.google.com/workspace/guides/create-credentials)
- [Setting up OAuth 2.0 - API Console Help](https://support.google.com/googleapi/answer/6158849?hl=en)
- [OAuth 2.0 Playground](https://developers.google.com/oauthplayground/)
- [Sensitive scope verification](https://developers.google.com/identity/protocols/oauth2/production-readiness/sensitive-scope-verification)
- [Restricted scope verification](https://developers.google.com/identity/protocols/oauth2/production-readiness/restricted-scope-verification)
- [Using secrets in GitHub Actions](https://docs.github.com/en/actions/how-tos/write-workflows/choose-what-workflows-do/use-secrets)
- [Authenticate to Google Cloud - GitHub Actions](https://github.com/google-github-actions/auth)
