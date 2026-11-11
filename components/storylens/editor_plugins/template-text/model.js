/* Local expression-name relocation; no evaluation of model text. */
var SLTemplateTextModel=(function(){
    function expression(source, names, originalName) {
        source = String(source || '');
        if (!source || !/\b(?:comp\s*\(|thisComp\s*\.\s*name\b)/.test(source) || /\b(?:function|var|let|const)\s+comp\b/.test(source)) return source;
        var fn = '__storylensCompRef', serial = 1, aliases = [], key;
        while (source.indexOf(fn) >= 0) fn = '__storylensCompRef' + serial++;
        function quote(s) { return '"' + String(s).replace(/\\/g, '\\\\').replace(/"/g, '\\"').replace(/\r/g, '\\r').replace(/\n/g, '\\n').replace(/\u2028/g, '\\u2028').replace(/\u2029/g, '\\u2029') + '"'; }
        function literalArgument(open) {
            var pos=open+1,value='',q,c,esc;while(pos<source.length&&/\s/.test(source.charAt(pos)))pos++;
            q=source.charAt(pos++);if(q!=='"'&&q!=="'")return null;
            while(pos<source.length){c=source.charAt(pos++);if(c===q){while(pos<source.length&&/\s/.test(source.charAt(pos)))pos++;return source.charAt(pos)===')'?{value:value,end:pos+1}:null;}
                if(c==='\\'){esc=source.charAt(pos++);if(esc==='\\'||esc==='"'||esc==="'")c=esc;else if(esc==='n')c='\n';else if(esc==='r')c='\r';else if(esc==='t')c='\t';else return null;}value+=c;
            }return null;
        }
        var out = '', i = 0, start, ch, end, token, last = '', previous = '', changed = false, inClass, needsLookup=false;
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
                if (token === 'thisComp' && typeof originalName === 'string') { var nameAccess = /^\s*\.\s*name\b/.exec(source.slice(i)); if (nameAccess) { out += quote(originalName); i += nameAccess[0].length; changed = true; previous = 'string'; last = '"'; continue; } }
                if (token === 'comp' && last !== '.' && source.charAt(end) === '(') {
                    var literal=literalArgument(end);
                    if(literal){if(names.hasOwnProperty(literal.value)&&names[literal.value]){out+='comp('+quote(names[literal.value])+')';changed=true;}else out+=source.slice(start,literal.end);i=literal.end;previous=')';last=')';continue;}
                    out += fn; changed = true; needsLookup=true;
                } else out += token;
                previous = token; last = token.charAt(token.length - 1); continue;
            }
            out += ch; i++; if (!/\s/.test(ch)) { last = ch; previous = ch; }
        }
        if(!changed)return source;
        if(!needsLookup)return out;
        for (key in names) if (names.hasOwnProperty(key)) aliases.push(quote(key) + ':' + quote(names[key]));
        return 'function ' + fn + '(name){var names={' + aliases.join(',') + '};return comp(names[name]||name);}\n' + out;
    }
    function decorationCandidate(name) {
        name=String(name||'').replace(/[_-]/g,' ');
        if(/photo|image|picture|footage|scene|texture|wall|collage|full.?screen/i.test(name))return false;
        return /under\s*line|^line\s*\d*$|^bar\s*\d*$|^paper(?:\s*\d+)?$|^torn paper\s*\d*(?:\.png)?$|^shape layer\s*\d*$|backplate|label|(?:text|title|heading|caption).*(?:paper|strip|background|plate|line|box|shadow)|(?:paper|strip|background|plate|line|box|shadow).*(?:text|title|heading|caption)/i.test(name);
    }
    function decorationOwners(nodes) {
        var out=[],texts=[],byId={},i,j;
        for(i=0;i<nodes.length;i++){byId[nodes[i].id]=nodes[i];if(nodes[i].text)texts.push(nodes[i]);}
        for(i=0;i<nodes.length;i++){
            var d=nodes[i],owners=[],r=d.rect;
            if(d.text||d.matte||d.protectedLayer||!decorationCandidate(d.name))continue;
            var explicit=d.ownerIds||[];
            for(j=0;j<explicit.length;j++)if(byId[explicit[j]]&&byId[explicit[j]].text)owners.push(explicit[j]);
            if(!owners.length&&(d.dedicatedTitle||!/^(?:(?:torn )?paper|shape layer)\s*\d*(?:\.png)?$/i.test(d.name))&&r&&r.w>0&&r.h>0){
                var overlapping=[];
                for(j=0;j<texts.length;j++){
                    var t=texts[j],b=t.rect;if(!b||b.w<=0||b.h<=0)continue;
                    if((r.space||'')!==(b.space||'')||Math.abs((r.z||0)-(b.z||0))>12)continue;
                    // Compact adjacent/overlapping title furniture only. A large
                    // paper background must never disappear with a small caption.
                    var horizontal=Math.min(r.x+r.w,b.x+b.w)-Math.max(r.x,b.x);
                    var gap=Math.max(0,r.y-(b.y+b.h),b.y-(r.y+r.h));
                    var centeredLabel=d.dedicatedTitle&&Math.abs(r.x+r.w/2-b.x-b.w/2)<=Math.max(12,b.w*.1)&&Math.abs(r.y+r.h/2-b.y-b.h/2)<=Math.max(12,b.h*.35);
                    if(horizontal>=Math.min(r.w,b.w)*.6&&gap<=Math.max(12,b.h*.35)&&r.w<=b.w*1.8&&r.h<=b.h*(centeredLabel?4:2.6)){owners.push(t.id);if(Math.min(r.y+r.h,b.y+b.h)-Math.max(r.y,b.y)>0)overlapping.push(t.id);}
                }
                if(overlapping.length)owners=overlapping;
            }
            if(owners.length)out.push({id:d.id,owners:owners});
        }
        return out;
    }
function titleGeometry(samples,w,h){
 var heights=[],good=0;for(var i=0;i<samples.length;i++){var b=samples[i],bw=b.right-b.left,bh=b.bottom-b.top;if(!isFinite(bw+bh)||bw<=0||bh<=0)continue;
  var visible=Math.max(0,Math.min(w,b.right)-Math.max(0,b.left))*Math.max(0,Math.min(h,b.bottom)-Math.max(0,b.top))/(bw*bh);
  heights.push(bh*1080/h);if(visible>=.8&&bh*1080/h>=20&&bw*1920/w>=30)good++;
 }heights.sort(function(a,b){return a-b;});return {usable:good>=2,height:heights.length?heights[Math.floor(heights.length/2)]:0,samples:samples};
}
return {expression:expression,decorationCandidate:decorationCandidate,decorationOwners:decorationOwners,titleGeometry:titleGeometry};
})();
