(function(){var base='D:/Full Drive/remove silence/',r={ok:false};try{var s=SLPasteTiming;
 if(!s||s.comp!==app.project.itemByID(24516))throw Error('Timing context unavailable.');
 r.items=app.project.numItems;r.expected_items=s.items;r.root_restored=s.layer.source===s.root;r.comment_restored=String(s.layer.comment)===s.comment;r.root_comment_restored=String(s.root.comment)===s.rootComment;
 r.graph_restored=SLCopyPaste.json(SLCopyPaste.graph(s.root,true))===s.graph;r.original_unchanged=SLCopyPaste.json(SLCopyPaste.graph(app.project.itemByID(59502),true))===s.source;
 r.ok=r.items===s.items&&r.root_restored&&r.comment_restored&&r.root_comment_restored&&r.graph_restored&&r.original_unchanged;
 if(r.ok){SLCopyPaste.clipboard=s.clipboard;SLCopyPaste.history=s.history;SLCopyPaste.targetRef=s.targetRef;}
}catch(e){r.error=String(e);}var f=new File(base+'output/copy-paste-evidence/scroll-speed/first-private-restored.json');f.encoding='UTF-8';f.open('w');f.write(JSON.stringify(r));f.close();})();
