// State checks shared with fixture tests captured from the real Instagram composer.
((root)=>{
  const controlText=value=>(value||'').replace(/\s+/g,' ').trim().toLocaleLowerCase();
  function sameControl(actual,expected){return controlText(actual)===controlText(expected)}
  function signedInAccount(document){
    const accounts=[...document.querySelectorAll('a[href]')].filter(a=>
      a.getClientRects().length&&!a.closest('main,header,article,[role="main"],[role="dialog"]')&&
      /profile picture/i.test([a.getAttribute('aria-label'),...[...a.querySelectorAll('img')].map(i=>i.alt)].join(' ')))
      .map(a=>(a.getAttribute('href')||'').match(/^\/([A-Za-z0-9._]+)\/$/)?.[1]?.toLowerCase()).filter(Boolean);
    const unique=[...new Set(accounts)];return unique.length===1?unique[0]:'';
  }
  function profileReady(document,pathname,account){
    return signedInAccount(document)===account&&pathname.replace(/\/+$/,'').toLowerCase()==='/'+account&&
      [...document.querySelectorAll('main h1,main h2,main [role="heading"]')].some(h=>
        h.getClientRects().length&&controlText(h.innerText)===account);
  }
  function emptyComposer(dialog){
    if(!dialog)return false;
    if([...dialog.querySelectorAll('input[type="file"]')].some(input=>input.files?.length))return false;
    if([...dialog.querySelectorAll('video,img[src^="blob:"]')].length)return false;
    return ![...dialog.querySelectorAll('[contenteditable="true"],textarea')].some(box=>(box.value||box.innerText||'').trim());
  }
  function checked(element){
    if(!element)return null;
    if(element.type==='checkbox'&&typeof element.checked==='boolean')return element.checked;
    const value=element.getAttribute('aria-checked');
    return value==='true'?true:value==='false'?false:null;
  }
  function composerAccount(dialog,account){
    return !!dialog&&[...dialog.querySelectorAll('a,[role="link"]')].some(link=>
      link.getAttribute('href')==='/'+account+'/'||link.querySelector('img')?.alt===account+"'s profile picture");
  }
  function videoInput(dialog){
    return dialog&&[...dialog.querySelectorAll('input[type="file"]')].find(input=>/video\/mp4|video\/\*/i.test(input.getAttribute('accept')||''))||null;
  }
  function newTopReel(document,account,prior){
    // Instagram can render its profile grid as a sibling of main after publishing.
    const top=[...document.querySelectorAll('a[href]')].find(a=>new RegExp('^/'+account+'/(?:reel|p)/[A-Za-z0-9_-]+/$').test(a.getAttribute('href')));
    return top&&!prior.has(top.getAttribute('href'))?top:null;
  }
  function publishedCaption(article,href,caption){
    if(!article)return false;
    const norm=s=>(s||'').replace(/\s+/g,' ').trim();
    const headings=[...article.querySelectorAll('h1,[role="heading"][aria-level="1"]')].filter(h=>norm(h.innerText));
    return [...article.querySelectorAll('a[href]')].some(a=>a.getAttribute('href')===href)&&
      (norm(caption)?headings.some(h=>norm(h.innerText)===norm(caption)):headings.length===0);
  }
  function existingPublication(article,account,caption,after,before){
    if(!article||!Number.isFinite(after)||!Number.isFinite(before)||after>before)return null;
    const links=[...article.querySelectorAll('a[href]')];
    const path=new RegExp('^/'+account.replace(/[.*+?^${}()|[\]\\]/g,'\\$&')+'/(?:reel|p)/[A-Za-z0-9_-]+/$','i');
    const link=links.find(a=>path.test(a.getAttribute('href')||''));
    if(!link||!publishedCaption(article,link.getAttribute('href'),caption))return null;
    const times=[...article.querySelectorAll('time[datetime]')].map(t=>Date.parse(t.getAttribute('datetime'))/1000);
    const posted=times.find(t=>Number.isFinite(t)&&t>=after&&t<=before);
    if(!posted)return null;
    return {url:'https://www.instagram.com'+link.getAttribute('href'),account,posted_at:posted,caption_verified:true};
  }
  function matchingReel(document,account,caption){
    const norm=value=>(value||'').replace(/\s+/g,' ').trim();
    const pattern=new RegExp('^/'+account.replace(/[.*+?^${}()|[\]\\]/g,'\\$&')+'/(?:reel|p)/[A-Za-z0-9_-]+/$','i');
    const accountLinks=[...document.querySelectorAll('a[href]')].filter(a=>pattern.test(a.getAttribute('href')||''));
    // Without caption text the top profile post is only a candidate. Its exact
    // account, absent caption and submission-time window must still verify.
    if(!norm(caption))return accountLinks[0]||null;
    const links=accountLinks.filter(a=>[...a.querySelectorAll('img')].some(img=>norm(img.alt)===norm(caption)));
    return links.length===1?links[0]:null;
  }
  function accountSwitchRow(dialog,account,labels=[],exactOnly=false){
    if(!dialog)return null;
    const norm=s=>(s||'').replace(/\s+/g,' ').trim();
    const rows=[...dialog.querySelectorAll('[role="button"],button')].filter(e=>e.getClientRects().length);
    const exact=rows.find(e=>[...e.querySelectorAll('span,div')].some(n=>norm(n.textContent)===account));
    if(exact)return exact;
    // Owner-confirmed switcher labels are navigation aliases only. The
    // executor still verifies the real signed-in handle before any upload.
    const aliases=new Set(labels.filter(s=>typeof s==='string').map(s=>norm(s).toLowerCase()));
    const matching=rows.filter(e=>aliases.has(norm(e.innerText).toLowerCase())||
      [...e.querySelectorAll('span,div')].some(n=>aliases.has(norm(n.textContent).toLowerCase())));
    if(matching.length)return matching.length===1?matching[0]:null;
    if(aliases.size||exactOnly)return null;
    // Instagram can display a remembered login email instead of its public username.
    // Only try a single unambiguous alternative; the worker verifies the real username afterwards.
    // The current switcher can omit the remembered login's avatar entirely.
    // Its missing image is not evidence that the saved login is unavailable.
    const emailRows=rows.filter(e=>/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(norm(e.innerText)));
    return emailRows.length===1?emailRows[0]:null;
  }
  function commentContext(document,location,account){
    if(signedInAccount(document)!==account)throw Error('Open Instagram while signed in as @'+account+'.');
    const postPath=/^\/(?:([A-Za-z0-9._]+)\/)?(reels?|p)\/([A-Za-z0-9_-]{1,64})\/?$/;
    const page=location.pathname.match(postPath);
    const profileOpen=location.pathname.replace(/\/+$/,'')==='/'+account;
    if((!page&&!profileOpen)||page?.[1]&&page[1]!==account)throw Error('Open one of @'+account+'’s posts or Reels in Chrome.');
    const visible=element=>element.getClientRects().length>0;
    const articles='article,[role="article"]';
    const surface=page?'main,[role="main"],[role="dialog"]':'[role="dialog"]';
    function candidate(container, singlePage){
      const links=[...container.querySelectorAll('a[href]')].filter(visible);
      const posts=new Map();
      for(const link of links){
        const owned=link.getAttribute('href').match(postPath);
        if(owned?.[1]===account&&(!page||page[3]===owned[3])){
          posts.set(owned[3],{kind:owned[2]==='p'?'p':'reel',sourceId:owned[3],article:container});
        }
      }
      if(!posts.size&&page){
        const exact=links.map(link=>link.getAttribute('href').match(postPath))
          .find(post=>post&&!post[1]&&post[3]===page[3]);
        const authors=new Set();
        for(const link of links){
          if(link.closest('li,[role="listitem"]'))continue;
          const author=link.getAttribute('href').match(/^\/([A-Za-z0-9._]{1,30})\/?$/)?.[1]?.toLowerCase();
          if(!author)continue;
          const header=link.closest('header');
          const portrait=link.querySelector?.('img')?.alt||link.getAttribute('aria-label')||'';
          const namesOwner=portrait.toLowerCase().startsWith(author+"'s profile picture");
          if(header?.closest(articles)===container||singlePage&&(namesOwner||header&&container.contains(header)))
            authors.add(author);
        }
        const singleVideo=singlePage&&[...container.querySelectorAll('video')].filter(visible).length===1;
        if((exact||singleVideo)&&authors.size===1&&authors.has(account)){
          posts.set(page[3],{kind:page[2]==='p'?'p':'reel',sourceId:page[3],article:container});
        }
      }
      return posts.size===1?[...posts.values()][0]:null;
    }
    const postContainers=[...document.querySelectorAll(articles)].filter(article=>visible(article)&&article.closest(surface));
    let candidates=postContainers.map(container=>candidate(container,false)).filter(Boolean);
    if(!candidates.length&&page){
      const containers=[...document.querySelectorAll(surface)].filter(visible);
      const matches=containers.map(container=>candidate(container,true)).filter(Boolean);
      candidates=matches.filter(outer=>!matches.some(inner=>inner!==outer&&outer.article.contains(inner.article)));
    }
    if(candidates.length!==1){
      const reason=postContainers.length?'No single post container exposed its exact permalink and author.':'No visible post container exposed the exact post and author.';
      throw Error('Instagram could not verify the open post for @'+account+'. '+reason);
    }
    return candidates[0];
  }
  function commentPostDate(context, location, account){
    const {article,kind,sourceId}=context;
    const pattern=/^\/(?:([A-Za-z0-9._]+)\/)?(?:reels?|p)\/([A-Za-z0-9_-]{1,64})\/?$/;
    const times=[...article.querySelectorAll('time[datetime]')].filter(element=>{
      if(!element.getClientRects().length||element.closest('li,[role="listitem"]'))return false;
      const href=element.closest('a[href]')?.getAttribute('href');
      if(!href)return false;
      const url=new URL(href,location.origin);
      const post=url.pathname.match(pattern);
      return url.origin===location.origin&&post?.[2]===sourceId&&(!post[1]||post[1]===account)&&
        !url.searchParams.has('comment_id')&&!url.searchParams.has('reply_comment_id');
    });
    const timestamps=[...new Set(times.map(element=>Date.parse(element.getAttribute('datetime'))))];
    if(timestamps.length!==1||!Number.isFinite(timestamps[0])||timestamps[0]>Date.now())
      throw Error('Instagram did not expose the exact publication date for this post.');
    return {source_url:location.origin+'/'+account+'/'+kind+'/'+sourceId+'/',
      source_published_at:new Date(timestamps[0]).toISOString()};
  }
  function visibleComments(document,location,account){
    const {article,kind,sourceId}=commentContext(document,location,account);
    const visible=element=>element.getClientRects().length>0;
    const postPath=/^\/(?:([A-Za-z0-9._]+)\/)?(reels?|p)\/([A-Za-z0-9_-]{1,64})\/?$/;
    const ownedPath='/'+account+'/'+kind+'/'+sourceId+'/';
    const caption=[...article.querySelectorAll('h1,[role="heading"][aria-level="1"]')].filter(visible);
    const description=caption.length===1?caption[0].innerText.trim().slice(0,2200):'';
    const rows=[];
    for(const link of article.querySelectorAll('a[href*="comment_id="]')){
      const url=new URL(link.getAttribute('href'),location.origin);
      const commentPost=url.pathname.match(postPath);
      const ids=url.searchParams.getAll('comment_id');
      if(url.origin!==location.origin||commentPost?.[3]!==sourceId||
        commentPost[1]&&commentPost[1]!==account||ids.length!==1||!/^\d{1,30}$/.test(ids[0])||
        url.searchParams.has('reply_comment_id')||!visible(link))continue;
      const row=link.closest('li,[role="listitem"]');
      if(!row||!article.contains(row)||row.parentElement?.closest('li,[role="listitem"]')&&
        article.contains(row.parentElement.closest('li,[role="listitem"]')))continue;
      const time=link.querySelector('time[datetime]');
      const when=Date.parse(time?.getAttribute('datetime'));
      const authors=[...new Set([...row.querySelectorAll('a[href]')].filter(a=>
        a.closest('li,[role="listitem"]')===row&&visible(a)&&a.innerText.trim())
        .map(a=>a.getAttribute('href').match(/^\/([A-Za-z0-9._]{1,30})\/$/)?.[1]?.toLowerCase()).filter(Boolean))];
      const author=authors.length===1?authors[0]:'';
      const candidates=[...new Set([...row.querySelectorAll('span[dir="auto"]')].filter(element=>
        element.closest('li,[role="listitem"]')===row&&!element.closest('a,time,button,[role="button"]')&&visible(element))
        .map(element=>element.innerText.trim()).filter(Boolean))];
      if(!author||!Number.isFinite(when)||candidates.length!==1||candidates[0].length>2200)continue;
      rows.push({source_id:sourceId,source_url:location.origin+ownedPath,comment_id:ids[0],author_id:author,
        text:candidates[0],published_at:new Date(when).toISOString(),source_title:description.split('\n')[0].slice(0,140),
        source_description:description,own:author===account});
    }
    if(!rows.length){
      const empty=[...article.querySelectorAll('span,p,h2,h3')].some(element=>
        visible(element)&&!element.closest('header,li,[role="listitem"],a,button,[role="button"]')&&
        /^(?:no comments yet|be the first to comment|comments are (?:off|turned off|disabled))[.!]?$/i.test(element.innerText.trim()));
      if(empty)return {account,rows,empty_source:location.origin+ownedPath};
      throw Error('Open the comments panel. Instagram did not expose an empty state or comments with verifiable IDs.');
    }
    if(rows.length>30)throw Error('This post exceeded the Chrome comment scan limit.');
    if(new Set(rows.map(row=>row.comment_id)).size!==rows.length)throw Error('Instagram exposed ambiguous comment identities on this post.');
    return {account,rows};
  }
  const checks={commentContext,commentPostDate,sameControl,signedInAccount,profileReady,emptyComposer,checked,composerAccount,videoInput,newTopReel,publishedCaption,existingPublication,matchingReel,accountSwitchRow,visibleComments};root.StorylensDOM=checks;
  if(typeof module!=='undefined'&&module.exports)module.exports=checks;
})(globalThis);
