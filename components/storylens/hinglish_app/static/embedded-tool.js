(()=>{
  if(new URLSearchParams(location.search).get('embedded')!=='1'||window.parent===window)return;
  document.documentElement.classList.add('embedded-tool');
  const style=document.createElement('style');style.textContent=`html.embedded-tool{background:transparent;font-family:Inter,'Segoe UI',sans-serif}html.embedded-tool{overflow:hidden;background:#171a1f}html.embedded-tool body{overflow:hidden;background:#171a1f}html.embedded-tool .feature-tools-heading{display:none!important}html.embedded-tool body>header,html.embedded-tool main>.eyebrow,html.embedded-tool main>h1,html.embedded-tool main>.intro{display:none}html.embedded-tool main{max-width:none;margin:0;padding:0 1px}html.embedded-tool main>section{margin:0 0 18px;padding:22px;background:#171a1f;border:1px solid #343a43;border-radius:9px}html.embedded-tool .grid{gap:14px}html.embedded-tool label{font-size:14px}html.embedded-tool h2{font-size:18px;font-weight:600}html.embedded-tool button{background:#252a30;color:#f1f3f6}html.embedded-tool button.secondary{background:#282e36;color:#e1e7ef}html.embedded-tool input:focus,html.embedded-tool select:focus{outline-color:#a6b5c6}html.embedded-tool #latest{margin-bottom:18px}html.embedded-tool .heading span{border:0;padding:0;color:#9eacbd}html.embedded-tool .heading{margin-bottom:16px}`;document.head.append(style);
  // The native editor uses a fixed-height utility iframe and does not consume
  // the web shell's height messages. Let Photo Collector scroll internally;
  // hiding overflow here otherwise makes later photo rows unreachable.
  if(new URLSearchParams(location.search).get('panel')==='1'){
    style.textContent+='html.embedded-tool{overflow-x:hidden;overflow-y:auto}html.embedded-tool body{overflow:visible}';
  }
  const resize=()=>parent.postMessage({type:'storylens-tool-height',height:Math.ceil(document.querySelector('main').getBoundingClientRect().height)+28},location.origin);
  new ResizeObserver(resize).observe(document.querySelector('main'));window.addEventListener('load',resize);resize();
})();
