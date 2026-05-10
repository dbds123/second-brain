"""
RWTH Mail Bridge — lokaler IMAP-zu-HTTP Proxy
Starten: python rwth_mail.py
Läuft auf http://localhost:3334
"""

import imaplib
import email
import email.header
import json
import time
import threading
import getpass
from http.server import HTTPServer, BaseHTTPRequestHandler
from email.utils import parsedate_to_datetime
from datetime import datetime, timezone

# ── Config ────────────────────────────────────────────────────────────────────
IMAP_HOST  = 'mail.rwth-aachen.de'
IMAP_PORT  = 993
HTTP_PORT  = 3334
CACHE_TTL  = 120  # Sekunden zwischen IMAP-Abrufen

# ── Cache ─────────────────────────────────────────────────────────────────────
cache = {'mails': [], 'last_fetch': 0, 'error': None}
credentials = {'user': None, 'password': None}

def decode_header_value(val):
    if not val:
        return ''
    parts = email.header.decode_header(val)
    result = []
    for part, enc in parts:
        if isinstance(part, bytes):
            result.append(part.decode(enc or 'utf-8', errors='replace'))
        else:
            result.append(part)
    return ''.join(result)

def zeit_formatieren(ts):
    try:
        dt = parsedate_to_datetime(ts)
        now = datetime.now(timezone.utc)
        diff = now - dt
        min_ = int(diff.total_seconds() / 60)
        h    = int(diff.total_seconds() / 3600)
        d    = int(diff.total_seconds() / 86400)
        if min_ < 2:   return 'gerade'
        if min_ < 60:  return f'{min_}m'
        if h < 24:     return f'{h}h'
        if d == 1:     return 'gestern'
        return f'{d}d'
    except:
        return ''

def fetch_mails():
    user = credentials['user']
    pwd  = credentials['password']
    if not user or not pwd:
        return

    try:
        mail = imaplib.IMAP4_SSL(IMAP_HOST, IMAP_PORT)
        mail.login(user, pwd)
        mail.select('INBOX')

        _, data = mail.search(None, 'ALL')
        ids = data[0].split()
        ids = ids[-15:]  # letzte 15

        mails = []
        for mid in reversed(ids):
            _, msg_data = mail.fetch(mid, '(RFC822.HEADER FLAGS)')
            raw = msg_data[0][1]
            msg = email.message_from_bytes(raw)

            flags_raw = msg_data[0][0].decode() if isinstance(msg_data[0][0], bytes) else str(msg_data[0][0])
            gelesen   = '\\Seen' in flags_raw

            absender = decode_header_value(msg.get('From', ''))
            # Name aus "Name <email>" extrahieren
            import re
            m = re.match(r'^"?([^"<]+?)"?\s*(?:<.*>)?$', absender)
            name = m.group(1).strip() if m else absender

            mails.append({
                'id':       mid.decode(),
                'absender': name,
                'betreff':  decode_header_value(msg.get('Subject', '(kein Betreff)')),
                'zeit':     zeit_formatieren(msg.get('Date', '')),
                'gelesen':  gelesen,
                'wichtig':  False,
            })

        mail.logout()
        cache['mails']      = mails
        cache['last_fetch'] = time.time()
        cache['error']      = None
        print(f'[RWTH Mail] {len(mails)} Mails geladen.')

    except imaplib.IMAP4.error as e:
        cache['error'] = f'Login fehlgeschlagen: {e}'
        print(f'[RWTH Mail] Fehler: {e}')
    except Exception as e:
        cache['error'] = str(e)
        print(f'[RWTH Mail] Fehler: {e}')

def background_fetch():
    while True:
        if time.time() - cache['last_fetch'] > CACHE_TTL:
            fetch_mails()
        time.sleep(30)

# ── HTTP Handler ──────────────────────────────────────────────────────────────
class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/mails':
            body = json.dumps({
                'mails': cache['mails'],
                'error': cache['error'],
                'last_fetch': cache['last_fetch'],
            }).encode()
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.send_header('Content-Length', len(body))
            self.end_headers()
            self.wfile.write(body)
        elif self.path == '/ping':
            self.send_response(200)
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(b'ok')
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        pass  # Logs unterdrücken

# ── Start ─────────────────────────────────────────────────────────────────────
if __name__ == '__main__':
    print('╔══════════════════════════════════════╗')
    print('║      RWTH Mail Bridge v1.0           ║')
    print('╚══════════════════════════════════════╝')
    print()

    credentials['user']     = input('RWTH Benutzername (ab123456@rwth-aachen.de): ').strip()
    credentials['password'] = getpass.getpass('RWTH Passwort: ')

    print('\nVerbinde mit IMAP...')
    fetch_mails()

    if cache['error']:
        print(f'Fehler: {cache["error"]}')
        input('Enter zum Beenden.')
    else:
        t = threading.Thread(target=background_fetch, daemon=True)
        t.start()

        print(f'Mail-Bridge läuft auf http://localhost:{HTTP_PORT}')
        print('Fenster offen lassen. Strg+C zum Beenden.\n')
        try:
            HTTPServer(('localhost', HTTP_PORT), Handler).serve_forever()
        except KeyboardInterrupt:
            print('\nBeendet.')
