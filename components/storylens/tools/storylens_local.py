"""Run a separate loopback-only Storylens MySQL instance and account service.

Never touches the existing MySQL80 service or its data. Secrets stay in an ACL-
restricted local file. --qa creates explicitly labelled fixture users only.
"""
import argparse
import atexit
import base64
import json
import os
from pathlib import Path
import secrets
import subprocess
import threading
import time
import uuid
import pymysql
import uvicorn
from hinglish_saas.config import Settings
from hinglish_saas.app import create_app
from hinglish_saas.security import PASSWORDS

ROOT=Path(__file__).resolve().parents[1]


def private(folder):
    folder.mkdir(parents=True,exist_ok=True)
    if os.name=='nt':
        identity=os.environ.get('USERDOMAIN','')+'\\'+os.environ['USERNAME']
        subprocess.run(['icacls',str(folder),'/inheritance:r','/grant:r',identity+':(OI)(CI)F'],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    else:folder.chmod(0o700)


def start(folder,port):
    private(folder);config=folder/'connection.private.json'
    if config.exists():values=json.loads(config.read_text())
    else:
        values={'root_password':secrets.token_urlsafe(32),'app_password':secrets.token_urlsafe(32),
            'support_totp_secret':base64.b32encode(secrets.token_bytes(20)).decode(),'database_port':port}
        config.write_text(json.dumps(values,indent=2),encoding='utf-8')
    if values['database_port']!=port:raise ValueError('Use the original database port for this data folder.')
    base=Path(r'C:\Program Files\MySQL\MySQL Server 8.0');binary=base/'bin/mysqld.exe'
    if not binary.is_file():raise ValueError('MySQL Server 8.0 is required. Set up an external MySQL connection as described in the deployment guide.')
    data=folder/'mysql-data';log=folder/'mysql.log'
    options=['--no-defaults','--basedir='+str(base),'--datadir='+str(data),'--log-error='+str(log)]
    initialized=(data/'mysql').exists()
    if not initialized:
        print('Initializing a separate Storylens MySQL database…',flush=True)
        subprocess.run([str(binary),*options,'--initialize-insecure'],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    process=subprocess.Popen([str(binary),*options,'--bind-address=127.0.0.1','--port='+str(port),
        '--mysqlx=OFF','--innodb-buffer-pool-size=67108864','--max-connections=50','--performance-schema=OFF',
        '--skip-log-bin','--innodb-flush-log-at-trx-commit=1'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
        creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    atexit.register(lambda:process.terminate() if process.poll() is None else None)
    connection=None
    for _ in range(80):
        if process.poll() is not None:raise RuntimeError('The separate MySQL instance stopped. See its local mysql.log.')
        try:
            connection=pymysql.connect(host='127.0.0.1',port=port,user='root',password=values['root_password'] if initialized else '',connect_timeout=1,autocommit=True);break
        except pymysql.OperationalError:time.sleep(.25)
    if connection is None:raise RuntimeError('MySQL startup timed out.')
    with connection:
        with connection.cursor() as cursor:
            if not initialized:cursor.execute("ALTER USER 'root'@'localhost' IDENTIFIED BY %s",(values['root_password'],))
            cursor.execute('CREATE DATABASE IF NOT EXISTS storylens CHARACTER SET utf8mb4 COLLATE utf8mb4_bin')
            cursor.execute("CREATE USER IF NOT EXISTS 'storylens_app'@'127.0.0.1' IDENTIFIED BY %s",(values['app_password'],))
            cursor.execute("GRANT SELECT,INSERT,UPDATE,DELETE,CREATE,ALTER,INDEX,REFERENCES ON storylens.* TO 'storylens_app'@'127.0.0.1'")
    values['database_url']='mysql+pymysql://storylens_app:'+values['app_password']+'@127.0.0.1:'+str(port)+'/storylens'
    config.write_text(json.dumps(values,indent=2),encoding='utf-8')
    return values,process


def fixtures(app):
    store=app.state.store;password=PASSWORDS.hash('Storylens fixture password 1234!');now=time.time()
    emails=['operator@example.test','customer@example.test']+['viewer'+str(i)+'@example.test' for i in range(1,30)]
    with store.connect(immediate=True) as db:
        for email in emails:
            if db.execute('SELECT id FROM users WHERE email=?',(email,)).fetchone():continue
            uid=uuid.uuid4().hex;db.execute('INSERT INTO users VALUES(?,?,?,?,?)',(uid,email,password,1,now))
            if email!='operator@example.test':db.execute("INSERT INTO orders(id,user_id,plan,amount,state,payment_id,starts,ends,created,edition) VALUES(?,?,?,?,'paid',?,?,?,?,?)",('order_fixture_'+uid,uid,'monthly',200000,'pay_fixture_'+uid,now-10,now+30*86400,now,'bundle'))


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--qa',action='store_true');parser.add_argument('--db-port',type=int,default=3308);parser.add_argument('--port',type=int,default=8788);parser.add_argument('--migrate-from',type=Path)
    args=parser.parse_args();folder=ROOT/('output/storylens/qa-mysql' if args.qa else 'cache/storylens-local')
    values,process=start(folder,args.db_port)
    settings=Settings(data_dir=folder/'app',origin='http://127.0.0.1:'+str(args.port),database_url=values['database_url'],qa_mode=args.qa,support_totp_secret='JBSWY3DPEHPK3PXP' if args.qa else values['support_totp_secret'],support_admin_emails=('operator@example.test',) if args.qa else ('vineetkd418@gmail.com',))
    app=create_app(settings)
    if args.migrate_from and args.migrate_from.is_file() and not values.get('sqlite_migration_complete'):
        from tools.migrate_storylens_mysql import migrate
        counts=migrate(args.migrate_from,app.state.store)
        values['sqlite_migration_complete']=True
        (folder/'connection.private.json').write_text(json.dumps(values,indent=2),encoding='utf-8')
        print('Existing account data copied to MySQL and row counts verified. The original SQLite database was not changed.',flush=True)
    if args.qa:fixtures(app);print('ISOLATED QA: fixture users and synthetic subscriptions only. No payments or email.',flush=True)
    print('Storylens is ready at '+settings.origin+' — database: MySQL; existing MySQL80 service unchanged.',flush=True)
    server=uvicorn.Server(uvicorn.Config(app,host='127.0.0.1',port=args.port,access_log=False,proxy_headers=False))
    def monitor_database():
        process.wait();server.should_exit=True
    threading.Thread(target=monitor_database,daemon=True).start()
    try:server.run()
    finally:
        app.state.store.close()
        if process.poll() is None:
            try:
                with pymysql.connect(host='127.0.0.1',port=args.db_port,user='root',password=values['root_password'],connect_timeout=2,autocommit=True) as db:
                    with db.cursor() as cursor:cursor.execute('SHUTDOWN')
                process.wait(timeout=20)
            except Exception:
                if process.poll() is None:process.terminate();process.wait(timeout=20)


if __name__=='__main__':main()
