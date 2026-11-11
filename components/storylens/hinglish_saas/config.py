from dataclasses import dataclass, field
from pathlib import Path
import os
import json
import hashlib
import re
import base64
from urllib.parse import urlparse

EDIT_TOOLS = ('clean', 'script', 'captions', 'broll', 'visuals', 'zoom', 'sound',
              'eyecontact', 'shorts', 'aiimage', 'aivideo', 'motion')
PLANS = {'monthly': {'amount': 200000, 'months': 1, 'label': 'Monthly'},
         'annual': {'amount': 2000000, 'months': 12, 'label': 'Annual'}}
EDITIONS = {'desktop': {'label': 'Desktop', 'hosts': ['standalone']},
            'plugins': {'label': 'Editor Plugins', 'hosts': ['aftereffects', 'premiere', 'resolve']}}


@dataclass
class Settings:
    data_dir: Path = Path('cache/saas')
    origin: str = 'http://127.0.0.1:8788'
    production: bool = False
    qa_mode: bool = False
    database_url: str = field(default='',repr=False)
    sales_enabled: bool = False
    worker_enabled: bool = False
    enabled_tools: tuple = ('clean',)
    key_id: str = ''
    key_secret: str = ''
    webhook_secret: str = ''
    smtp_host: str = ''
    smtp_port: int = 587
    smtp_user: str = ''
    smtp_password: str = ''
    mail_from: str = ''
    support_email: str = 'vineetkd418@gmail.com'
    support_admin_emails: tuple = ('vineetkd418@gmail.com',)
    support_totp_secret: str = ''
    license_private_key: str = ''  # Base64url raw Ed25519 private key; environment secret only.
    device_limit: int = 1
    max_upload_bytes: int = 2 * 1024**3
    storage_bytes: int = 10 * 1024**3
    max_jobs_month: int = 20
    session_seconds: int = 12 * 3600
    job_timeout: int = 3600

    def __post_init__(self):
        self.data_dir = Path(self.data_dir).resolve()
        if self.production and self.qa_mode:raise ValueError('Fixture mode cannot run in production.')
        if self.database_url:
            from sqlalchemy.engine import make_url
            try:
                db=make_url(self.database_url)
                if db.drivername!='mysql+pymysql' or not db.database or not db.username or not db.host:raise ValueError('Invalid MySQL URL.')
                if self.production and db.host not in ('localhost','127.0.0.1'):
                    if not db.query.get('ssl_ca') or any(str(db.query.get(key,'')).lower() not in ('true','1') for key in ('ssl_verify_cert','ssl_verify_identity')):raise ValueError('Remote MySQL requires CA and verified server identity.')
            except Exception:raise ValueError('Configure a mysql+pymysql database URL; use TLS for remote production MySQL.')
        if self.production and not self.database_url:raise ValueError('Production Storylens requires MySQL; SQLite is development-only.')
        parsed = urlparse(self.origin)
        if parsed.scheme not in ('http', 'https') or not parsed.hostname or parsed.path or parsed.query or parsed.fragment:
            raise ValueError('Set one exact origin without a trailing slash.')
        if self.production and (parsed.scheme != 'https' or parsed.hostname in ('localhost', '127.0.0.1')):
            raise ValueError('Production requires a public HTTPS origin.')
        if self.production and self.worker_enabled:
            raise ValueError('Hosted processing is disabled for commercial single-computer subscriptions until browser-to-device proof is implemented. Use the licensed local editor or plugins.')
        if not set(self.enabled_tools).issubset(EDIT_TOOLS):
            raise ValueError('Unknown editing tool in enabled_tools.')
        if self.max_upload_bytes<=0 or self.storage_bytes<self.max_upload_bytes or not 1<=self.max_jobs_month<=10000 or not 60<=self.job_timeout<=86400:
            raise ValueError('Set positive storage/job limits and a bounded processing timeout.')
        if self.production and self.sales_enabled:
            missing = [k for k in ('key_id', 'key_secret', 'webhook_secret', 'smtp_host', 'mail_from', 'support_email','support_totp_secret') if not getattr(self,k)]
            if missing or not self.license_private_key:
                raise ValueError('Live sales require payments, email, support and a license signing key.')
            try:
                release=json.loads((self.data_dir/'releases/release.json').read_text(encoding='utf-8'))
                if release.get('release_ready') is not True or not {'desktop','plugins'} <= {a.get('edition') for a in release.get('artifacts',[])}:
                    raise ValueError('Missing verified releases.')
                for artifact in release['artifacts']:
                    if not all(isinstance(artifact.get(k),str) and artifact[k] for k in ('id','label','edition','version','file','sha256')):raise ValueError('Incomplete artifact.')
                    file=artifact['file'];folder=self.data_dir/'releases';path=(folder/file).resolve()
                    if not path.is_relative_to(folder.resolve()) or Path(file).name!=file or '\\' in file or '/' in file:raise ValueError('Invalid release path.')
                    checksum=hashlib.sha256()
                    with path.open('rb') as handle:
                        for block in iter(lambda:handle.read(1024**2),b''):checksum.update(block)
                    if checksum.hexdigest()!=artifact['sha256']:raise ValueError('Release checksum failed.')
            except (OSError,ValueError,TypeError,KeyError,AttributeError):
                raise ValueError('Live sales require verified Desktop and Plugin installers. Do not sell an unfinished release.')
        if self.device_limit != 1:
            raise ValueError('Each subscription is limited to exactly one computer.')
        if not re.fullmatch(r'[A-Za-z0-9._%+\-]+@gmail\.com',self.support_email):
            raise ValueError('Use the owner Gmail support address.')
        self.support_admin_emails=tuple(email.strip().lower() for email in self.support_admin_emails)
        if self.support_totp_secret:
            try:
                key=base64.b32decode(self.support_totp_secret.upper()+'='*((-len(self.support_totp_secret))%8),casefold=True)
                if len(key)<10:raise ValueError('Short operator MFA key.')
            except (ValueError,base64.binascii.Error):
                raise ValueError('Set a valid Base32 support authenticator key of at least 80 bits.')
        if any(not re.fullmatch(r'[^\s@\x00-\x1f]+@[^\s@\x00-\x1f]+\.[^\s@\x00-\x1f]+',email) for email in self.support_admin_emails):
            raise ValueError('Invalid support operator address.')

    @classmethod
    def from_env(cls):
        def yes(key): return os.environ.get('HINGLISH_SAAS_'+key, '0') == '1'
        def value(key, default=''): return os.environ.get('HINGLISH_SAAS_'+key, default)
        return cls(data_dir=Path(value('DATA_DIR', 'cache/saas')), origin=value('ORIGIN','http://127.0.0.1:8788'),database_url=value('DATABASE_URL'),
                   production=yes('PRODUCTION'), sales_enabled=yes('SALES_ENABLED'), worker_enabled=yes('WORKER_ENABLED'),
                   enabled_tools=tuple(x.strip() for x in value('TOOLS','clean').split(',') if x.strip()),
                   key_id=value('RAZORPAY_KEY_ID'), key_secret=value('RAZORPAY_KEY_SECRET'), webhook_secret=value('RAZORPAY_WEBHOOK_SECRET'),
                   smtp_host=value('SMTP_HOST'), smtp_port=int(value('SMTP_PORT','587')), smtp_user=value('SMTP_USER'),
                   smtp_password=value('SMTP_PASSWORD'), mail_from=value('MAIL_FROM'), support_email=value('SUPPORT_EMAIL','vineetkd418@gmail.com'),
                   support_admin_emails=tuple(value('SUPPORT_ADMIN_EMAILS','vineetkd418@gmail.com').split(',')),support_totp_secret=value('SUPPORT_TOTP_SECRET'),
                   license_private_key=value('LICENSE_PRIVATE_KEY'), device_limit=int(value('DEVICE_LIMIT','1')),
                   max_upload_bytes=int(value('UPLOAD_LIMIT_GB','2'))*1024**3,storage_bytes=int(value('UPLOAD_STORAGE_GB','10'))*1024**3,
                   max_jobs_month=int(value('JOBS_MONTH','20')),job_timeout=int(value('JOB_TIMEOUT_SECONDS','3600')))
