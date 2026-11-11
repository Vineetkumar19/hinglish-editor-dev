"""Pre-demo diagnostics. No uploads, grants, worker startup or credential writes.

Existing YouTube credentials may refresh in memory for a read-only channel GET.
Instagram's existing browser transport is reported separately from optional API
credentials; an offline bridge never erases saved account bindings or receipts.
"""
from datetime import datetime, timezone
import json
from pathlib import Path
import time


def youtube_probe(stored):
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build
    from .providers import SCOPES
    credentials = Credentials.from_authorized_user_info(stored['credentials'], SCOPES)
    if not credentials.valid:
        credentials.refresh(Request())  # Deliberately never persist tokens here.
    client = build('youtube','v3',credentials=credentials,cache_discovery=False)
    try:
        rows = client.channels().list(part='snippet',mine=True).execute(num_retries=0).get('items',[])
        if len(rows)!=1:raise ValueError('Expected one channel identity')
        return {'id':rows[0]['id'],'name':rows[0]['snippet']['title']}
    finally:
        close=getattr(client,'close',None)
        if close:close()


def report(root,profile,*,online=False,browser=None):
    from hinglish_niche.profiles import account_key,valid_profile
    from . import secrets
    valid_profile(profile);root=Path(root)
    result={'profile':profile,'checked_at':time.time(),'publication_verified':False,'online_probe':online is True}
    try:
        stored=secrets.load(root,account_key('youtube',profile));credentials=stored.get('credentials',{})
        yt={'state':'saved_unverified','id':stored.get('channel_id',''),'name':stored.get('name',''),
            'refresh_available':bool(credentials.get('refresh_token')),
            'message':'Saved YouTube connection is readable. Run the account check before the demo.'}
        expiry=credentials.get('expiry')
        if expiry:
            try:
                expired=datetime.fromisoformat(expiry.replace('Z','+00:00'))<=datetime.now(timezone.utc)
                if expired:yt.update(state='refresh_required',message='The saved access token has expired. The existing connection needs its normal refresh before verification.')
            except (ValueError,TypeError):yt.update(state='saved_unverified')
        if online is True:
            try:
                observed=youtube_probe(stored)
                if observed['id']!=yt['id']:yt.update(state='account_mismatch',message='YouTube returned a different channel. Keep the draft paused and review this profile binding.')
                else:yt.update(state='verified',name=observed['name'],message='YouTube verified the saved channel. Upload and public-release capability have not been tested by this read-only check.')
            except Exception as error:
                # Provider errors can contain credentials/request URLs. Keep only
                # the error type and numeric HTTP status, never str(error).
                status=getattr(getattr(error,'resp',None),'status',None)
                allowed={'invalid_grant','invalid_client','invalid_scope','unauthorized_client','access_denied','temporarily_unavailable'}
                code=next((a.get('error') for a in error.args if isinstance(a,dict) and a.get('error') in allowed),None)
                yt.update(state='verification_failed',message='The saved YouTube connection could not be verified now. Keep drafts paused and check the service or connection details.',
                          technical={'type':type(error).__name__,'http_status':status if isinstance(status,int) else None,'provider_code':code})
                if code=='invalid_grant':
                    yt.update(state='refresh_rejected',message='Google rejected this saved connection refresh (invalid_grant). The channel mapping is kept. Reconnect the same YouTube channel through Google before uploading; no new sign-in was started.')
    except Exception as error:
        yt={'state':'connection_unavailable','message':'This profile has no readable saved YouTube connection. Review the selected profile before preparing its post.',
            'technical':{'type':type(error).__name__}}
    result['youtube']=yt
    path=root/'cache/local-browser/state.json'
    try:saved=json.loads(path.read_text('utf-8')) if path.is_file() else {}
    except (OSError,ValueError):saved={}
    actual=browser if isinstance(browser,dict) else {}
    account=(actual.get('accounts') or saved.get('accounts') or {}).get(profile,'')
    connected=actual.get('connected') is True
    receipts=[j for j in saved.get('jobs',[]) if j.get('action')=='reel' and j.get('account')==account and j.get('status')=='published']
    result['instagram']={'transport':'browser','account':account,'bridge_connected':connected,
        'state':'account_check_needed' if connected and account else 'bridge_offline' if account else 'account_selection_needed',
        'prior_published_receipts':len(receipts),
        'message':'The browser bridge is online. Check the selected Instagram account before posting; no Reel was submitted.' if connected else
                  'The saved Instagram browser account is kept. Its live browser connection has not been verified by this check; open the existing Chrome connection page before the demo.'}
    result['limits']=['This check creates no post or schedule.','YouTube account verification does not prove public API approval or upload quota.','Instagram requires its existing signed-in browser bridge; saved receipts do not prove the current login.']
    return result


def check(root,profile,browser,progress=print):
    """Inspect the selected saved account with no composer or publication."""
    result=report(root,profile,online=True,browser=browser.snapshot())
    state=browser.snapshot();account=state.get('accounts',{}).get(profile)
    if not state.get('connected') or not account:return result
    progress('Checking Instagram @'+account)
    job=browser.inspect_account(profile);deadline=time.monotonic()+120
    while time.monotonic()<deadline:
        job=browser.get(job['id'])
        if job['status'] not in ('queued','running'):break
        time.sleep(.5)
    else:
        browser.cancel(job['id'])
        result['instagram'].update(state='check_timed_out',message='Instagram verification took too long. Check the open Chrome tab before posting.')
        return result
    if job['status']=='complete' and job.get('account')==account:
        result['instagram'].update(state='verified',account=account,message='Instagram verified @'+account+'. No Reel was submitted.')
    else:result['instagram'].update(state='check_failed',message='Instagram could not verify @'+account+'. Check the signed-in profile in Chrome before posting.')
    return result


def main():
    import argparse
    parser=argparse.ArgumentParser(description='Read-only Publishing Studio pre-demo check')
    parser.add_argument('--root',type=Path,default=Path.cwd());parser.add_argument('--profile',choices=['general','cricket','gaming'],required=True)
    parser.add_argument('--online',action='store_true',help='Verify the existing YouTube channel; refresh in memory only')
    args=parser.parse_args();print(json.dumps(report(args.root,args.profile,online=args.online),indent=2))


if __name__=='__main__':main()
