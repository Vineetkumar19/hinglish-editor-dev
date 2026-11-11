"""Local-only owner provisioning. Enter the password privately in the terminal."""
import base64
import getpass
import json
from pathlib import Path
from urllib.parse import quote
import time
import uuid
from hinglish_saas.store import Store
from hinglish_saas.security import PASSWORDS,verify_password

ROOT=Path(__file__).resolve().parents[1]


def main():
    folder=ROOT/'cache/storylens-local';values=json.loads((folder/'connection.private.json').read_text())
    password=getpass.getpass('Set your private Storylens owner password (at least 12 characters): ')
    if not 12<=len(password)<=128:raise ValueError('Use 12 to 128 characters.')
    if password!=getpass.getpass('Confirm password: '):raise ValueError('Passwords did not match.')
    store=Store(folder/'app',values['database_url']);email='vineetkd418@gmail.com'
    try:
        existing=store.one('SELECT id,password FROM users WHERE email=?',(email,))
        if existing:
            if not verify_password(existing['password'],password):raise ValueError('An owner account already exists. Enter its existing password or use account recovery. No credentials were overwritten.')
            store.execute('UPDATE users SET verified=1 WHERE id=?',(existing['id'],))
        else:store.execute('INSERT INTO users VALUES(?,?,?,?,?)',(uuid.uuid4().hex,email,PASSWORDS.hash(password),1,time.time()))
        setup={'owner_email':email,'secret':values['support_totp_secret'],'authenticator_uri':'otpauth://totp/'+quote('Storylens:'+email)+'?secret='+values['support_totp_secret']+'&issuer=Storylens&digits=6&period=30'}
        (folder/'owner-authenticator.private.json').write_text(json.dumps(setup,indent=2),encoding='utf-8')
        print('Owner account created. Add the key from cache/storylens-local/owner-authenticator.private.json to your authenticator. Keep that file private. Then sign in at http://127.0.0.1:8788/dashboard .')
    finally:store.close()


if __name__=='__main__':main()
