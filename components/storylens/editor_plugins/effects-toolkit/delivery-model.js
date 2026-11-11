(function(root){var m=typeof module!=='undefined'&&module.exports?require('./model.js'):root.SLToolkitModel,c=m.choice,n=m.number;
 var template={id:'renderTemplate',label:'Render template (blank = AE default)',type:'text',value:'',allowEmpty:true,maxLength:150},output={id:'outputTemplate',label:'Output template (blank = AE default)',type:'text',value:'',allowEmpty:true,maxLength:150};
 m.register({id:'delivery',name:'Project & Delivery'},[
 {number:91,id:'organize',name:'Organize Selected Assets',help:'Move selected Project-panel items into type folders under Storylens Assets. Original files and unselected items stay where they are.',settings:[]},
 {number:92,id:'relink',name:'Relink Missing Footage',help:'Choose a search folder. Relink only unique exact filename matches; ambiguous names remain for manual review.',settings:[]},
 {number:93,id:'dependencies',name:'Dependency Report',help:'Inspect missing media, used effects and text font names on request. The report does not change the project.',settings:[]},
 {number:94,id:'collect-assets',name:'Collect Asset Copies',help:'Copy file-based footage and proxies into a new folder, with a source manifest. Originals stay intact. This collects media, not unsaved project edits; save an AEP copy separately.',settings:[]},
 {number:95,id:'render-profile',name:'Render Profiles',help:'List installed AE render/output templates, then enter their exact names to queue the open comp. Queuing does not start rendering.',settings:[c('mode','Action','list',['list','queue']),template,output]},
 {number:96,id:'proof-export',name:'Export Short Proof',help:'Render up to 10 seconds from the work-area start. Other queued jobs are temporarily excluded and restored. Choose the output file in the native dialog.',settings:[n('duration','Proof duration (s)',5,.1,10,.1),template,output]}
 ]);
 function sequencePattern(name){var match=/^(.*?)(\d+)(\.(?:png|jpe?g|tiff?|exr|dpx|tga|bmp|psd))$/i.exec(name);if(!match)return null;return new RegExp('^'+match[1].replace(/[.*+?^${}()|[\]\\]/g,'\\$&')+'\\d{'+match[2].length+'}'+match[3].replace('.','\\.')+'$','i');}
 var api={sequencePattern:sequencePattern};root.SLToolkitDeliveryModel=api;if(typeof module!=='undefined'&&module.exports)module.exports=api;
})(typeof $!=='undefined'&&$.global?$.global:this);
