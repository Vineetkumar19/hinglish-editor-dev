(function(root){var m=typeof module!=='undefined'&&module.exports?require('./model.js'):root.SLToolkitModel,n=m.number,c=m.choice;
 m.register({id:'typography',name:'Typography & Layout'},[
 {number:19,id:'text-box',name:'Responsive Text Box',help:'Create a shape behind each selected 2D text layer. The box follows text edits and transforms.',settings:[n('padding','Padding (px)',20,0,300,1),n('roundness','Corner radius (px)',12,0,300,1),{id:'color',label:'Box colour',type:'color',value:'#181818'}]},
 {number:20,id:'auto-fit',name:'Auto-fit Text',help:'Fit static unparented 2D text within a width and height, preserving its words and font.',settings:[n('width','Width (px)',800,10,16000,1),n('height','Height (px)',400,10,16000,1),c('upscale','Allow enlargement','no',['no','yes'])]},
 {number:21,id:'line-breaks',name:'Balance Lines',help:'Balance complete words across lines. Changes line breaks; retains word order.',settings:[n('words','Maximum words per line',4,1,30,1)]},
 {number:22,id:'split-text',name:'Split Text Layers',help:'Split a static single-line point-text layer into editable words. Keep the original disabled for recovery.',settings:[]},
 {number:23,id:'text-style',name:'Copy / Paste Text Style',help:'Copy the first character’s style, then apply it uniformly to selected text. Destination words stay unchanged.',settings:[c('mode','Action','copy',['copy','paste'])]},
 {number:24,id:'lower-third',name:'Lower-third Builder',help:'Create an editable name and subtitle graphic in the active timeline.',settings:[{id:'title',label:'Name',type:'text',value:'Your name',maxLength:100},{id:'subtitle',label:'Subtitle',type:'text',value:'Your title',maxLength:160},n('duration','Duration (s)',5,1,60,.1),{id:'color',label:'Accent',type:'color',value:'#d9e56c'}]}
 ]);
})(typeof $!=='undefined'&&$.global?$.global:this);
