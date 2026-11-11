"""Apply the approved product name and one bundled subscription to customer UI.

Internal module names, license audience, installation directories and plugin IDs
remain stable so existing installations and saved projects can be upgraded.
"""
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parents[1]


def main():
    folders=['saas_site/dist','hinglish_app/static']
    files=[]
    for folder in folders:
        files.extend(p for p in (ROOT/folder).rglob('*') if p.suffix in ('.html','.js','.css','.svg'))
    files.extend((ROOT/'editor_plugins').rglob('index.html'))
    files.extend((ROOT/'hinglish_saas').glob('*.py'))
    files.extend(ROOT/name for name in ('tools/package_saas_website.py','tools/provision_support_auth.py'))
    replacements={
        'Hinglish Editor':'Storylens',
        'Desktop and Editor Plugins are separate purchases.':'Desktop and Editor Plugins are both included in one subscription.',
        'Desktop and Plugin editions are separate purchases.':'Desktop and Editor Plugins are both included in one subscription.',
        'Desktop and Editor Plugins are separate editions.':'Desktop and Editor Plugins are both included in one subscription.',
        'Each purchased edition is registered to one Windows computer.':'Your subscription includes Desktop and Editor Plugins on one Windows computer.',
        'Each edition is purchased separately. Both use your computer for editing. The Plugin edition includes all three editor integrations.':'Your subscription includes Desktop and all three editor integrations on one registered computer.',
        'Each edition: ₹2,000 monthly or ₹20,000 annually. Choose Desktop or Editor Plugins in your account.':'One subscription. Desktop and Editor Plugins included. ₹2,000 monthly or ₹20,000 annually.',
        'Access to the purchased edition':'Desktop + Editor Plugins included',
        'Or ₹20,000 for annual access. Purchased separately from Desktop.':'Included with Desktop: ₹2,000 monthly or ₹20,000 annually.',
        'this edition':'Storylens',
        'before purchasing this edition':'before subscribing',
    }
    for path in files:
        text=path.read_text(encoding='utf-8')
        for old,new in replacements.items():text=text.replace(old,new)
        text=text.replace('?v=20261015b','?v=storylens1').replace('?v=20261015a','?v=storylens1')
        if path.parent==ROOT/'saas_site/dist' and path.suffix=='.html' and path.name not in ('dashboard.html','reviews.html','support-inbox.html'):
            if 'href="/reviews"' not in text:text=text.replace('</header>','<a href="/reviews">Reviews</a></header>',1)
        path.write_text(text,encoding='utf-8')
    path=ROOT/'saas_site/dist/account.html';text=path.read_text(encoding='utf-8')
    text=re.sub(r'<label for="edition">.*?</select>', '<input id="edition" type="hidden" value="bundle"><p class="bundle-note"><b>Desktop + Editor Plugins included</b></p>',text,count=1)
    path.write_text(text,encoding='utf-8')
    path=ROOT/'saas_site/dist/index.html';text=path.read_text(encoding='utf-8')
    text=text.replace('Desktop edition','Desktop application').replace('Editor Plugins edition','Editor Plugins')
    text=text.replace('Choose Desktop</a>','Included in your subscription</a>').replace('Choose Editor Plugins</a>','Included in your subscription</a>')
    text=text.replace('/account?edition=desktop&amp;view=register','/account?view=register').replace('/account?edition=plugins&amp;view=register','/account?view=register')
    path.write_text(text,encoding='utf-8')
    path=ROOT/'saas_site/dist/assets/account.js';text=path.read_text(encoding='utf-8')
    text=text.replace("$('#edition').value=new URLSearchParams(location.search).get('edition')==='plugins'?'plugins':'desktop';","$('#edition').value='bundle';")
    text=text.replace("(order.edition==='plugins'?'Editor Plugins':'Desktop')+' · '","'Desktop + Editor Plugins · '")
    text=text.replace("const subs=Object.entries(me.editions||{}).filter(([k,v])=>v.active);if(subs.length)$('#subscription-status').textContent=subs.map(([k,v])=>(k==='plugins'?'Editor Plugins':'Desktop')+' active until '+new Date(v.expires*1000).toLocaleDateString('en-IN')).join(' · ');", "if(me.subscription.active)$('#subscription-status').textContent='Desktop + Editor Plugins active until '+new Date(me.subscription.expires*1000).toLocaleDateString('en-IN')+'.';")
    if 'owner-dashboard-link' not in text:
        text=text.replace("csrf=me.csrf;", "csrf=me.csrf;if(me.is_operator&&!document.querySelector('#owner-dashboard-link')){const a=document.createElement('a');a.id='owner-dashboard-link';a.className='button secondary';a.href='/dashboard';a.textContent='Owner dashboard';$('#billing-panel').prepend(a)}")
    path.write_text(text,encoding='utf-8')
    print('Storylens branding and bundled subscription UI applied; internal installation identifiers preserved.')


if __name__=='__main__':main()
