"""MySQL 8 storage adapter: bounded pool, parameter binding and InnoDB transactions."""
import re
import sqlite3
from contextlib import contextmanager
from sqlalchemy import create_engine,MetaData,Table,Column,String,Text,Integer,BigInteger,Float,ForeignKey,Index
import pymysql


def schema():
    m=MetaData()
    def table(name,*fields):
        columns=[]
        for field in fields:
            key,kind,*flags=field
            kw={};args=[]
            for flag in flags:
                if isinstance(flag,dict):kw.update(flag)
                else:args.append(ForeignKey(flag))
            columns.append(Column(key,kind,*args,**kw))
        return Table(name,m,*columns,mysql_engine='InnoDB',mysql_charset='utf8mb4',mysql_collate='utf8mb4_bin')
    pk={'primary_key':True};req={'nullable':False}
    def s(n=64):return String(n)
    def default(value):return {'nullable':False,'server_default':str(value)}
    table('users',('id',s(),pk),('email',s(254),{'unique':True,**req}),('password',s(255),req),('verified',Integer,default(0)),('created',Float(53),req))
    table('sessions',('token',s(),pk),('user_id',s(),'users.id',req),('csrf',s(),req),('expires',Float(53),req))
    table('tokens',('hash',s(),pk),('user_id',s(),'users.id',req),('kind',s(30),req),('expires',Float(53),req))
    table('orders',('id',s(90),pk),('user_id',s(),'users.id',req),('plan',s(20),req),('amount',BigInteger,req),('currency',s(5),default('INR')),('state',s(20),default('created')),('payment_id',s(90),{'unique':True}),('starts',Float(53)),('ends',Float(53)),('created',Float(53),req),('edition',s(20),default('bundle')))
    table('webhook_events',('id',s(),pk),('created',Float(53),req))
    table('revocations',('payment_id',s(90),pk),('created',Float(53),req))
    table('uploads',('id',s(),pk),('user_id',s(),'users.id',req),('name',s(100),req),('path',Text,req),('bytes',BigInteger,req),('created',Float(53),req))
    table('jobs',('id',s(),pk),('user_id',s(),'users.id',req),('tool',s(30),req),('payload',Text,req),('state',s(20),default('queued')),('message',s(1000),default('Waiting for the rendering worker')),('created',Float(53),req),('updated',Float(53),req))
    # MySQL TEXT defaults vary across 8.0 patch versions; supply this in INSERTs.
    table('exports',('id',s(),pk),('user_id',s(),'users.id',req),('job_id',s(),'jobs.id',req),('name',s(255),req),('path',Text,req),('created',Float(53),req))
    table('rate_limits',('key',s(255),pk),('bucket',BigInteger,pk),('count',Integer,req),('expires',Float(53),default(0)))
    table('device_codes',('code',s(),pk),('user_code',s(9),{'unique':True,**req}),('edition',s(20),req),('public_key',s(44),req),('name',s(100),req),('expires',Float(53),req),('user_id',s()),('consumed',Integer,default(0)),('hardware_hash',s(),default('')))
    table('devices',('id',s(),pk),('user_id',s(),'users.id',req),('edition',s(20),req),('public_key',s(44),req),('name',s(100),req),('credential',s(),req),('revoked',Integer,default(0)),('created',Float(53),req),('hardware_hash',s(),default('')),('last_lease',Float(53),default(0)))
    table('license_nonces',('device_id',s(),pk),('nonce',s(),pk),('expires',Float(53),req))
    table('device_bindings',('user_id',s(),'users.id',pk),('edition',s(20),pk),('device_id',s()),('release_after',Float(53),default(0)))
    table('computer_bindings',('user_id',s(),'users.id',pk),('public_key',s(44)),('hardware_hash',s()),('release_after',Float(53),default(0)))
    table('security_events',('id',s(),pk),('actor',s(),req),('action',Text,req),('target',s(100),req),('created',Float(53),req))
    table('support_tickets',('id',s(),pk),('user_id',s(),'users.id',req),('subject',s(140),req),('category',s(30),req),('status',s(20),default('open')),('created',Float(53),req),('updated',Float(53),req))
    table('support_messages',('id',s(),pk),('ticket_id',s(),'support_tickets.id',req),('author',s(),'users.id',req),('staff',Integer,default(0)),('body',Text,req),('created',Float(53),req))
    table('support_outbox',('id',s(),pk),('recipient',s(254),req),('subject',s(255),req),('body',Text,req),('state',s(20),default('pending')),('attempts',Integer,default(0)),('available',Float(53),req),('lease_until',Float(53),default(0)),('claim',s()),('created',Float(53),req))
    table('reviews',('id',s(),pk),('user_id',s(),'users.id',{'unique':True,**req}),('display_name',s(60),req),('rating',Integer,req),('title',s(120),req),('body',Text,req),('status',s(20),default('pending')),('created',Float(53),req),('updated',Float(53),req))
    table('usage_events',('id',s(),pk),('user_id',s(),'users.id',req),('device_id',s(),'devices.id',req),('tool',s(30),req),('outcome',s(20),req),('duration',Float(53),req),('app_version',s(30),req),('created',Float(53),req))
    table('transaction_lock',('id',Integer,pk))
    for name,fields in {'sessions':('user_id','expires'),'orders':('user_id','state','ends'),'devices':('user_id','revoked'),
        'jobs':('user_id','created'),'uploads':('user_id',),'support_tickets':('user_id','updated'),
        'support_outbox':('state','available'),'reviews':('status','updated'),'usage_events':('user_id','created')}.items():
        Index('ix_'+name+'_lookup',*(m.tables[name].c[x] for x in fields))
    return m


