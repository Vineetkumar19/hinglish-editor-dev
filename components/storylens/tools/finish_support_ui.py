"""Connect support navigation and update the one-computer customer copy."""
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def main():
    for file in (ROOT/'saas_site/dist').glob('*.html'):
        source=file.read_text(encoding='utf-8')
        if file.name in ('support.html','support-inbox.html'):continue
        if 'href="/support"' not in source:
            source=source.replace('</header>','<a class="nav-support" href="/support">Support</a></header>',1)
        source=source.replace('two active computers','one registered computer').replace('Two active computers','One registered computer')
        source=source.replace('Two computers per edition','One computer per subscription')
        source=source.replace('?v=20261015a','?v=20261015b').replace('?v=20261014c','?v=20261015b')
        file.write_text(source,encoding='utf-8')
    script=ROOT/'saas_site/dist/assets/account.js';source=script.read_text(encoding='utf-8')
    source=source.replace("name.textContent=d.name+' · '+(d.edition==='plugins'?'Editor Plugins':'Desktop')+' ';", "name.textContent=d.name+' · '+(d.edition==='plugins'?'Editor Plugins':'Desktop')+' · Registered computer ';")
    source=source.replace('Device deactivated. Any offline access expires within 24 hours.','Device deactivated. This subscription remains tied to this computer. Request a replacement through Support.')
    script.write_text(source,encoding='utf-8')
    css=ROOT/'saas_site/dist/assets/site.css';source=css.read_text(encoding='utf-8')
    if '.nav-support{' not in source:
        source+='\n.nav-support{color:#38655f;font-size:14px;text-decoration:none;margin-left:20px}.nav-support:hover{text-decoration:underline}\n'
        css.write_text(source,encoding='utf-8')
    app=ROOT/'hinglish_app/static/index.html';source=app.read_text(encoding='utf-8')
    if 'vineetkd418@gmail.com' not in source:
        source=source.replace('Editing stays local','Editing stays local · <a href="mailto:vineetkd418@gmail.com?subject=Hinglish%20Editor%20Support">Support</a>')
        app.write_text(source,encoding='utf-8')
    for folder in ('premiere-cep','premiere-uxp'):
        path=ROOT/'editor_plugins'/folder/'index.html';source=path.read_text(encoding='utf-8')
        if 'vineetkd418@gmail.com' not in source:
            source=source.replace('</body>','<footer><a href="mailto:vineetkd418@gmail.com?subject=Hinglish%20Editor%20Support">Customer support · Gmail</a></footer></body>')
            path.write_text(source,encoding='utf-8')


if __name__=='__main__':main()
