"""Build a public marketing-only bundle, never a copy of the project folder."""
import hashlib
import json
import zipfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'saas_site/dist'
OUT=ROOT/'output/saas'
STATIC_ACCOUNT='''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Choose your edition | Storylens</title><link rel="stylesheet" href="/assets/site.css?v=storylens1"><main class="wrap workflow"><a class="brand" href="/">Storylens</a><h1>Choose where<br>you create.</h1><div class="price-grid"><article class="price-plan"><h3>Desktop</h3><p>A standalone local editing workspace on your Windows computer.</p><p class="price">₹2,000<span>/ month</span></p><p>Or ₹20,000 for annual access.</p></article><article class="price-plan"><h3>Editor Plugins</h3><p>Integrations for After Effects, Premiere Pro and DaVinci Resolve Studio, with one shared local runtime.</p><p class="price">₹2,000<span>/ month</span></p><p>Included with Desktop: ₹2,000 monthly or ₹20,000 annually.</p></article></div><p class="availability">Purchases are not open yet. Merchant verification and signed, host-tested installers are being prepared. This public preview does not collect account information or take payments.</p><div class="actions"><a class="button primary" href="/tour">Explore the editor preview</a><a class="button quiet" href="/">Back to the website</a></div></main></html>'''


STATIC_SUPPORT='''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Support | Storylens</title><link rel="icon" href="/assets/mark.svg"><link rel="stylesheet" href="/assets/site.css?v=storylens1"><link rel="stylesheet" href="/assets/support.css?v=storylens1"></head><body><header class="nav"><a class="brand" href="/"><img src="/assets/mark.svg" alt="" width="28" height="28">Storylens</a><a href="/tour">Explore the editor</a></header><main class="support-layout wrap"><aside><h1>Help, when<br>you need it.</h1><p>Questions about the editor, installation or subscriptions? Get in touch directly.</p><a class="support-email" href="mailto:vineetkd418@gmail.com">vineetkd418@gmail.com</a><p class="support-note">Email support only. We do not offer phone or WhatsApp support. Never send passwords, payment details or API keys.</p></aside><section class="support-workspace support-faq"><h2>A few quick answers.</h2><details open><summary>Can I use my subscription on another computer?</summary><p>Each subscription is registered to one computer. Desktop and Editor Plugins are both included in one subscription. Contact support for a computer replacement or Windows reinstallation. Deactivating a device does not free the subscription for account sharing.</p></details><details><summary>Does local editing require internet?</summary><p>The commercial editor checks the subscription before an edit and during processing. Models and rendering run on your computer. There is no offline editing allowance in the commercial activation policy.</p></details><details><summary>Where are my support tickets?</summary><p>The full account service includes private support threads. This public website is a preview; purchases, account registration and the private ticket inbox are not open here yet. You can contact the owner using the email address on this page.</p></details><details><summary>What should I include in an email?</summary><p>Include the tool, operating system, editor version and error message, together with what you expected to happen. Please avoid attaching private recordings unless requested.</p></details><a class="button primary" href="mailto:vineetkd418@gmail.com?subject=Hinglish%20Editor%20support">Email support</a></section></main><footer class="footer wrap"><a href="/">Storylens</a><a href="/policies">Service information</a></footer></body></html>'''


STATIC_ACCOUNT='''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>One subscription | Storylens</title><link rel="stylesheet" href="/assets/site.css?v=storylens1"></head><body><header class="nav"><a class="brand" href="/">Storylens</a><a href="/reviews">Reviews</a><a href="/support">Support</a></header><main class="wrap workflow"><h1>One subscription.<br>Every way to edit.</h1><p>Desktop application + After Effects, Premiere Pro and DaVinci Resolve Studio integrations. Use them on one registered Windows computer.</p><div class="price-grid"><article class="price-plan"><h3>Monthly</h3><p class="price">₹2,000<span>/ month</span></p><p>Desktop and Editor Plugins included.</p></article><article class="price-plan"><h3>Annual</h3><p class="price">₹20,000<span>/ year</span></p><p>Desktop and Editor Plugins included. Save ₹4,000 compared with 12 monthly payments.</p></article></div><p class="availability">Purchases are not open on this public preview. The MySQL account service runs locally while hosting, payment verification and signed installers are prepared. No payments or account information are collected here.</p><div class="actions"><a class="button primary" href="/tour">Explore the editor preview</a><a class="button quiet" href="/">Back to Storylens</a></div></main></body></html>'''


def main():
    OUT.mkdir(parents=True,exist_ok=True);target=OUT/'STORYLENS_PUBLIC_WEBSITE.zip';manifest=[]
    with zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(SOURCE.rglob('*')):
            if not path.is_file():continue
            name=path.relative_to(SOURCE).as_posix()
            if name in ('workspace.html','support-inbox.html','dashboard.html','assets/dashboard.js','assets/account.js','assets/support-inbox.js','assets/support.js'):continue
            content=({'account.html':STATIC_ACCOUNT,'support.html':STATIC_SUPPORT}[name].encode('utf-8')
                     if name in ('account.html','support.html') else path.read_bytes())
            if name=='reviews.html':content=content.replace(b'<body>',b'<body data-preview="static">')
            archive.writestr(name,content);manifest.append({'path':name,'bytes':len(content),'sha256':hashlib.sha256(content).hexdigest()})
        archive.writestr('app.html',STATIC_ACCOUNT)
    receipt={'type':'public marketing and read-only tour only','accounts':False,'payments':False,'editing':False,
             'private_code_included':False,'files':manifest,'zip':str(target)}
    (OUT/'website-package.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')
    print(json.dumps({'file':str(target),'bytes':target.stat().st_size,'files':len(manifest),'private_code_included':False}))


if __name__=='__main__':main()
