"""Retryable Gmail notification worker. No messages are sent without configured SMTP."""
import argparse
from email.message import EmailMessage
from email.utils import formatdate
import smtplib
import ssl
import time
import uuid
from .config import Settings
from .store import Store


def send(settings,row):
    message=EmailMessage();message['From']=settings.mail_from;message['To']=row['recipient']
    message['Reply-To']=settings.support_email;message['Subject']=row['subject']
    message['Date']=formatdate(localtime=False);message['Message-ID']='<hinglish-support-'+row['id']+'@'+settings.mail_from.split('@')[-1]+'>'
    message.set_content(row['body'])
    with smtplib.SMTP(settings.smtp_host,settings.smtp_port,timeout=15) as server:
        server.starttls(context=ssl.create_default_context())
        if settings.smtp_user:server.login(settings.smtp_user,settings.smtp_password)
        server.send_message(message)


def run_once(settings,sender=send,store=None):
    if not settings.smtp_host or not settings.mail_from:return False
    store=store or Store(settings.data_dir,settings.database_url);now=time.time();claim=uuid.uuid4().hex
    with store.connect(immediate=True) as db:
        # A process can crash during its final attempt, before recording failure.
        # Expose that exhausted lease instead of leaving it 'sending' forever.
        db.execute("UPDATE support_outbox SET state='failed',lease_until=0 WHERE state='sending' AND lease_until<? AND attempts>=8",(now,))
        row=db.execute("SELECT * FROM support_outbox WHERE ((state='pending' AND available<=?) OR (state='sending' AND lease_until<?)) AND attempts<8 ORDER BY created LIMIT 1",(now,now)).fetchone()
        if not row:return False
        db.execute("UPDATE support_outbox SET state='sending',claim=?,lease_until=?,attempts=attempts+1 WHERE id=?",(claim,now+120,row['id']))
    try:sender(settings,dict(row))
    except Exception:
        store.execute("UPDATE support_outbox SET state=CASE WHEN attempts>=8 THEN 'failed' ELSE 'pending' END,available=?,lease_until=0 WHERE id=? AND claim=?",(now+min(3600,30*2**row['attempts']),row['id'],claim))
        return True
    store.execute("UPDATE support_outbox SET state='sent',lease_until=0 WHERE id=? AND claim=?",(row['id'],claim));return True


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--once',action='store_true');args=parser.parse_args();settings=Settings.from_env()
    store=Store(settings.data_dir,settings.database_url)
    while True:
        worked=run_once(settings,store=store)
        if args.once:break
        if not worked:time.sleep(10)
