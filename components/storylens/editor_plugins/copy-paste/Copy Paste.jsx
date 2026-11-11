#target aftereffects
#targetengine "StorylensCopyPaste"
(function(){
 var dir=new File($.fileName).parent;
 $.evalFile(new File(dir.fsName+'/model.js'));$.evalFile(new File(dir.fsName+'/host.jsx'));
 var w=new Window('palette','Storylens - Copy Paste',undefined,{resizeable:true});w.orientation='column';w.alignChildren=['fill','top'];
 w.add('statictext',undefined,'Project media > Copy media | Template layer > Paste next');
 var buttons=w.add('group'),copy=buttons.add('button',undefined,'Copy media'),read=buttons.add('button',undefined,'Read slots'),paste=buttons.add('button',undefined,'Paste next');
 var copied=w.add('statictext',undefined,'No media copied.'),status=w.add('statictext',undefined,'Select one template layer on the timeline.',{multiline:true});status.preferredSize=[470,55];
 var fit=w.add('dropdownlist',undefined,['Fill - crop edges','Fit - full picture']);fit.selection=0;
 var list=w.add('dropdownlist',undefined,[]);list.preferredSize=[470,26];var reset=w.add('button',undefined,'Set next slot');
 var technical=w.add('panel',undefined,'Technical details'),details=technical.add('edittext',undefined,'',{multiline:true,readonly:true});details.preferredSize=[450,65];technical.visible=false;
 function call(p){try{technical.visible=false;var r=SLCopyPaste.dispatch(p);if(r.error){status.text=r.error;details.text=r.details;technical.visible=true;return;}if(r.clipboard)copied.text='Copied: '+r.clipboard.name;if(r.copied){status.text='Now select your template layer and press Paste next.';return;}list.removeAll();for(var i=0;i<r.slots.length;i++)list.add('item',r.slots[i].number+'. '+r.slots[i].path);if(r.slots.length)list.selection=Math.min(r.next,r.slots.length-1);status.text=r.template+' | '+r.total+' slots | '+(r.complete?'All filled.':'Next '+(r.next+1))+ (r.pasted?'\nPlaced '+r.pasted.media+' in slot '+r.pasted.number+'.':'');}catch(e){status.text='Copy Paste could not finish. Check Technical details.';details.text=String(e);technical.visible=true;}w.layout.layout(true);}
 copy.onClick=function(){call({action:'copy'});};read.onClick=function(){call({action:'inspect'});};paste.onClick=function(){call({action:'paste',fit:fit.selection.index?'fit':'fill'});};reset.onClick=function(){if(list.selection)call({action:'reset',next:list.selection.index});};
 w.onResizing=w.onResize=function(){this.layout.resize();};w.center();w.show();
})();
