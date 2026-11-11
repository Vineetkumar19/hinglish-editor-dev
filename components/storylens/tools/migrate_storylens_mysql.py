"""Copy an existing SQLite account database into an EMPTY MySQL database.

No source data is modified; all records move in one target transaction. Target
credentials are read from an environment variable, never command-line text.
"""
import argparse
import json
import os
from pathlib import Path
import sqlite3
from contextlib import closing
from hinglish_saas.store import Store
from hinglish_saas.mysql import schema


def migrate(source,target):
    if not Path(source).is_file():raise ValueError('The SQLite source does not exist.')
    metadata=schema();tables=[t for t in metadata.sorted_tables if t.name!='transaction_lock']
    for table in tables:
        if target.one('SELECT COUNT(*) AS n FROM `'+table.name+'`')['n']:raise ValueError('The MySQL target must be empty. No overwrite was performed.')
    with closing(sqlite3.connect('file:'+Path(source).resolve().as_posix()+'?mode=ro',uri=True)) as original:
        original.row_factory=sqlite3.Row
        available={r['name'] for r in original.execute("SELECT name FROM sqlite_master WHERE type='table'")};counts={}
        with target.connect(immediate=True) as destination:
            for table in tables:
                if table.name not in available:continue
                columns=[r['name'] for r in original.execute('PRAGMA table_info('+table.name+')') if r['name'] in table.c]
                names=','.join('`'+name+'`' for name in columns)
                count=0
                for row in original.execute('SELECT '+names+' FROM `'+table.name+'`'):
                    destination.execute('INSERT INTO `'+table.name+'`('+names+') VALUES('+','.join('?' for _ in columns)+')',tuple(row));count+=1
                actual=destination.execute('SELECT COUNT(*) AS n FROM `'+table.name+'`').fetchone()['n']
                if actual!=count:raise ValueError('Migration count verification failed; target transaction rolled back.')
                counts[table.name]=count
    target._bundle_migration()
    return counts


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--source',type=Path,required=True);parser.add_argument('--data-dir',type=Path,default=Path('cache/saas'));args=parser.parse_args()
    url=os.environ.get('HINGLISH_SAAS_DATABASE_URL','')
    if not url:raise ValueError('Set HINGLISH_SAAS_DATABASE_URL in your private environment.')
    target=Store(args.data_dir,url)
    try:print(json.dumps({'database':'MySQL','source_unchanged':True,'verified_counts':migrate(args.source,target)},indent=2))
    finally:target.close()


if __name__=='__main__':main()
