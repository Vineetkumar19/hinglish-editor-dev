/* ES3, deterministic output selection. Helpers and placeholders are never outputs. */
(function(root,factory){var api=factory();if(typeof module!=='undefined'&&module.exports)module.exports=api;else root.SLEffectsModel=api;})(this,function(){
 function helper(name){if(/(?:^|[^a-z])(?:controls?|controllers?|placeholders?|replace|logos?|assets?|textures?|backgrounds?|audio|music|sfx|solids?)(?:[^a-z]|$)/i.test(name))return true;return !/(?:^|[^a-z])(?:main|master|final|render|output|delivery)(?:[^a-z]|$)/i.test(name)&&/(?:^|[^a-z])(?:footage|videos?|images?|photos?)(?:[^a-z]|$)/i.test(name);}
 function outputs(rows){var candidates=[],named=[],i;for(i=0;i<rows.length;i++){var r=rows[i];if(r.used||!(r.duration>0)||helper(r.name))continue;candidates.push(r);if(/(?:^|[^a-z])(?:main|master|final|render|output|delivery)(?:[^a-z]|$)/i.test(r.name))named.push(r);}var choices=named.length?named:candidates;return {selected:choices.length===1?String(choices[0].id):null,choices:choices};}
 return {outputs:outputs,helper:helper};
});
