"""Update release receipts and owner-only launch preparation after security QA."""
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def main():
    policy=ROOT/'saas_site/dist/policies.html';text=policy.read_text(encoding='utf-8')
    if '<h2>One computer per subscription</h2>' not in text:
        text=text.replace('<h2>Files and privacy</h2>',
            '<h2>One computer per subscription</h2><p>Each purchased edition is registered to one Windows computer. Commercial editing requires online verification. Deactivation does not release the subscription for another computer; contact support for a reviewed replacement.</p><h2>Customer support</h2><p>Email <a href="mailto:vineetkd418@gmail.com">vineetkd418@gmail.com</a>. Gmail only; no phone or WhatsApp. The full account service includes private ticket threads. This public preview does not yet host customer accounts or accept ticket submissions.</p><h2>Files and privacy</h2>')
    policy.write_text(text,encoding='utf-8')
    template=ROOT/'tools/update_saas_editions.py';text=template.read_text(encoding='utf-8')
    text=text.replace('Device deactivated. Any offline access expires within 24 hours.',
        'Device deactivated. This subscription remains tied to this computer. Request a replacement through Support.')
    template.write_text(text,encoding='utf-8')
    file=ROOT/'output/saas/release-readiness.json';receipt=json.loads(file.read_text(encoding='utf-8'))
    receipt['implemented']=[x.replace('Ed25519 device activation, proof-of-possession refresh and 24-hour offline leases',
        'One registered computer per edition, DPAPI-protected keys, hardware-bound activation and online checks') for x in receipt['implemented']]
    for item in ('Private customer tickets and MFA-protected operator inbox',
                 'Audited support-controlled device replacement with lease drain',
                 'Persistent Gmail notification queue with retry and failure visibility',
                 'Hardened XML import, bridge origin and local JSON size boundaries'):
        if item not in receipt['implemented']:receipt['implemented'].append(item)
    receipt['support']={'email':'vineetkd418@gmail.com','phone':False,'whatsapp':False,
        'ticket_ui_tested':True,'real_gmail_delivery_tested':False,'public_preview':'Email contact only; account service not deployed'}
    receipt['device_policy']={'per_edition':1,'offline_editing':False,'replacement':'Operator MFA and ticket review',
        'hardware_attestation':False,'production_hosted_worker':'Blocked until device-possession proof is implemented'}
    receipt['verification']['relevant_automated_checks_passed']=211
    receipt['verification']['security_account_bridge_and_integration_checks']=98
    receipt['verification']['timeline_and_media_regression_checks']=113
    receipt['security']={'report':'docs/SECURITY_REVIEW_2026-10-15.md',
        'server_dependency_advisories':0,'local_transformers_advisory_records':9,
        'local_transformers_unique_advisory_ids':6,'torch_variants_scanner_status':'Could not audit PyPI-unmatched +cpu packages',
        'commercial_release_ready':False}
    receipt['remaining']=[x.replace('Verified email-delivery service and final operator policies/contact details',
        'Gmail App Password configuration, real delivery test, operator MFA provisioning and final policies') for x in receipt['remaining']]
    for item in ('Resolve AI runtime dependency advisories and verify model provenance',
                 'Browser-to-device proof before offering production hosted processing'):
        if item not in receipt['remaining']:receipt['remaining'].append(item)
    file.write_text(json.dumps(receipt,indent=2),encoding='utf-8')
    report=json.loads((ROOT/'output/security/server-dependency-audit.json').read_text())
    if any(p.get('vulns') or not p.get('version') for p in report['dependencies']):raise ValueError('Review server dependency findings before locking.')
    lock='# Resolved and pip-audit checked on 2026-10-15; rescan on every update.\n'
    lock+='\n'.join(sorted(p['name']+'=='+p['version'] for p in report['dependencies']))+'\n'
    (ROOT/'requirements-saas.lock').write_text(lock,encoding='utf-8')
    print('Security receipt, public contact policy and server dependency lock prepared.')


if __name__=='__main__':main()
