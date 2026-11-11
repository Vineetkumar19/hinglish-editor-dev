(function(root){var m=typeof module!=='undefined'&&module.exports?require('./model.js'):root.SLToolkitModel,c=m.choice;
 m.register({id:'library',name:'Library & Templates'},[
 {number:85,id:'favourites',name:'Favourites & Recent',ui:'favourites',help:'Star any tool to keep it here. Recent lists tools successfully applied from this panel.',settings:[]},
 {number:86,id:'search-tools',name:'Search & Tags',ui:'search',help:'Search names, descriptions and categories across the whole toolkit.',settings:[]},
 {number:87,id:'preview-cache',name:'Capture Motion Preview',help:'Capture eight actual frames from the selected precomp (or open comp) starting at its playhead. Attach the cached preview to a tool ID shown on its card.',settings:[{id:'tool',label:'Tool ID',type:'text',value:'lower-third',maxLength:80}]},
 {number:88,id:'save-preset',name:'Save / Apply My Preset',help:'Save selected properties with AE’s native .ffx dialog, or choose an existing .ffx to apply to selected layers.',settings:[c('mode','Action','save',['save','apply'])]},
 {number:89,id:'reset-toolkit',name:'Reset / Replace',help:'Disable toolkit expressions and owned text animators/effects while retaining their settings. Replace swaps one selected layer’s source with one selected Project item.',settings:[c('mode','Action','reset',['reset','replace'])]},
 {number:90,id:'batch-variations',name:'Batch Variations',help:'Deep-copy one selected precomp and replace the named static text layer in each copy. One line per version: Name | New text. Original stays intact.',settings:[{id:'target',label:'Text layer name',type:'text',value:'Title',maxLength:100},{id:'rows',label:'Versions',type:'text',multiline:true,value:'Version 1 | First title\nVersion 2 | Second title',maxLength:6000}]}
 ]);
})(typeof $!=='undefined'&&$.global?$.global:this);
