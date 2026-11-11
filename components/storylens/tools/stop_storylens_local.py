"""Gracefully stop only the separately configured local Storylens database/app."""
import json
from pathlib import Path
import pymysql


def main():
    path=Path(__file__).resolve().parents[1]/'cache/storylens-local/connection.private.json'
    if not path.exists():print('Storylens has not been started yet.');return
    values=json.loads(path.read_text())
    try:
        with pymysql.connect(host='127.0.0.1',port=values['database_port'],user='root',password=values['root_password'],connect_timeout=2,autocommit=True) as db:
            with db.cursor() as cursor:cursor.execute('SHUTDOWN')
        print('Storylens is shutting down safely. Your MySQL80 service is unchanged.')
    except pymysql.OperationalError as error:
        if error.args[0]==2003:print('Storylens is already stopped.')
        else:raise RuntimeError('Could not stop the configured Storylens instance; no other process was changed.') from None


if __name__=='__main__':main()
