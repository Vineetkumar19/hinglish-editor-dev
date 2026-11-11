/* Include model.js and framing.jsx first. Native edits; optional local CPU face bounds. */
if (typeof SLCopyPaste === 'undefined') SLCopyPaste = { project: null, clipboard: null };
SLCopyPaste.json = function (v) {
    if (v === null || typeof v === 'undefined') return 'null';
    if (typeof v === 'string') return '"' + v.replace(/\\/g, '\\\\').replace(/"/g, '\\"').replace(/\r/g, '\\r').replace(/\n/g, '\\n').replace(/\t/g, '\\t').replace(/\u2028/g, '\\u2028').replace(/\u2029/g, '\\u2029') + '"';
    if (typeof v !== 'object') return String(v);
    var a = [], k;
    if (v instanceof Array) { for (k = 0; k < v.length; k++) a.push(SLCopyPaste.json(v[k])); return '[' + a.join(',') + ']'; }
    for (k in v) if (v.hasOwnProperty(k)) a.push(SLCopyPaste.json(k) + ':' + SLCopyPaste.json(v[k]));
    return '{' + a.join(',') + '}';
};
SLCopyPaste.item = function (id) {
    // Native lookup avoids repeated linear walks through a large imported library.
    // Do not retain an item cache: Undo/deletion/project switches invalidate it.
    try { if (typeof app.project.itemByID === 'function') return app.project.itemByID(Number(id)); } catch (_) {}
    for (var i = 1; i <= app.project.numItems; i++) { var item = app.project.item(i); if (String(item.id) === String(id)) return item; }
    return null;
};
SLCopyPaste.checkProject = function () {
    if (typeof CompItem === 'undefined') SLCopyPasteModel.fail('copy_paste_host', 'Nested After Effects template slots must be filled in After Effects. Premiere cannot edit the inside of a Dynamic Link composition. This action does not open either editor.');
    if (!app.project) SLCopyPasteModel.fail('copy_paste_target', 'Open the intended After Effects project first.');
    if (SLCopyPaste.project !== app.project) { SLCopyPaste.project = app.project; SLCopyPaste.clipboard = null; SLCopyPaste.receipts = {}; SLCopyPaste.history = []; SLCopyPaste.targetRef = null; }
};
SLCopyPaste.rememberTarget = function(t) {
    SLCopyPaste.targetRef={comp:t.comp.id,layer:t.layer.id,source:t.layer.source.id};return t;
};
SLCopyPaste.target = function () {
    var M=SLCopyPasteModel,c=app.project.activeItem,explicit=c instanceof CompItem?c:null,rows=[],seen={},i,j;
    function valid(comp,layer){
        if(layer.locked)M.fail('copy_paste_target','Unlock the selected template.');
        if(SLCopyPaste.isShared(comp))M.fail('copy_paste_target','Choose this template on the main timeline.');
        return SLCopyPaste.rememberTarget({comp:comp,layer:layer,root:layer.source});
    }
    function selected(comp,strict){
        if(!(comp instanceof CompItem))return null;
        var ls=comp.selectedLayers||[];
        if(ls.length>1&&strict)M.fail('copy_paste_target','Choose one template.');
        if(ls.length===1&&ls[0].source instanceof CompItem&&String(ls[0].source.comment||'').indexOf('Storylens Copy Paste media v1|')!==0)return valid(comp,ls[0]);
        if(ls.length&&strict)M.fail('copy_paste_target','Choose a template in the timeline.');
        return null;
    }
    var direct=selected(c,true);if(direct)return direct;
    // Copying a Project asset can obscure the composition without clearing its selection.
    try{if(!explicit&&app.activeViewer&&typeof ViewerType!=='undefined'&&app.activeViewer.type===ViewerType.VIEWER_COMPOSITION){app.activeViewer.setActive();c=app.project.activeItem;}}catch(_){}
    direct=selected(c,false);if(direct)return direct;
    function add(comp,layer){var key=String(comp.id)+':'+String(layer.id);if(!seen[key]){seen[key]=true;rows.push({comp:comp,layer:layer});}}
    var ref=SLCopyPaste.targetRef;
    if(ref){var pinned=SLCopyPaste.item(ref.comp);if(pinned instanceof CompItem){var pins=pinned.selectedLayers||[];if(pins.length===1&&String(pins[0].id)===String(ref.layer)&&pins[0].source instanceof CompItem&&String(pins[0].source.id)===String(ref.source)&&(!explicit||pins[0].source===explicit))add(pinned,pins[0]);}}
    for(i=1;i<=app.project.numItems;i++){
        var comp=app.project.item(i);if(!(comp instanceof CompItem))continue;
        var layers=comp.selectedLayers||[];
        for(j=0;j<layers.length;j++){
            var layer=layers[j];if(!(layer.source instanceof CompItem))continue;
            if(String(layer.source.comment||'').indexOf('Storylens Copy Paste media v1|')===0)continue;
            var note=String(layer.comment||''),origin=note.match(/(?:\||^)\s*source=(\d+)/);
            var matches=explicit&&(layer.source===explicit||(origin&&String(origin[1])===String(explicit.id)));
            var tagged=/Storylens Template Aliner v1|\[Storylens Copy Paste v1\||Storylens Cinematic Instance:|Ordered template/.test(note);
            if(matches||(!explicit&&tagged))add(comp,layer);
        }
    }
    if(rows.length===1)return valid(rows[0].comp,rows[0].layer);
    if(rows.length>1)M.fail('copy_paste_target','More than one template is selected. Choose one.');
    M.fail('copy_paste_target','Choose the template you want to fill.');
};
SLCopyPaste.graph = function (root, includeDecorations) {
    var graph = {}, seen = {}, count = 0, layers = 0;
    function walk(c) {
        if (seen[c.id]) return; seen[c.id] = true;
        if (++count > 1500) SLCopyPasteModel.fail('copy_paste_template', 'This template has too many nested compositions. Select a smaller scene.');
        var rows = [], pictures = {}, pictureCount = 0, nested = false, hasText = false, placeholderLabel=false, onlyCanvas=true; graph[c.id] = { id: c.id, name: c.name, layers: rows };
        for (var i = 1; i <= c.numLayers; i++) {
            if (++layers > 20000) SLCopyPasteModel.fail('copy_paste_template', 'This template has too many layers to scan safely. Select a smaller scene.');
            var l = c.layer(i), s = l.source; if (typeof TextLayer !== 'undefined' && l instanceof TextLayer) {hasText = true;if(SLCopyPasteModel.positive(c.name))try{if(/^\s*(?:photo|image|picture|media|footage|placeholder)\s*[_#-]?\s*\d+\s*$/i.test(l.property('ADBE Text Properties').property('ADBE Text Document').value.text))placeholderLabel=true;}catch(_){}} if (!s) continue;
            var wrapped = String(s.comment || '').indexOf('Storylens Copy Paste media v1|') === 0;
            // ExtendScript's chained conditional evaluation differs from modern JS.
            // Keep native type dispatch explicit: an output comp must never be a slot.
            var kind = 'other';
            if (wrapped) kind = 'media';
            else if (s instanceof CompItem) kind = 'comp';
            else if (s instanceof FootageItem) kind = 'media';
            rows.push({ index: i, name: l.name, sourceName: wrapped ? '' : s.name, source: s.id, kind: kind, start: l.inPoint,
                solid: s instanceof FootageItem && s.mainSource instanceof SolidSource, wrapped: wrapped, hasVideo: wrapped || s.hasVideo !== false,
                nullLayer: !!l.nullLayer, adjustment: !!l.adjustmentLayer, guide: !!l.guideLayer, matte: !!l.isTrackMatte, placeholder: typeof PlaceholderSource !== 'undefined' && s instanceof FootageItem && s.mainSource instanceof PlaceholderSource });
            if (kind === 'comp') nested = true;
            if(!wrapped&&!(s instanceof FootageItem&&s.mainSource instanceof SolidSource))onlyCanvas=false;
            if (kind === 'media' && s.hasVideo !== false && !(s instanceof FootageItem && s.mainSource instanceof SolidSource) && !SLCopyPasteModel.excluded(l.name + ' ' + s.name) && !pictures[s.id]) { pictures[s.id] = true; pictureCount++; }
            if (kind === 'comp' && (includeDecorations || !SLCopyPasteModel.excluded(l.name + ' ' + s.name))) walk(s);
        }
        graph[c.id].structuralHolder = !nested && !hasText && pictureCount === 1 && !SLCopyPasteModel.excluded(c.name);
        graph[c.id].hasText = hasText;
        graph[c.id].placeholderCanvas=placeholderLabel&&onlyCanvas&&!nested&&SLCopyPasteModel.positive(c.name);
    }
    walk(root); return graph;
};
SLCopyPaste.read = function (t) {
    var scan = SLCopyPasteModel.scan(SLCopyPaste.graph(t.root), t.root.id), state = SLCopyPasteModel.state(t.layer.comment), next = 0;
    if (state) {
        if (state.root !== String(t.root.id)) SLCopyPasteModel.fail('copy_paste_stale', 'The template structure changed after a paste. Restart from the first placeholder in Settings to continue; existing pictures are kept.');
        next = state.next;
        if(state.signature!==scan.signature){
            // Detector updates may remove decoration-only slots. Resume by native
            // slot identity, never by an old numeric offset or a guessed source.
            var prior=state.signature?state.signature.split(';'):[],cursor=0,resume=0;
            for(var si=0;si<scan.slots.length;si++){
                while(cursor<prior.length&&prior[cursor]!==scan.slots[si].key)cursor++;
                if(cursor>=prior.length)SLCopyPasteModel.fail('copy_paste_stale','The template structure changed after a paste. Restart from the first placeholder in Settings to continue; existing pictures are kept.');
                if(cursor<state.next)resume++;cursor++;
            }
            next=resume;
        }
    }
    return { scan: scan, next: next, state: state };
};
SLCopyPaste.describe = function (t, r) {
    return { ok: true, host: 'aftereffects', template: t.layer.name, composition_id: t.comp.id, layer_id: t.layer.id, source_id: t.root.id,
        next: r.next, total: r.scan.slots.length, slots: r.scan.slots, complete: r.next >= r.scan.slots.length,
        clipboard: SLCopyPaste.clipboard ? { id: SLCopyPaste.clipboard.id, name: SLCopyPaste.clipboard.name } : null };
};
SLCopyPaste.copy = function () {
    SLCopyPaste.clipboard = null;
    var items = app.project.selection || [], eligible = [], i, item;
    for (i = 0; i < items.length; i++) if (items[i] instanceof FootageItem) eligible.push(items[i]);
    if (eligible.length !== 1) SLCopyPasteModel.fail('copy_paste_media', 'Select one imported image or video in the Project panel, then press Copy.');
    item = eligible[0];
    if (!item.hasVideo || item.footageMissing || !item.file || !item.file.exists) SLCopyPasteModel.fail('copy_paste_media', 'This picture or video is missing or cannot be used. Relink it in After Effects or choose another imported media item.');
    SLCopyPaste.clipboard = { kind:'project', id: item.id, name: item.name, file: item.file.fsName };
    return { ok: true, copied: true, clipboard: SLCopyPaste.clipboard };
};
SLCopyPaste.isShared = function (root) {
    var users = root.usedIn || [], count = 0;
    for (var i = 0; i < users.length; i++) for (var k = 1; k <= users[i].numLayers; k++) if (users[i].layer(k).source === root && ++count > 1) return true;
    return false;
};
SLCopyPaste.hasSharedBranch = function (root, scan) {
    if (SLCopyPaste.isShared(root)) return true;
    for (var id in scan.ancestors) if (scan.ancestors.hasOwnProperty(id) && String(id) !== String(root.id)) {
        var c = SLCopyPaste.item(id), users = c.usedIn || [];
        for (var i = 0; i < users.length; i++) if (!scan.ancestors[String(users[i].id)]) return true;
    }
    return false;
};
SLCopyPaste.reusable = function(t, graph) {
    // Only our exact instance's private branches can be edited in place.
    // Native usage checks prevent a copied/reused timeline from inheriting edits.
    var allowed={},key,i,j,root=String(t.root.id),owner=String(t.layer.id),changed=true;
    for(key in graph)if(graph.hasOwnProperty(key)){
        var name=String(graph[key].name),sltt=name.match(/\[SLTT (\d+)-\d+-[^\]]+\]/),paste=name.match(/\[Copy Paste (\d+)\]$/),cinematic=String(SLCopyPaste.item(key).comment||'').match(/\[Storylens Cinematic owner=(\d+)\]/);
        if(sltt){if(sltt[1]===owner)allowed[key]=true;}
        if(paste){if(paste[1]===owner)allowed[key]=true;}
        if(cinematic&&cinematic[1]===owner)allowed[key]=true;
    }
    while(changed){changed=false;for(key in allowed)if(allowed.hasOwnProperty(key)&&allowed[key]){
        var item=SLCopyPaste.item(key),users=item.usedIn||[],valid=true,count=0;
        for(i=0;i<users.length&&valid;i++){
            if(String(key)===root){
                if(users[i]!==t.comp){valid=false;break;}
                for(j=1;j<=users[i].numLayers;j++)if(users[i].layer(j).source===item){count++;if(users[i].layer(j)!==t.layer)valid=false;}
            }else if(!allowed[String(users[i].id)])valid=false;
        }
        if(String(key)===root&&count!==1)valid=false;
        if(!valid){allowed[key]=false;changed=true;}
    }}
    if(!allowed[root])return {};
    return allowed;
};
SLCopyPaste.paste = function (p, target) {
    var timingStart=new Date().getTime(),timings={},timingLast=timingStart;
    function tick(name){var now=new Date().getTime();timings[name]=now-timingLast;timingLast=now;}
    var t = target || SLCopyPaste.target();tick('target');
    var r = SLCopyPaste.read(t), M = SLCopyPasteModel, clip = SLCopyPaste.clipboard;tick('scan');
    if (clip && clip.kind === 'file') return SLCopyPaste.fromFiles({paths:[clip.file],fit:p.fit,request_id:p.request_id}, t);
    if (p.expected && (String(p.expected.layer_id) !== String(t.layer.id) || String(p.expected.source_id) !== String(t.root.id) || p.expected.next !== r.next)) M.fail('copy_paste_stale', 'The selected template or next slot changed. Select the intended template again before pasting.');
    if (!r.scan.slots.length) M.fail('copy_paste_template', 'No replaceable picture or video holder was found in this selected layer. Select the full template layer on your main timeline and try again.');
    if (r.next >= r.scan.slots.length) M.fail('copy_paste_full', 'Every detected slot is filled. Choose a different template, or restart from the first placeholder in Settings.');
    if (!clip) M.fail('copy_paste_media', 'Copy an imported image or video first.');
    var media = SLCopyPaste.item(clip.id);
    if (!(media instanceof FootageItem) || !media.hasVideo || media.footageMissing || !media.file || !media.file.exists || media.file.fsName !== clip.file) M.fail('copy_paste_media', 'The copied media changed or is missing. Select it in the Project panel and copy it again.');
    var created = [], changed = [], expressionChanges=[],rootCommentBefore=null,oldRoot = t.root, oldComment = t.layer.comment, oldTargetName = t.layer.name, undo = false, isolated = false, rollback = true, map = {}, key, i, undoRecord=null, beforeRevision=app.project.revision;
    try {
        if (!target) { app.beginUndoGroup('Copy Paste - next media slot'); undo = true; }
        if (!r.state || r.state.owner !== String(t.layer.id) || String(t.root.comment || '').indexOf('[Storylens Copy Paste isolation v2]') < 0 || SLCopyPaste.hasSharedBranch(t.root, r.scan)) {
            // Copy the affected holder and all render/expression dependants.
            // Computed comp references retain the conservative full-tree path.
            var isolationClock=new Date().getTime(),dependencies = SLCopyPaste.graph(t.root, true);
            var dependencyRefs={},dynamicReference=false;
            function inspectReferences(group,record){for(var pi=1;pi<=group.numProperties;pi++){var property=group.property(pi);if(property.canSetExpression&&property.expression){var refs=M.referencedComps(property.expression);record.names=record.names.concat(refs.names);if(refs.dynamic){record.dynamic=true;dynamicReference=true;return;}}if(property.numProperties){inspectReferences(property,record);if(dynamicReference)return;}}}
            for(key in dependencies)if(dependencies.hasOwnProperty(key)){var record={names:[],dynamic:false},sourceComp=SLCopyPaste.item(key);dependencyRefs[key]=record;for(i=1;i<=sourceComp.numLayers;i++){inspectReferences(sourceComp.layer(i),record);if(dynamicReference)break;}if(dynamicReference)break;}
            var reusable=SLCopyPaste.reusable(t,dependencies),chosenDependencies=M.isolationSet(dependencies,t.root.id,r.scan.slots[r.next].comp,dependencyRefs,reusable);dependencies=chosenDependencies.graph;timings.isolation_mode=chosenDependencies.mode;timings.reused_private_comps=0;
            timings.isolation_graph=new Date().getTime()-isolationClock;isolationClock=new Date().getTime();
            timings.duplicate_native=0;timings.duplicate_metadata=0;
            for (key in dependencies) if (dependencies.hasOwnProperty(key)) {
                if(reusable[key]){map[key]=SLCopyPaste.item(key);timings.reused_private_comps++;continue;}
                var original = SLCopyPaste.item(key), duplicateClock=new Date().getTime(), duplicate = original.duplicate(); created.push(duplicate); map[key] = duplicate;
                timings.duplicate_native+=new Date().getTime()-duplicateClock;duplicateClock=new Date().getTime();
                duplicate.name = original.name + ' [Copy Paste ' + t.layer.id + ']';if(duplicate.parentFolder!==original.parentFolder)duplicate.parentFolder=original.parentFolder;
                timings.duplicate_metadata+=new Date().getTime()-duplicateClock;
            }
            timings.isolation_duplicate=new Date().getTime()-isolationClock;isolationClock=new Date().getTime();
            if(reusable[String(t.root.id)])rootCommentBefore=String(t.root.comment||'');
            if(String(map[String(t.root.id)].comment||'').indexOf('[Storylens Copy Paste isolation v2]')<0)map[String(t.root.id)].comment = String(map[String(t.root.id)].comment || '') + '\n[Storylens Copy Paste isolation v2]';
            var expressionNames = {};
            for (key in map) if (map.hasOwnProperty(key)) expressionNames[SLCopyPaste.item(key).name] = map[key].name;
            for (key in map) if (map.hasOwnProperty(key)) { var baseName = SLCopyPaste.item(key).name.replace(/(?: \[Copy Paste \d+\])+$/, ''); if (!expressionNames.hasOwnProperty(baseName)) expressionNames[baseName] = map[key].name; }
            function fixProperties(group,reused) {
                for (var pi = 1; pi <= group.numProperties; pi++) {
                    var property = group.property(pi);
                    if (property.canSetExpression) { var before=property.expression;if(before){var enabled = property.expressionEnabled, after = M.expression(before, expressionNames); if (after !== before) { if(reused)expressionChanges.push({property:property,before:before,enabled:enabled});property.expression = after; if(property.expressionEnabled!==enabled)property.expressionEnabled = enabled; } } }
                    if (property.numProperties) fixProperties(property,reused);
                }
            }
            for (key in map) if (map.hasOwnProperty(key)) {
                var c = map[key];
                for (i = 1; i <= c.numLayers; i++) { var edge = c.layer(i), s = edge.source; if (s && map[String(s.id)]&&map[String(s.id)]!==s) { var edgeName = edge.name, edgeLock = edge.locked;if(reusable[key])changed.push({layer:edge,source:s,name:edgeName,locked:edgeLock});edge.locked = false; try { edge.replaceSource(map[String(s.id)], false); edge.name = edgeName; } finally { edge.locked = edgeLock; } } fixProperties(edge,!!reusable[key]); }
            }
            timings.isolation_rewire=new Date().getTime()-isolationClock;
            var targetName = t.layer.name; if(t.layer.source!==map[String(t.root.id)]){t.layer.replaceSource(map[String(t.root.id)], false);t.layer.name = targetName;isolated = true;}t.root = t.layer.source;
            r = { scan: M.scan(SLCopyPaste.graph(t.root), t.root.id), next: r.next };
        }
        tick('isolation');
        var slot = r.scan.slots[r.next], owner = SLCopyPaste.item(slot.comp), old;
        if (slot.empty) old = owner; else old = owner.layer(slot.layers[0]).source;
        var w = old.width, h = old.height, aspect = old.pixelAspect || 1, seconds = Math.max(owner.duration, old.duration || 0, 1 / owner.frameRate);
        var viewport={rect:[0,0,w,h],method:'holder-only',warnings:[]};
        try{if(typeof SLCopyPasteViewport!=='undefined')viewport=SLCopyPasteViewport.measure(t,slot,w,h);else viewport.warnings.push('Animated frame measurement is unavailable; holder framing was used.');}
        catch(viewError){viewport.warnings.push('Animated frame measurement could not finish; holder framing was used. '+String(viewError.message||viewError));}
        tick('viewport');
        var analysis=clip.framing||null;
        if(analysis&&Math.abs((analysis.width/analysis.height)/(media.width/media.height)-1)>.03)analysis=null;
        var framing;
        try{if(typeof SLCopyPasteFramingModel!=='undefined')framing=SLCopyPasteFramingModel.reframe(w,h,aspect,media.width,media.height,media.pixelAspect||1,analysis,viewport.rect);}catch(subjectError){viewport.warnings.push('Subject framing could not finish; the whole image was kept. '+String(subjectError.message||subjectError));}
        if(!framing){var contain=M.fit(w,h,aspect,media.width,media.height,media.pixelAspect||1,'fit'),cover=M.fit(w,h,aspect,media.width,media.height,media.pixelAspect||1,'fill');framing={position:[w/2,h/2],scale:contain,background:Math.abs(contain-cover)>.001,background_scale:cover,method:'whole-image',video_sampled:false};viewport.warnings.push('Subject framing is unavailable; the whole image was kept.');}
        var destinationItems=owner.parentFolder&&owner.parentFolder.items?owner.parentFolder.items:app.project.items;
        var wrapper = destinationItems.addComp('Copy Paste ' + (r.next + 1) + ' - ' + media.name, w, h, aspect, seconds, owner.frameRate);
        created.push(wrapper); if(wrapper.parentFolder!==owner.parentFolder)wrapper.parentFolder = owner.parentFolder;
        wrapper.comment = 'Storylens Copy Paste media v1|source=' + media.id;
        var inside = wrapper.layers.add(media); inside.audioEnabled = false;
        var tr = inside.property('ADBE Transform Group');
        tr.property('ADBE Anchor Point').setValue([media.width / 2, media.height / 2]);
        tr.property('ADBE Position').setValue(framing.position);
        var scale = framing.scale;
        tr.property('ADBE Scale').setValue([scale, scale]);
        if (!media.mainSource.isStill && media.duration < seconds) {
            // Keep short videos visible for the full holder; never leave a blank tail.
            inside.timeRemapEnabled = true;
            var remap = inside.property('ADBE Time Remapping');
            var last = Math.max(0, media.duration - 1 / (media.frameRate || owner.frameRate));
            remap.setValueAtTime(0, 0); if (last > 0) remap.setValueAtTime(last, last);
            remap.setValueAtTime(seconds, last);
            // Removing the final key disables native Time Remapping. Add the
            // hold keys first, then remove only the old source-end key.
            var keyTolerance=0.5/owner.frameRate+0.000001; // AE snaps key times to the composition frame grid.
            for(var rk=remap.numKeys;rk>=1;rk--){var rt=remap.keyTime(rk);if(Math.abs(rt)>keyTolerance&&Math.abs(rt-last)>keyTolerance&&Math.abs(rt-seconds)>keyTolerance)remap.removeKey(rk);}
        }
        inside.outPoint = seconds;
        if(framing.background){
            // A full-frame blurred copy fills excess canvas when the sharp subject must zoom out.
            var backdrop=inside.duplicate();backdrop.name='Picture edge fill';backdrop.moveAfter(inside);
            var bt=backdrop.property('ADBE Transform Group');bt.property('ADBE Position').setValue([w/2,h/2]);bt.property('ADBE Scale').setValue([framing.background_scale,framing.background_scale]);
            var blur=backdrop.property('ADBE Effect Parade').addProperty('ADBE Gaussian Blur 2');blur.property(1).setValue(Math.max(w,h)*.06);try{blur.property(3).setValue(true);}catch(_){}
        }
        if (slot.empty) { var filled = owner.layers.add(wrapper); changed.push({layer:filled,added:true});filled.audioEnabled=false;filled.startTime=0;filled.inPoint=0;filled.outPoint=owner.duration; }
        for (i = 0; i < slot.layers.length; i++) {
            var leaf = owner.layer(slot.layers[i]), leafName = leaf.name, leafLock = leaf.locked; changed.push({ layer: leaf, source: leaf.source, name: leafName, locked: leafLock });
            leaf.locked = false; try { leaf.replaceSource(wrapper, false); leaf.name = leafName; } finally { leaf.locked = leafLock; }
        }
        tick('replacement');
        var after = M.scan(SLCopyPaste.graph(t.root), t.root.id);
        if (after.slots.length !== r.scan.slots.length) throw Error('The slot list changed during replacement.');
        t.layer.comment = M.writeState(oldComment, { owner: t.layer.id, root: t.root.id, next: r.next + 1, signature: after.signature });
        var result = SLCopyPaste.describe(t, { scan: after, next: r.next + 1 });
        result.pasted = { number: r.next + 1, name: slot.name, media: media.name, wrapper_id: wrapper.id, isolated: isolated, fit: 'fill', short_video: !media.mainSource.isStill && media.duration < seconds ? 'hold-last-frame' : null };
        result.framing={method:framing.method,scale:framing.scale,position:framing.position,background:framing.background,viewport:viewport.rect,viewport_method:viewport.method,samples:viewport.samples||0,video_sampled:framing.video_sampled,warnings:viewport.warnings||[]};
        SLCopyPaste.rememberTarget(t);
        result.undo = 'Copy Paste - next media slot';
        if (!target) undoRecord=SLCopyPaste.rememberUndo(t, result.undo,beforeRevision,{root:oldRoot,comment:String(oldComment),name:String(oldTargetName)});
        tick('verification');result.performance=timings;SLCopyPaste.lastPerformance=timings;SLCopyPaste.lastFraming=result.framing;SLCopyPaste.lastProjection=typeof SLCopyPasteViewport!=='undefined'?SLCopyPasteViewport.lastProjection:null;
        return result;
    } catch (e) {
        for(i=expressionChanges.length-1;i>=0;i--)try{expressionChanges[i].property.expression=expressionChanges[i].before;expressionChanges[i].property.expressionEnabled=expressionChanges[i].enabled;}catch(_){rollback=false;}
        for (i = changed.length - 1; i >= 0; i--) try { if(changed[i].added)changed[i].layer.remove();else{changed[i].layer.locked = false; changed[i].layer.replaceSource(changed[i].source, false); changed[i].layer.name = changed[i].name; changed[i].layer.locked = changed[i].locked;} } catch (_) { rollback = false; }
        if(rootCommentBefore!==null)try{oldRoot.comment=rootCommentBefore;}catch(_){rollback=false;}
        try { if (t.layer.source !== oldRoot) t.layer.replaceSource(oldRoot, false); t.layer.name = oldTargetName; t.layer.comment = oldComment; } catch (_) { rollback = false; }
        for (i = created.length - 1; i >= 0; i--) try { created[i].remove(); } catch (_) { rollback = false; }
        var failure = new Error(rollback ? 'The paste could not finish. Its changes were rolled back; the next slot did not advance. Try again.' : 'The paste stopped and some new items may remain. Undo Copy Paste before trying again.');
        failure.code = 'copy_paste_native'; failure.userFacing = true; failure.details = String(e.message || e); failure.rollback_complete = rollback; throw failure;
    } finally { if (undo) {app.endUndoGroup();if(undoRecord)undoRecord.revision=app.project.revision;} }
};
SLCopyPaste.fromFiles = function (p, target) {
    var M = SLCopyPasteModel, id = String(p.request_id || ''), imported = null, beforeClipboard = SLCopyPaste.clipboard, undo = false, undoRecord=null;
    SLCopyPaste.receipts = SLCopyPaste.receipts || {};
    if (id && SLCopyPaste.receipts[id]) return SLCopyPaste.receipts[id];
    if (!p.paths || p.paths.length !== 1 || typeof p.paths[0] !== 'string' || !/\.(?:jpe?g|png|tiff?|bmp|gif|psd|exr|tga|mp4|mov|avi|mxf|m4v|webm)$/i.test(p.paths[0])) M.fail('copy_paste_media', 'Select one picture or video in Explorer, press Copy media, then select the template and press Paste next.');
    var t = target || SLCopyPaste.target(), file = new File(p.paths[0]), media = null,beforeRevision=app.project.revision,beforeTarget={root:t.root,comment:String(t.layer.comment),name:String(t.layer.name)};
    if (!file.exists) M.fail('copy_paste_media', 'The copied file is no longer available. Copy the picture or video in Explorer again.');
    var normalized = String(file.fsName).replace(/\\/g, '/').toLowerCase();
    for (var i = 1; i <= app.project.numItems; i++) { var item = app.project.item(i); if (item instanceof FootageItem && item.file && String(item.file.fsName).replace(/\\/g, '/').toLowerCase() === normalized) { media = item; break; } }
    try {
        app.beginUndoGroup('Copy Paste file into next slot'); undo = true;
        if (!media) {
            var options = new ImportOptions(file);
            if (typeof ImportAsType !== 'undefined' && options.canImportAs && options.canImportAs(ImportAsType.FOOTAGE)) options.importAs = ImportAsType.FOOTAGE;
            options.sequence = false; media = app.project.importFile(options); imported = media;
        }
        if (!(media instanceof FootageItem) || !media.hasVideo) M.fail('copy_paste_media', 'After Effects could not open this as a picture or video. Choose another media file.');
        SLCopyPaste.clipboard = { id: media.id, name: media.name, file: media.file.fsName, framing:p.framing||(beforeClipboard&&beforeClipboard.file===media.file.fsName?beforeClipboard.framing:null) };
        var result = SLCopyPaste.paste(p, t); result.undo = 'Copy Paste file into next slot';
        undoRecord=SLCopyPaste.rememberUndo(t, result.undo,beforeRevision,beforeTarget);
        if (id) SLCopyPaste.receipts[id] = result;
        return result;
    } catch (e) {
        SLCopyPaste.clipboard = beforeClipboard;
        if (imported) try { imported.remove(); } catch (_) {}
        throw e;
    } finally { if (undo) {app.endUndoGroup();if(undoRecord)undoRecord.revision=app.project.revision;} }
};
SLCopyPaste.rememberUndo = function(t, title,beforeRevision,beforeTarget) {
    SLCopyPaste.history = SLCopyPaste.history || [];
    var previous=SLCopyPaste.history.length?SLCopyPaste.history[SLCopyPaste.history.length-1]:null;
    if(previous&&previous.revision!==beforeRevision)SLCopyPaste.history=[];
    SLCopyPaste.history.push({project:app.project,revision:app.project.revision,beforeRevision:beforeRevision,before:beforeTarget,comp:t.comp,layer:t.layer,root:t.layer.source,name:String(t.layer.name),comment:String(t.layer.comment),title:title});
    return SLCopyPaste.history[SLCopyPaste.history.length-1];
};
SLCopyPaste.undoLast = function() {
    var history=SLCopyPaste.history||[],last=history.length?history[history.length-1]:null,M=SLCopyPasteModel;
    if(!last || last.project!==app.project || typeof last.revision!=='number' || app.project.revision!==last.revision || last.layer.source!==last.root || String(last.layer.name)!==last.name || String(last.layer.comment)!==last.comment)
        M.fail('copy_paste_stale','There is no unchanged Storylens paste to undo. Your other edits are kept.');
    var command=app.findMenuCommandId('Undo '+last.title);
    if(!command)M.fail('copy_paste_stale','Your latest edit is not this Storylens paste. Use AE History to review it; no edit was undone.');
    if(typeof last.comp.openInViewer==='function'){var undoViewer=last.comp.openInViewer();if(undoViewer&&typeof undoViewer.setActive==='function')undoViewer.setActive();else if(app.activeViewer&&typeof app.activeViewer.setActive==='function')app.activeViewer.setActive();}
    app.executeCommand(command);
    if(app.project.revision===last.revision&&last.layer.source===last.root&&String(last.layer.name)===last.name&&String(last.layer.comment)===last.comment)
        M.fail('copy_paste_native','After Effects did not undo the paste. Wait for any autosave or dialog to finish, then try Undo again.');
    if(!last.before || last.layer.source!==last.before.root || String(last.layer.name)!==last.before.name || String(last.layer.comment)!==last.before.comment)
        M.fail('copy_paste_native','AE Undo ran, but its restored state could not be confirmed. Check AE History before another Undo.');
    history.pop();
    var previous=history.length?history[history.length-1]:null;
    if(previous&&previous.project===app.project&&previous.revision===last.beforeRevision&&previous.layer.source===previous.root&&String(previous.layer.name)===previous.name&&String(previous.layer.comment)===previous.comment)previous.revision=app.project.revision;
    var t={comp:last.comp,layer:last.layer,root:last.layer.source},result=SLCopyPaste.describe(t,SLCopyPaste.read(t));result.undone=true;return result;
};
SLCopyPaste.dispatch = function (request) {
    var p = request || {}, M = SLCopyPasteModel, renderingBefore=null;
    try {
        SLCopyPaste.checkProject();
        if((p.action==='paste'||p.action==='pasteFiles')&&typeof app.disableRendering==='boolean'){
            renderingBefore=app.disableRendering;app.disableRendering=true;
        }
        if(typeof StorylensTemplateImportJob!=='undefined'&&StorylensTemplateImportJob&&StorylensTemplateImportJob.project===app.project&&StorylensTemplateImportJob.running)M.fail('copy_paste_native','The templates are still importing. Wait for Import Template to finish, then press Copy or Paste again.');
        if (p.action === 'clear') { SLCopyPaste.clipboard = null; return {ok:true,cleared:true}; }
        if(p.action==='rememberFraming'){
            var clip=SLCopyPaste.clipboard;
            if(!clip||!p.clipboard||clip.file!==p.clipboard.file||String(clip.id)!==String(p.clipboard.id))M.fail('copy_paste_stale','The copied media changed during framing. Copy it again.');
            var f=p.framing;if(!f||f.version!==1||!(f.width>0&&f.height>0)||!(f.faces instanceof Array)||f.faces.length>1000)M.fail('copy_paste_media','The picture framing response is invalid. Copy it again.');
            clip.framing=f;return {ok:true,copied:true,clipboard:clip};
        }
        if (p.action === 'undo') return SLCopyPaste.undoLast();
        if (p.action === 'copyFile') {
            SLCopyPaste.clipboard = null;
            if (!p.paths || p.paths.length !== 1 || typeof p.paths[0] !== 'string' || !/\.(?:jpe?g|png|tiff?|bmp|gif|psd|exr|tga|mp4|mov|avi|mxf|m4v|webm)$/i.test(p.paths[0])) M.fail('copy_paste_media','Select one image or video in Explorer, then press Copy.');
            var copiedFile = new File(p.paths[0]); if (!copiedFile.exists) M.fail('copy_paste_media','The selected file is unavailable. Select it again in Explorer.');
            SLCopyPaste.clipboard = {kind:'file',name:copiedFile.name,file:copiedFile.fsName}; return {ok:true,copied:true,clipboard:SLCopyPaste.clipboard};
        }
        if (p.action === 'pasteFiles') return SLCopyPaste.fromFiles(p);
        if (p.action === 'copy') return SLCopyPaste.copy();
        if (p.action === 'paste') return SLCopyPaste.paste(p);
        var t = SLCopyPaste.target(), r;
        if (p.action === 'reset') {
            var scan = M.scan(SLCopyPaste.graph(t.root), t.root.id), next = Number(p.next);
            if (!isFinite(next) || next < 0 || next % 1 || next > scan.slots.length) M.fail('copy_paste_stale', 'Choose an existing next slot.');
            // The next paste will fork again: reset never assumes shared comps are owned.
            app.beginUndoGroup('Copy Paste - choose next slot');
            try { t.layer.comment = M.writeState(t.layer.comment, { owner: 0, root: t.root.id, next: next, signature: scan.signature }); } finally { app.endUndoGroup(); }
            r = { scan: scan, next: next };
        } else if (p.action === 'inspect') r = SLCopyPaste.read(t);
        else M.fail('copy_paste_native', 'Choose Copy, Paste or Undo.');
        return SLCopyPaste.describe(t, r);
    } catch (e) {
        return { error: e.userFacing ? String(e.message || e) : 'Copy Paste could not finish. Select the picture and template again, then retry the unfinished step.', code: e.code || 'copy_paste_native', details: e.details || String(e), rollback_complete: e.rollback_complete };
    } finally { if(renderingBefore!==null)app.disableRendering=renderingBefore; }
};
function storylensPanelCopyPaste(request) { return SLCopyPaste.json(SLCopyPaste.dispatch(request)); }