class Row(dict):
    def __getitem__(self,key):return tuple(self.values())[key] if isinstance(key,int) else super().__getitem__(key)


class Result:
    def __init__(self,rows,rowcount):self.rows=rows;self.rowcount=rowcount
    def fetchone(self):return self.rows.pop(0) if self.rows else None
    def fetchall(self):rows=self.rows;self.rows=[];return rows
    def __iter__(self):return iter(self.fetchall())


def query(sql):
    # Internal statements use sqlite-style parameters; user values always remain
    # bound driver arguments, never part of this translation.
    sql=re.sub(r'(?<!`)\bkey\b(?!`)','`key`',sql,flags=re.I)
    sql=re.sub(r'\bINSERT OR IGNORE\b','INSERT IGNORE',sql,flags=re.I)
    sql=re.sub(r'ON CONFLICT\([^)]*\) DO UPDATE SET','ON DUPLICATE KEY UPDATE',sql,flags=re.I)
    sql=re.sub(r'\bexcluded\.([a-z_]+)',r'VALUES(\1)',sql,flags=re.I)
    sql=re.sub(r'\bMAX\(last_lease,','GREATEST(last_lease,',sql,flags=re.I)
    return sql.replace('%','%%').replace('?','%s')


class Connection:
    def __init__(self,raw):self.raw=raw
    def execute(self,sql,args=()):
        try:
            with self.raw.cursor(pymysql.cursors.DictCursor) as cursor:
                cursor.execute(query(sql),args)
                rows=[Row(row) for row in cursor.fetchall()] if cursor.description else []
                return Result(rows,cursor.rowcount)
        except pymysql.IntegrityError as error:raise sqlite3.IntegrityError('Database constraint rejected this operation.') from error


class Database:
    def __init__(self,url):
        self.engine=create_engine(url,pool_size=8,max_overflow=4,pool_timeout=10,pool_recycle=1800,
            pool_pre_ping=True,hide_parameters=True,isolation_level='READ COMMITTED',
            connect_args={'connect_timeout':5,'read_timeout':15,'write_timeout':15,'charset':'utf8mb4'})
        schema().create_all(self.engine)
        with self.engine.begin() as db:db.exec_driver_sql('INSERT IGNORE INTO transaction_lock(id) VALUES(1)')

    @contextmanager
    def connect(self,immediate=False):
        raw=self.engine.raw_connection()
        try:
            raw.begin();db=Connection(raw)
            # Serializes short account/device/payment mutations across workers.
            # It preserves the existing SQLite BEGIN IMMEDIATE contract at this
            # deliberately small scale; media processing never holds this lock.
            if immediate:db.execute('SELECT id FROM transaction_lock WHERE id=1 FOR UPDATE')
            yield db
            raw.commit()
        except BaseException:raw.rollback();raise
        finally:raw.close()

    def close(self):self.engine.dispose()
