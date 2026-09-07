#!/usr/bin/env python3
"""Thin CLI over GmailService for the inbox-cleanup skill.

Reads .env and tokens/ from --root (default: this repo). Output is JSON on stdout.

  gmail_cli.py labels  <account>
  gmail_cli.py profile <account>
  gmail_cli.py search  <account> --query 'in:inbox newer_than:30d' [--max 150]
  gmail_cli.py ensure-label <account> 'AI/reviewed'
  gmail_cli.py apply   <account> --plan plan.json [--dry-run]

<account> is the ACCOUNT_N_NAME from .env, or N itself.

plan.json: a list of {"threadId": ..., "add": [labelId...], "remove": [labelId...], "note": "..."}
or the same keyed by "id" (message id). A threadId entry is applied to every message in the
thread. Writes go through messages.modify only — no delete, no trash, no send.
"""
import argparse
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent


def _load(root: Path, account: str):
    from dotenv import load_dotenv
    load_dotenv(root / '.env')
    sys.path.insert(0, str(HERE))
    from src.gmail_service import GmailService  # noqa: E402
    n = 1
    while os.environ.get(f'ACCOUNT_{n}_NAME'):
        if account in (os.environ[f'ACCOUNT_{n}_NAME'], str(n)):
            token = (root / 'tokens' / f'{n}.json').read_text()
            return GmailService(token), os.environ.get(f'ACCOUNT_{n}_EMAIL', '')
        n += 1
    sys.exit(f'unknown account {account!r}; names come from ACCOUNT_N_NAME in {root}/.env')


def _headers(msg):
    h = {x['name'].lower(): x['value'] for x in msg.get('payload', {}).get('headers', [])}
    return {
        'id': msg['id'], 'threadId': msg['threadId'], 'labelIds': msg.get('labelIds', []),
        'from': h.get('from', ''), 'subject': h.get('subject', ''), 'date': h.get('date', ''),
        'snippet': msg.get('snippet', ''),
    }


def cmd_labels(svc, a):
    print(json.dumps({l['name']: l['id'] for l in svc.list_labels()}, indent=2))


def cmd_profile(svc, a):
    print(json.dumps(svc.service.users().getProfile(userId='me').execute(), indent=2))


def cmd_search(svc, a):
    api = svc.service.users().messages()
    out, token = [], None
    while len(out) < a.max:
        r = api.list(userId='me', q=a.query, maxResults=min(100, a.max - len(out)), pageToken=token).execute()
        for m in r.get('messages', []):
            full = api.get(userId='me', id=m['id'], format='metadata',
                           metadataHeaders=['From', 'Subject', 'Date']).execute()
            out.append(_headers(full))
        token = r.get('nextPageToken')
        if not token:
            break
    print(json.dumps({'count': len(out), 'messages': out}, indent=2))


def cmd_ensure_label(svc, a):
    r = svc.get_or_create_label(a.name)
    print(json.dumps({'name': a.name, **r}))


def cmd_apply(svc, a):
    plan = json.loads(Path(a.plan).read_text())
    api = svc.service.users()
    results = []
    # Entries may name a label as "name:AI/reviewed"; resolve (creating if needed) once per run.
    # On a dry run nothing is created — the name is left as-is so the plan stays inspectable.
    resolved = {}

    def _ids(items):
        out = []
        for x in items:
            if x.startswith('name:'):
                nm = x[5:]
                if nm not in resolved:
                    resolved[nm] = x if a.dry_run else svc.get_or_create_label(nm)['labelId']
                out.append(resolved[nm])
            else:
                out.append(x)
        return out

    for entry in plan:
        add, remove = _ids(entry.get('add', [])), _ids(entry.get('remove', []))
        if 'threadId' in entry:
            t = api.threads().get(userId='me', id=entry['threadId'], format='metadata',
                                  metadataHeaders=['From', 'Subject', 'Date']).execute()
            msgs = [_headers(m) for m in t.get('messages', [])]
        else:
            msgs = [_headers(api.messages().get(userId='me', id=entry['id'], format='metadata',
                                                metadataHeaders=['From', 'Subject', 'Date']).execute())]
        for m in msgs:
            rec = {**m, 'add': add, 'remove': remove, 'note': entry.get('note', ''), 'applied': False}
            rec.pop('snippet', None)
            if not a.dry_run:
                body = {}
                if add:
                    body['addLabelIds'] = add
                if remove:
                    body['removeLabelIds'] = remove
                if body:
                    api.messages().modify(userId='me', id=m['id'], body=body).execute()
                    rec['applied'] = True
            results.append(rec)
    print(json.dumps({'dry_run': a.dry_run, 'entries': len(plan), 'messages': len(results),
                      'applied': sum(r['applied'] for r in results), 'results': results}, indent=2))


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--root', default=str(HERE), help='dir holding .env and tokens/ (default: this repo)')
    sub = p.add_subparsers(dest='cmd', required=True)
    for name in ('labels', 'profile'):
        s = sub.add_parser(name); s.add_argument('account')
    s = sub.add_parser('search'); s.add_argument('account'); s.add_argument('--query', required=True); s.add_argument('--max', type=int, default=150)
    s = sub.add_parser('ensure-label'); s.add_argument('account'); s.add_argument('name')
    s = sub.add_parser('apply'); s.add_argument('account'); s.add_argument('--plan', required=True); s.add_argument('--dry-run', action='store_true')
    a = p.parse_args()
    svc, email = _load(Path(a.root), a.account)
    print(f'# account {a.account} = {email}', file=sys.stderr)
    globals()['cmd_' + a.cmd.replace('-', '_')](svc, a)


if __name__ == '__main__':
    main()
