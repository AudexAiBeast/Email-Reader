#!/usr/bin/env python3
"""Simple IMAP mail reader that uses credentials from environment variables.

Environment variables:
  EMAIL_USER    - email address / username
  EMAIL_PASS    - password or app password
  IMAP_SERVER   - IMAP server (default: imap.gmail.com)
  IMAP_PORT     - IMAP port (default: 993)
  MAILBOX       - mailbox to select (default: INBOX)

Usage examples:
  Set env vars then run:
    python mail_reader.py --limit 5

For Gmail use an app password and IMAP_SERVER=imap.gmail.com.
"""
import os
import imaplib
import email
import argparse
from email import policy
from email.header import make_header, decode_header
from pathlib import Path

# Try to load .env file if python-dotenv is installed
try:
    from dotenv import load_dotenv
    load_dotenv(dotenv_path=Path('.env'))
except Exception:
    pass


def getenv(name, default=None):
    v = os.environ.get(name)
    return v if v is not None else default


def decode_hdr(value):
    if not value:
        return ""
    try:
        return str(make_header(decode_header(value)))
    except Exception:
        return value


def connect_imap(server, port, use_ssl=True):
    if use_ssl:
        return imaplib.IMAP4_SSL(server, port)
    return imaplib.IMAP4(server, port)


def fetch_messages(imap, mailbox, limit, unseen, mark_read, save_attachments):
    imap.select(mailbox)
    criteria = '(UNSEEN)' if unseen else 'ALL'
    typ, data = imap.search(None, criteria)
    if typ != 'OK':
        raise RuntimeError('Search failed: ' + str(data))

    ids = data[0].split()
    if not ids:
        print('No messages found.')
        return

    # keep only the last `limit` messages
    if limit and len(ids) > limit:
        ids = ids[-limit:]

    for num in ids:
        typ, msg_data = imap.fetch(num, '(RFC822)')
        if typ != 'OK':
            print(f'Failed to fetch message {num.decode() or num}')
            continue

        raw = msg_data[0][1]
        msg = email.message_from_bytes(raw, policy=policy.default)
        subject = decode_hdr(msg['subject'])
        sender = decode_hdr(msg['from'])
        date = msg['date'] or ''

        # extract a short snippet
        snippet = ''
        if msg.is_multipart():
            for part in msg.walk():
                if part.get_content_type() == 'text/plain' and part.get_content_disposition() is None:
                    snippet = part.get_content().strip()
                    break
        else:
            if msg.get_content_type() == 'text/plain':
                snippet = msg.get_content().strip()

        snippet = snippet.replace('\r', ' ').replace('\n', ' ')[:200]

        print('---')
        print(f'ID: {num.decode()}')
        print(f'From: {sender}')
        print(f'Subject: {subject}')
        print(f'Date: {date}')
        if snippet:
            print(f'Snippet: {snippet}')

        # attachments
        if save_attachments:
            save_path = Path(save_attachments)
            save_path.mkdir(parents=True, exist_ok=True)
            for part in msg.iter_attachments():
                filename = part.get_filename()
                if not filename:
                    continue
                data = part.get_content()
                out = save_path / filename
                with open(out, 'wb') as fh:
                    if isinstance(data, bytes):
                        fh.write(data)
                    else:
                        fh.write(data.encode('utf-8', errors='ignore'))
                print(f'Saved attachment: {out}')

        if mark_read:
            imap.store(num, '+FLAGS', '\\Seen')


def main():
    parser = argparse.ArgumentParser(description='Read mail via IMAP using env credentials')
    parser.add_argument('--limit', '-n', type=int, default=10, help='Number of recent messages to show')
    parser.add_argument('--unseen', action='store_true', help='Only fetch unseen messages')
    parser.add_argument('--mark-read', action='store_true', help='Mark fetched messages as read')
    parser.add_argument('--save-attachments', '-a', help='Directory to save attachments')
    parser.add_argument('--mailbox', '-m', help='Mailbox to select (overrides MAILBOX env)')
    args = parser.parse_args()

    user = getenv('EMAIL_USER')
    password = getenv('EMAIL_PASS')
    server = getenv('IMAP_SERVER', 'imap.gmail.com')
    port = int(getenv('IMAP_PORT', '993'))
    mailbox = args.mailbox or getenv('MAILBOX', 'INBOX')

    if not user or not password:
        print('Missing EMAIL_USER or EMAIL_PASS environment variables.')
        return

    try:
        imap = connect_imap(server, port, use_ssl=True)
        imap.login(user, password)
    except Exception as e:
        print('IMAP connection/login failed:', e)
        return

    try:
        fetch_messages(imap, mailbox, args.limit, args.unseen, args.mark_read, args.save_attachments)
    finally:
        try:
            imap.logout()
        except Exception:
            pass


if __name__ == '__main__':
    main()
