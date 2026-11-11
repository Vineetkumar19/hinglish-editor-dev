/* Adobe ExtendScript host adapter. All edits are imported as new compositions. */
function hString(s){return '"'+String(s).replace(/\\/g,'\\\\').replace(/"/g,'\\"').replace(/\r/g,'\\r').replace(/\n/g,'\\n').replace(/\t/g,'\\t')+'"';}
function hJSON(v){if(v===null)return 'null';if(typeof v==='string')return hString(v);if(typeof v==='number'||typeof v==='boolean')return String(v);var a=[],i;if(v instanceof Array){for(i=0;i<v.length;i++)a.push(hJSON(v[i]));return '['+a.join(',')+']';}for(i in v)if(v.hasOwnProperty(i))a.push(hString(i)+':'+hJSON(v[i]));return '{'+a.join(',')+'}';}
function hinglishSelectedMedia(){
    var paths=[],seen={},items=app.project.selection,i,path,comp=app.project.activeItem;
    try{
        if(comp instanceof CompItem && comp.selectedLayers.length){items=[];for(i=0;i<comp.selectedLayers.length;i++)items.push(comp.selectedLayers[i].source);}
        for(i=0;i<items.length;i++){if(items[i] instanceof FootageItem && items[i].file){path=items[i].file.fsName;if(!seen[path]){seen[path]=true;paths.push(path);}}}
        return hJSON({paths:paths});
    }catch(e){return hJSON({error:e.toString()});}
}
function hinglishExportActiveSequence(outputPath){
    /* A composition can include native AE effects that FCP XML cannot represent.
       Render a temporary queue item, preserving all existing queue flags. */
    var comp=app.project.activeItem,item=null,flags=[],i,queue=app.project.renderQueue;
    if(!(comp instanceof CompItem))return hJSON({error:'Open the composition you want to edit first.'});
    try{
        for(i=1;i<=queue.numItems;i++){flags.push({item:queue.item(i),render:queue.item(i).render});queue.item(i).render=false;}
        item=queue.items.add(comp);
        var target=outputPath.replace(/\.xml$/i,'.avi');item.outputModule(1).applyTemplate('Lossless');item.outputModule(1).file=new File(target);
        item.timeSpanStart=comp.workAreaStart;item.timeSpanDuration=comp.workAreaDuration;item.render=true;queue.render();
        if(item.status!==RQItemStatus.DONE||!new File(target).exists)throw new Error('Composition render did not complete.');
        return hJSON({path:target,name:comp.name});
    }catch(e){return hJSON({error:'Could not render the work area. Check the Lossless output template and writable output folder. '+e.toString()});}
    finally{if(item)try{item.remove();}catch(_){}for(i=0;i<flags.length;i++)try{flags[i].item.render=flags[i].render;}catch(_){} }
}
function hinglishImportResult(manifest){
    var imported=[],cache={},comp=null,i,c,footage,layer,file,folder=null;
    app.beginUndoGroup('Hinglish Editor — import new result');
    try{
        folder=app.project.items.addFolder(manifest.name||'Hinglish Edit');
        if(manifest.type==='cuts'){
            comp=app.project.items.addComp(manifest.name,manifest.width,manifest.height,1,manifest.duration,manifest.fps);comp.parentFolder=folder;
            var hasAudio=false;for(i=0;i<manifest.clips.length;i++)if(manifest.clips[i].kind==='audio')hasAudio=true;
            for(i=manifest.clips.length-1;i>=0;i--){c=manifest.clips[i];file=new File(c.path);if(!file.exists)throw new Error('Media missing: '+c.path);
                if(!cache[c.path]){footage=app.project.importFile(new ImportOptions(file));footage.parentFolder=folder;cache[c.path]=footage;}footage=cache[c.path];
                layer=comp.layers.add(footage);layer.startTime=c.start-c.source_in;layer.inPoint=c.start;layer.outPoint=c.end;
                if(c.kind==='audio'){layer.enabled=false;layer.audioEnabled=true;}else{layer.audioEnabled=!hasAudio;layer.property('Transform').property('Scale').setValue([Math.min(manifest.width/footage.width,manifest.height/footage.height)*100,Math.min(manifest.width/footage.width,manifest.height/footage.height)*100]);}
            }
            comp.openInViewer();return 'ok';
        }
        for(i=0;i<manifest.paths.length;i++){file=new File(manifest.paths[i]);if(!file.exists)throw new Error('Output missing: '+manifest.paths[i]);footage=app.project.importFile(new ImportOptions(file));footage.parentFolder=folder;imported.push(footage);}
        if(imported.length && imported[0].hasVideo && !imported[0].mainSource.isStill){footage=imported[0];comp=app.project.items.addComp(manifest.name,footage.width,footage.height,footage.pixelAspect,footage.duration,footage.frameRate);comp.parentFolder=folder;comp.layers.add(footage);comp.openInViewer();}
        return 'ok';
    }catch(e){return e.toString();}finally{app.endUndoGroup();}
}

#include "panel.jsx"

#include "photo-import.jsx"

#include "template-model.js"

#include "template-aliner-model.js"

#include "template-aliner.jsx"

#include "copy-paste-model.js"

#include "copy-paste.jsx"

#include "template-import-model.js"
#include "template-import.jsx"
