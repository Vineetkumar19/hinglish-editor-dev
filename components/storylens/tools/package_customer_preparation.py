"""Package reviewable integration and deployment source; never label it release-ready."""
import hashlib
import json
import zipfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'output/saas'


def bundle(filename,folders,files):
    entries=[]
    for name in folders:
        for path in (ROOT/name).rglob('*'):
            if path.is_file() and '__pycache__' not in path.parts and path.suffix!='.pyc':entries.append(path)
    entries += [ROOT/name for name in files]
    manifest=[];target=OUT/filename
    with zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(set(entries)):
            name=path.relative_to(ROOT).as_posix();content=path.read_bytes()
            if any(part in ('cache','models','input','output','library','publishing','.git','.venv') for part in path.relative_to(ROOT).parts):raise ValueError('Private directory in build manifest.')
            archive.writestr(name,content);manifest.append({'file':name,'sha256':hashlib.sha256(content).hexdigest()})
        archive.writestr('PACKAGE_STATUS.json',json.dumps({'release_ready':False,'customer_installer':False,
            'purpose':'Owner review and build preparation only. Not a signed customer release.','files':manifest},indent=2))
    return {'file':str(target),'bytes':target.stat().st_size,'sha256':hashlib.sha256(target.read_bytes()).hexdigest(),'release_ready':False}


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    artifacts=[bundle('STORYLENS_PLUGIN_PREPARATION.zip',['editor_plugins'],['docs/CINEMATIC_REELS.md','docs/BEAT_STUDIO.md','tools/prepare_beat_panels.py','docs/CUSTOMER_RELEASE_AND_PLUGINS.md','docs/STORYLENS_OWNER_GUIDE.md',
        'tools/stage_customer_runtime.py','tools/prepare_editor_panels.py','docs/SECURITY_REVIEW_2026-10-15.md']),
        bundle('STORYLENS_SERVER_DEPLOYMENT.zip',['hinglish_saas','hinglish_license','saas_site/dist'],[
          'requirements-saas.txt','requirements-saas.lock','saas_site/Dockerfile.api','saas_site/Dockerfile.api.dockerignore',
          'saas_site/.env.example','saas_site/render.yaml','tools/backup_saas.py','tools/provision_license_key.py',
          'tools/provision_support_auth.py','tools/migrate_storylens_mysql.py','saas_site/mysql-schema.sql',
          'docs/CINEMATIC_REELS.md','docs/BEAT_STUDIO.md','docs/STORYLENS_OWNER_GUIDE.md','docs/CUSTOMER_RELEASE_AND_PLUGINS.md','docs/SECURITY_REVIEW_2026-10-15.md'])]
    (OUT/'customer-preparation-packages.json').write_text(json.dumps(artifacts,indent=2),encoding='utf-8')
    print(json.dumps(artifacts))


if __name__=='__main__':main()
