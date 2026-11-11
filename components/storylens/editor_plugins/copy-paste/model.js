/* ES3 deterministic slot discovery. Names are data, never executable code. */
var SLCopyPasteModel = (function () {
    function fail(code, message, details) { var e = new Error(message); e.code = code; e.userFacing = true;if(details)e.details=details;throw e; }
    function natural(a, b) {
        var aa = String(a).toLowerCase().match(/\d+|\D+/g) || [], bb = String(b).toLowerCase().match(/\d+|\D+/g) || [], i;
        for (i = 0; i < Math.min(aa.length, bb.length); i++) {
            if (aa[i] === bb[i]) continue;
            if (/^\d+$/.test(aa[i]) && /^\d+$/.test(bb[i])) return Number(aa[i]) - Number(bb[i]);
            return aa[i] < bb[i] ? -1 : 1;
        }
        return aa.length - bb.length;
    }
    function excluded(name) {
        if (/(?:^|[^a-z])(?:controllers?|brush(?:es)?|contours?|particles?|textures?|backgrounds?|bg|overlays?|light leaks?|flares?|grains?|dust|smoke|noise|vignettes?|audio|music|sfx|texts?|titles?|logos?)(?:[^a-z]|$)/i.test(name)) return true;
        if (!positive(name) && /(?:^|[^a-z])(?:fx|clouds?|leaks?|old film|film.rolls?|grunge|light.transitions?|papers?|polaroids?|old_polaroid|frame borders?|borders?|icons?|emoji|sparks?|compass|ropes?|envelopes?|wipes?|notebook)(?:[^a-z]|$)/i.test(name)) return true;
        return /(?:^|[^a-z])(?:masks?|envato|watermarks?)(?:[^a-z]|$)/i.test(name) && !positive(name);
    }
    function control(row, comp) {
        return row.nullLayer === true || row.adjustment === true || row.guide === true || row.matte === true || (row.solid && comp.hasText && !row.wrapped && !row.placeholder && !positive(row.name + ' ' + (row.sourceName || '')));
    }
    function positive(name) {
        return /(?:^|[^a-z])(?:images?|photos?|pictures?|videos?|footage|media|placeholders?|replace)(?:[^a-z]|$)/i.test(name);
    }
    function scan(graph, root) {
        var slots = [], groups = {}, visiting = {}, touched = {}, ancestors = {}, checked = 0;
        function walk(id, path, chain, hint) {
            var c = graph[id], rows, i, row, name, key, slot, nextChain;
            if (!c) fail('copy_paste_stale', 'A nested composition is no longer available. Read the template again.');
            if (visiting[id]) fail('copy_paste_template', 'This template has a circular composition path. Check its nested compositions.');
            if (chain.length > 40 || ++checked > 6000) fail('copy_paste_template', 'This template is too large to scan safely in one paste. Select a smaller scene.');
            visiting[id] = true; touched[id] = true;
            rows = c.layers.slice(0);
            hint = hint || c.structuralHolder === true;
            // Some stock templates use a labelled solid canvas rather than footage.
            // Fill above its original label/solids; keep those original layers intact.
            if (c.placeholderCanvas === true) {
                var filledRows=[];
                for(i=0;i<rows.length;i++)if(rows[i].wrapped)filledRows.push(rows[i]);
                if(filledRows.length>1)fail('copy_paste_template','This picture canvas has more than one replacement. Select a separate holder.');
                key=String(id)+':canvas';nextChain=chain.concat([String(id)]);
                if(!groups[key]){slot={comp:String(id),layers:filledRows.length?[filledRows[0].index]:[],empty:!filledRows.length,canvas:true,name:c.name,path:path.join(' > '),source:filledRows.length?filledRows[0].source:null,ancestors:nextChain};groups[key]=slot;slots.push(slot);}
                for(i=0;i<nextChain.length;i++)ancestors[nextChain[i]]=true;
                visiting[id]=false;return;
            }
            // A shared holder name is not enough to choose among unrelated,
            // unnamed source layers. Refuse before any native cloning or paste.
            var solidOnly = true;
            for (var sq = 0; sq < rows.length; sq++) if (rows[sq].kind === 'media' && !rows[sq].solid && !control(rows[sq],c) && !excluded(rows[sq].name + ' ' + (rows[sq].sourceName || ''))) solidOnly = false;
            var candidates = {}, candidateCount = 0, unnamed = false;
            for (var aq = 0; aq < rows.length; aq++) {
                var ar = rows[aq];
                if (ar.kind !== 'media' || ar.hasVideo === false || control(ar,c) || (ar.solid && !solidOnly) || excluded(ar.name + ' ' + (ar.sourceName || ''))) continue;
                var sourceKey = '$' + String(ar.source);
                if (!candidates[sourceKey]) { candidates[sourceKey] = true; candidateCount++; }
                if (!ar.wrapped && !ar.placeholder && !positive(ar.name + ' ' + (ar.sourceName || ''))) unnamed = true;
            }
            if (hint && candidateCount > 1 && unnamed) {var debug=['Holder: '+c.name+' (#'+id+')'];for(var di=0;di<rows.length;di++){var dr=rows[di];debug.push(dr.index+' | '+dr.name+' | '+dr.sourceName+' | source='+dr.source+' | '+dr.kind+' | solid='+!!dr.solid+' | placeholder='+!!dr.placeholder);}fail('copy_paste_template', 'This picture holder contains multiple unnamed media sources, so Storylens cannot safely choose one. Select a separate picture holder or another template. No media was changed.',debug.join('\n'));}
            if (!rows.length && !c.hasText && (hint || positive(c.name))) {
                key = String(id) + ':empty'; nextChain = chain.concat([String(id)]);
                if (!groups[key]) { slot = {comp:String(id),layers:[],empty:true,name:c.name,path:path.join(' > '),source:null,ancestors:nextChain};groups[key]=slot;slots.push(slot); }
                for (var en = 0; en < nextChain.length; en++) ancestors[nextChain[en]] = true;
            }
            rows.sort(function (a, b) { return a.start - b.start || natural(a.name, b.name) || a.index - b.index; });
            for (i = 0; i < rows.length; i++) {
                row = rows[i]; name = row.name + ' ' + (row.sourceName || '');
                if (excluded(name) || control(row,c)) continue;
                nextChain = chain.concat([String(id)]);
                if (row.kind === 'comp') {
                    walk(row.source, path.concat([row.name]), nextChain, hint || positive(name));
                } else if (row.kind === 'media' && row.hasVideo !== false && (row.wrapped || row.placeholder || ((!row.solid || solidOnly) && (hint || positive(name))))) {
                    // Repeated uses of the same footage inside ONE holder are one logical slot.
                    key = String(id) + ':' + String(row.source);
                    slot = groups[key];
                    if (!slot) {
                        slot = { comp: String(id), layers: [], name: c.name + ' / ' + row.name,
                            path: path.concat([row.name]).join(' > '), source: row.source, ancestors: nextChain };
                        groups[key] = slot; slots.push(slot);
                    }
                    var listed = false;
                    for (var z = 0; z < slot.layers.length; z++) if (slot.layers[z] === row.index) listed = true;
                    if (!listed) slot.layers.push(row.index);
                    for (var n = 0; n < nextChain.length; n++) ancestors[nextChain[n]] = true;
                }
            }
            visiting[id] = false;
        }
        walk(String(root), [], [], positive(graph[root] ? graph[root].name : ''));
        var sig = [], j;
        for (j = 0; j < slots.length; j++) {
            slots[j].layers.sort(function (a, b) { return a - b; });
            slots[j].key = slots[j].comp + ':' + (slots[j].canvas?'canvas':slots[j].layers.join(','));
            slots[j].number = j + 1; sig.push(slots[j].key);
        }
        if (slots.length > 300) fail('copy_paste_template', 'This template has more than 300 media slots. Select a smaller scene.');
        return { slots: slots, ancestors: ancestors, signature: sig.join(';'), scanned: checked };
    }
    function state(comment) {
        var m = String(comment || '').match(/(?:^|\n)\[Storylens Copy Paste v1\|owner=(\d+)\|root=(\d+)\|next=(\d+)\|sig=([^\]\r\n]*)\]/);
        return m ? { owner: m[1], root: m[2], next: Number(m[3]), signature: m[4] } : null;
    }
    function writeState(comment, s) {
        var clean = String(comment || '').replace(/(?:^|\n)\[Storylens Copy Paste v1\|[^\]\r\n]*\]/g, '');
        return clean + '\n[Storylens Copy Paste v1|owner=' + s.owner + '|root=' + s.root + '|next=' + s.next + '|sig=' + s.signature + ']';
    }
    function fit(w, h, aspect, sw, sh, sourceAspect, mode) {
        if (!(w > 0 && h > 0 && sw > 0 && sh > 0 && aspect > 0 && sourceAspect > 0)) fail('copy_paste_media', 'This media has no usable picture dimensions. Choose another image or video.');
        var x = w * aspect / (sw * sourceAspect), y = h / sh;
        return 100 * (mode === 'fit' ? Math.min(x, y) : Math.max(x, y));
    }
    function expression(source, names, inspection) {
        source = String(source || '');
        if (!source || source.indexOf('comp')<0 || /\b(?:function|var|let|const)\s+comp\b/.test(source)) return source;
        var fn = '__storylensCompRef', serial = 1, aliases = [], key, references={},dynamic=false;
        while (source.indexOf(fn) >= 0) fn = '__storylensCompRef' + serial++;
        function quote(s) { return '"' + String(s).replace(/\\/g, '\\\\').replace(/"/g, '\\"').replace(/\r/g, '\\r').replace(/\n/g, '\\n').replace(/\u2028/g, '\\u2028').replace(/\u2029/g, '\\u2029') + '"'; }
        function literalArgument(open) {
            var pos=open+1,value='',q,c,esc;while(pos<source.length&&/\s/.test(source.charAt(pos)))pos++;
            q=source.charAt(pos++);if(q!=='"'&&q!=="'")return null;
            while(pos<source.length){c=source.charAt(pos++);if(c===q){while(pos<source.length&&/\s/.test(source.charAt(pos)))pos++;return source.charAt(pos)===')'?{value:value,end:pos+1}:null;}
                if(c==='\\'){esc=source.charAt(pos++);if(esc==='\\'||esc==='"'||esc==="'")c=esc;else if(esc==='n')c='\n';else if(esc==='r')c='\r';else if(esc==='t')c='\t';else return null;}value+=c;
            }return null;
        }
        var out = '', i = 0, start, ch, end, token, last = '', previous = '', changed = false, inClass;
        while (i < source.length) {
            ch = source.charAt(i); start = i;
            if (ch === '"' || ch === "'" || ch === '`') {
                i++; while (i < source.length) { if (source.charAt(i) === '\\') i += 2; else if (source.charAt(i++) === ch) break; }
                out += source.slice(start, i); previous = 'string'; last = '"'; continue;
            }
            if (ch === '/' && source.charAt(i + 1) === '/') { while (i < source.length && source.charAt(i) !== '\n') i++; out += source.slice(start, i); continue; }
            if (ch === '/' && source.charAt(i + 1) === '*') { end = source.indexOf('*/', i + 2); i = end < 0 ? source.length : end + 2; out += source.slice(start, i); continue; }
            if (ch === '/' && (!last || /[=(:,\[!{;?&|]/.test(last) || /^(return|case|throw)$/.test(previous))) {
                i++; inClass = false;
                while (i < source.length) { ch = source.charAt(i++); if (ch === '\\') i++; else if (ch === '[') inClass = true; else if (ch === ']') inClass = false; else if (ch === '/' && !inClass) break; }
                while (/[a-z]/i.test(source.charAt(i)) && i < source.length) i++;
                out += source.slice(start, i); last = '/'; previous = 'regex'; continue;
            }
            if (/[A-Za-z_$]/.test(ch)) {
                i++; while (i < source.length && /[A-Za-z0-9_$]/.test(source.charAt(i))) i++;
                token = source.slice(start, i); end = i; while (/\s/.test(source.charAt(end)) && end < source.length) end++;
                if (token === 'comp' && last !== '.' && source.charAt(end) === '(') {
                    // Literal controls need no helper or alias-table compilation.
                    // Computed arguments keep the conservative dynamic mapping.
                    var literal=literalArgument(end);
                    if(literal){if(inspection)inspection.names.push(literal.value);if(names.hasOwnProperty(literal.value)&&names[literal.value]){out+='comp('+quote(names[literal.value])+')';changed=true;}else out+=source.slice(start,literal.end);i=literal.end;previous=')';last=')';continue;}
                    if(inspection)inspection.dynamic=true;
                    dynamic=true;
                    out += fn; changed = true;
                } else out += token;
                previous = token; last = token.charAt(token.length - 1); continue;
            }
            out += ch; i++; if (!/\s/.test(ch)) { last = ch; previous = ch; }
        }
        if(!changed)return source;
        if(!dynamic)return out;
        for (key in names) if (names.hasOwnProperty(key)&&(dynamic||references.hasOwnProperty(key))) aliases.push(quote(key) + ':' + quote(names[key]));
        return aliases.length ? 'function ' + fn + '(name){var names={' + aliases.join(',') + '};return comp(names[name]||name);}\n' + out : source;
    }
    function referencedComps(source){var result={names:[],dynamic:false};expression(source,{},result);return result;}
    function isolationSet(graph,root,target,refs,reusable){
        var parents={},expressionParents={},byName={},chosen={},queue=[String(target)],i,key;reusable=reusable||{};
        function edge(child,parent,table){table=table||parents;child=String(child);if(!table[child])table[child]=[];table[child].push(String(parent));}
        for(key in graph)if(graph.hasOwnProperty(key)){
            var c=graph[key],base=c.name.replace(/(?: \[Copy Paste \d+\])+$/,'');
            if(!byName[c.name])byName[c.name]=[];byName[c.name].push(key);
            if(base!==c.name){if(!byName[base])byName[base]=[];byName[base].push(key);}
            for(i=0;i<c.layers.length;i++)if(c.layers[i].kind==='comp')edge(c.layers[i].source,key);
        }
        for(key in refs)if(refs.hasOwnProperty(key)){
            if(refs[key].dynamic)return {graph:graph,mode:'full-controller-graph'};
            for(i=0;i<refs[key].names.length;i++){var ids=byName[refs[key].names[i]]||[];for(var j=0;j<ids.length;j++)edge(ids[j],key,expressionParents);}
        }
        while(queue.length){key=queue.pop();if(chosen[key]||!graph[key])continue;chosen[key]=graph[key];var up=parents[key]||[];for(i=0;i<up.length;i++)queue.push(up[i]);
            // Consumers need rewiring only when the referenced identity changes.
            // Keeping a private controller avoids cloning its unrelated scenes.
            if(!reusable[key]){up=expressionParents[key]||[];for(i=0;i<up.length;i++)queue.push(up[i]);}
        }
        if(!chosen[String(root)])fail('copy_paste_stale','The selected picture holder no longer belongs to this template.');
        return {graph:chosen,mode:'affected-branch'};
    }
    return { scan: scan, natural: natural, excluded: excluded, positive: positive, state: state, writeState: writeState, fit: fit, expression: expression, referencedComps:referencedComps,isolationSet:isolationSet,fail: fail };
})();
if (typeof module !== 'undefined' && module.exports) module.exports = SLCopyPasteModel;
