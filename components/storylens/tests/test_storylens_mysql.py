"""Real MySQL integration suite, only against our separately created QA instance."""
import json
import os
from pathlib import Path
import unittest
import uuid
from unittest.mock import patch
from urllib.parse import quote
import pymysql
from tests import test_storylens
from hinglish_saas.store import Store
from tools.migrate_storylens_mysql import migrate

CONFIG=Path(__file__).resolve().parents[1]/'output/storylens/qa-mysql/connection.private.json'


@unittest.skipUnless(os.environ.get('STORYLENS_MYSQL_TEST')=='1','Explicitly enable the isolated MySQL test server.')
class MySQLStorylensTests(test_storylens.StorylensTests):
    def setUp(self):
        settings=json.loads(CONFIG.read_text());self.database='storylens_test_'+uuid.uuid4().hex
        self.root_connection=pymysql.connect(host='127.0.0.1',port=settings['database_port'],user='root',password=settings['root_password'],autocommit=True)
        with self.root_connection.cursor() as cursor:cursor.execute('CREATE DATABASE `'+self.database+'` CHARACTER SET utf8mb4 COLLATE utf8mb4_bin')
        url='mysql+pymysql://root:'+quote(settings['root_password'],safe='')+'@127.0.0.1:'+str(settings['database_port'])+'/'+self.database
        with patch('hinglish_saas.app.Store',side_effect=lambda folder,*args:Store(folder,url)):super().setUp()
        self.settings.database_url=url

    def tearDown(self):
        self.store.close();super().tearDown()
        # The exact UUID database was created by this fixture on our separate
        # QA server. Never accept a user-supplied database name here.
        assert self.database.startswith('storylens_test_') and len(self.database)==47
        with self.root_connection.cursor() as cursor:cursor.execute('DROP DATABASE `'+self.database+'`')
        self.root_connection.close()

    def test_sqlite_migration_preserves_source_and_refuses_overwrite(self):
        source=Store(self.root/'legacy');source.execute('INSERT INTO users VALUES(?,?,?,?,?)',('legacy-user','legacy@example.test','fixture-password-hash',1,1000))
        before=source.path.read_bytes()
        with self.assertRaisesRegex(ValueError,'empty'):migrate(source.path,self.store)
        copy=self.database+'_copy'
        with self.root_connection.cursor() as cursor:cursor.execute('CREATE DATABASE `'+copy+'` CHARACTER SET utf8mb4 COLLATE utf8mb4_bin')
        values=json.loads(CONFIG.read_text());url='mysql+pymysql://root:'+quote(values['root_password'],safe='')+'@127.0.0.1:'+str(values['database_port'])+'/'+copy
        target=Store(self.root/'copy',url)
        try:
            counts=migrate(source.path,target);self.assertEqual(counts['users'],1)
            self.assertEqual(target.one('SELECT email FROM users')['email'],'legacy@example.test')
            self.assertEqual(source.path.read_bytes(),before)
        finally:
            target.close()
            with self.root_connection.cursor() as cursor:cursor.execute('DROP DATABASE `'+copy+'`')
