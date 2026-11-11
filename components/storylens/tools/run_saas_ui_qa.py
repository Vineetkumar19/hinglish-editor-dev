"""Isolated loopback UI test service. No production users, mail or payments."""
from pathlib import Path
import tempfile
import uvicorn
import time
import uuid
from hinglish_saas.app import create_app
from hinglish_saas.config import Settings
from hinglish_saas.security import PASSWORDS


if __name__=='__main__':
    folder=Path(__file__).resolve().parents[1]/'output/test-temp';folder.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(dir=folder,prefix='account-ui-') as data:
        app=create_app(Settings(data_dir=data,origin='http://127.0.0.1:8790',support_admin_emails=('operator@example.test',),support_totp_secret='JBSWY3DPEHPK3PXP'))
        # Explicit loopback-only interface fixtures. No email is sent and these
        # users are never created in the owner's real account database.
        for email in ('customer@example.test','operator@example.test'):
            app.state.store.execute('INSERT INTO users VALUES(?,?,?,?,?)',(uuid.uuid4().hex,email,PASSWORDS.hash('Interface test password 1234!'),1,time.time()))
        uvicorn.run(app,host='127.0.0.1',port=8790,access_log=False,proxy_headers=False)
