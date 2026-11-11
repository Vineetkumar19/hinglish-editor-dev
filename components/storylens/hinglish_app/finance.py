"""Loopback-only, read-only finance workspace for StoryLens Desktop."""

from datetime import datetime, timedelta, timezone
from http.client import HTTPConnection, HTTPException
from http.server import BaseHTTPRequestHandler
import json
from pathlib import Path
import re
import threading
from urllib.parse import parse_qs, urlsplit

from .server import LocalHTTPServer

PORT = 43822
IST = timezone(timedelta(hours=5, minutes=30))
UI = Path(__file__).with_name('finance_ui')
LIMIT = 30_000_000  # The Pocket Tracker companion bounds snapshots to this size.
FILES = {
    '/': ('index.html', 'text/html; charset=utf-8'),
    '/finance.js': ('finance.js', 'text/javascript; charset=utf-8'),
    '/finance.css': ('finance.css', 'text/css; charset=utf-8'),
    '/geist-latin-400-normal.woff2': ('geist-latin-400-normal.woff2', 'font/woff2'),
    '/geist-latin-600-normal.woff2': ('geist-latin-600-normal.woff2', 'font/woff2'),
    '/geist-latin-700-normal.woff2': ('geist-latin-700-normal.woff2', 'font/woff2'),
}


def upstream(port, path, timeout):
    conn = HTTPConnection('127.0.0.1', port, timeout=timeout)
    try:
        conn.request('GET', path, headers={'Accept': 'application/json'})
        response = conn.getresponse()
        if response.status != 200 or not response.getheader('Content-Type', '').startswith('application/json'):
            raise ValueError('Source unavailable')
        payload = response.read(LIMIT + 1)
        if len(payload) > LIMIT:
            raise ValueError('Source response exceeds local limit')
        return json.loads(payload)
    finally:
        conn.close()


def pocket_summary(snapshot, month):
    def when(row):
        return datetime.fromtimestamp(row['time'] / 1000, IST)

    rows = [row for row in snapshot['transactions'] if when(row).strftime('%Y-%m') == month]
    cashflow = [row for row in rows if not row.get('transfer')]
    plan = snapshot['plan']
    return {
        'count': len(rows),
        'moneyIn': sum(row['amount'] for row in cashflow if row['direction'] == 'credit'),
        'moneyOut': sum(row['amount'] for row in cashflow if row['direction'] == 'debit'),
        'creditSpend': sum(row['amount'] for row in cashflow
                           if row['direction'] == 'debit' and row.get('instrument') == 'credit_card'),
        'recurring': sum(row['amount'] for row in plan['recurring'] if row['active']),
        'budget': plan['budget'],
    }


class FinanceHandler(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def send(self, status, data, mime):
        self.send_response(status)
        self.send_header('Content-Type', mime)
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Referrer-Policy', 'no-referrer')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Content-Security-Policy',
                         "default-src 'none'; script-src 'self'; style-src 'self'; font-src 'self'; connect-src 'self'; "
                         "base-uri 'none'; form-action 'none'; frame-ancestors "
                         "http://127.0.0.1:8765 http://localhost:8765")
        self.end_headers()
        self.wfile.write(data)

    def reply(self, status, data):
        self.send(status, json.dumps(data).encode(), 'application/json; charset=utf-8')

    def do_GET(self):
        port = self.server.server_port
        hosts = {f'127.0.0.1:{port}', f'localhost:{port}'}
        if self.headers.get('Host') not in hosts:
            return self.reply(403, {'error': 'Local host only'})
        target = urlsplit(self.path)
        if target.path in FILES:
            filename, mime = FILES[target.path]
            return self.send(200, (UI / filename).read_bytes(), mime)
        if target.path not in ('/api/finance-tracker', '/api/pocket'):
            return self.reply(404, {'error': 'Page unavailable'})
        origin = self.headers.get('Origin')
        if (self.headers.get('X-StoryLens-Finance') != '1'
                or (origin is not None and origin not in {f'http://{host}' for host in hosts})
                or self.headers.get('Sec-Fetch-Site') not in (None, 'same-origin')):
            return self.reply(403, {'error': 'Open the local Finance workspace'})
        try:
            if target.path == '/api/finance-tracker':
                return self.reply(200, upstream(4310, '/api/finance-summary', 4))
            month = parse_qs(target.query).get('month', [''])[0]
            if not re.fullmatch(r'\d{4}-(0[1-9]|1[0-2])', month):
                return self.reply(400, {'error': 'Select a valid month'})
            return self.reply(200, pocket_summary(upstream(43820, '/api/snapshot', 68), month))
        except (OSError, HTTPException, ValueError, KeyError, TypeError, OverflowError):
            return self.reply(503, {'error': 'Source unavailable'})


def create_server(port=PORT):
    return LocalHTTPServer(('127.0.0.1', port), FinanceHandler)


def start():
    try:
        server = create_server()
    except OSError:
        return None  # An independently launched companion can already own the port.
    threading.Thread(target=server.serve_forever, name='storylens-finance', daemon=True).start()
    return server


if __name__ == '__main__':
    with create_server() as server:
        server.serve_forever()

