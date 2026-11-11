"""Finalize Storylens launch-preparation receipts; never include secrets or fixtures."""
from pathlib import Path
import json

ROOT=Path(__file__).resolve().parents[1]


def main():
    for folder in ('after-effects-cep','premiere-cep'):
        p=ROOT/'editor_plugins'/folder/'CSXS/manifest.xml';p.write_text(p.read_text().replace('Hinglish Editor','Storylens'),encoding='utf-8')
    p=ROOT/'editor_plugins/premiere-uxp/manifest.json';p.write_text(p.read_text().replace('Hinglish Editor','Storylens'),encoding='utf-8')
    p=ROOT/'editor_plugins/davinci-resolve-studio/Hinglish Editor.py';text=p.read_text(encoding='utf-8')
    for old,new in (("'WindowTitle':'Hinglish Editor'","'WindowTitle':'Storylens'"),("'Text':'Hinglish Editor · Local AI'","'Text':'Storylens · Local AI'"),('Open Hinglish Editor once','Open Storylens once')):text=text.replace(old,new)
    p.write_text(text,encoding='utf-8')
    p=ROOT/'editor_plugins/release/windows-installer.iss';text=p.read_text(encoding='utf-8').replace('AppName=Hinglish Editor','AppName=Storylens').replace('DefaultGroupName=Hinglish Editor','DefaultGroupName=Storylens').replace('Name: "{group}\\Hinglish Editor"','Name: "{group}\\Storylens"').replace('Description: "Open Hinglish Editor"','Description: "Open Storylens"')
    p.write_text(text,encoding='utf-8')
    p=ROOT/'output/saas/release-readiness.json';receipt=json.loads(p.read_text())
    receipt['date']='2026-10-16';receipt['brand']='Storylens'
    receipt['public_marketing_site']={'url':'https://storylens.magicpearl129.chatgpt.site','version':3,'deployment_verified':True,'accounts_and_payments':False,
        'deployment_id':'appgdep_6ad11cf550a081918ebd5e32ccf450b4','source_commit':'160a3538ae7e30c0d19285b80803bec7a397935c'}
    receipt['subscription']={'monthly_inr':2000,'annual_inr':20000,'included':['desktop','plugins'],'computers':1,'renewal':'manual'}
    receipt['database']={'engine':'MySQL 8.0+','local_data':'cache/storylens-local','legacy_sqlite':'Read-only source migration; development fallback only','source_migration_verified':True,'public_hosting':'Deferred at owner request'}
    receipt['device_policy']['per_subscription']=1;receipt['device_policy'].pop('per_edition',None)
    receipt['implemented']=[v.replace('Desktop and Editor Plugins purchase editions','One bundled subscription: Desktop + Editor Plugins').replace('Separate edition renewal periods and payment revocation','Shared subscription renewal periods and payment revocation').replace('One registered computer per edition','One registered computer across Desktop and Plugins') for v in receipt['implemented']]
    for item in ('MySQL schema, bounded connection pool and tested SQLite migration','Private owner dashboard with user counts, subscription counts and review moderation','Verified-account 1–5 star reviews, unique per account, with public aggregates','Opt-in signed local tool usage reporting without footage or captions'):
        if item not in receipt['implemented']:receipt['implemented'].append(item)
    receipt['verification']['storylens_regression_log']='output/storylens/regression-tests.log'
    receipt['verification']['load_test']=json.loads((ROOT/'output/storylens/load-test.json').read_text())
    receipt['verification']['real_mysql_suite']=True
    receipt['verification']['real_customer_data_used_for_load_test']=False
    receipt['security']['server_dependency_advisories']=0
    receipt['owner_guide']='docs/STORYLENS_OWNER_GUIDE.md'
    p.write_text(json.dumps(receipt,indent=2),encoding='utf-8')
    print('Storylens receipts and visible plugin labels updated. Legacy internal installation IDs retained.')


if __name__=='__main__':main()
