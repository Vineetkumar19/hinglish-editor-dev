(function(root){var m=typeof module!=='undefined'&&module.exports?require('./model.js'):root.SLToolkitModel,n=m.number,c=m.choice;
 m.register({id:'masks',name:'Masks & Tracking'},[
 {number:61,id:'matte',name:'Track Matte Helper',help:'Select two layers. Use the upper selected layer as the matte for the lower one.',settings:[c('mode','Matte','alpha',['alpha','alpha-inverted','luma','luma-inverted'])]},
 {number:62,id:'rounded-crop',name:'Rounded Crop',help:'Add an editable rounded mask, intersecting existing masks when present.',settings:[n('width','Width (%)',90,1,100,1),n('height','Height (%)',90,1,100,1),n('radius','Corner radius (px)',40,0,1000,1)]},
 {number:63,id:'green-screen',name:'Green Screen',help:'Apply installed Keylight. Sample the actual screen colour and refine the matte in Effect Controls.',settings:[{id:'color',label:'Screen colour',type:'color',value:'#00ff00'},n('gain','Screen gain',100,0,200,1),n('balance','Screen balance',50,0,100,1)]},
 {number:64,id:'roto-assistant',name:'Roto Assistant',help:'Prepare a separate source copy in Layer view. You must paint the Roto Brush selection, review propagation and Freeze it.',settings:[]},
 {number:65,id:'tracked-blur',name:'Tracked Blur',help:'Select a visual layer and an already tracked null. Blur follows that null; review drift through the shot.',settings:[n('radius','Region radius (px)',100,1,2000,1),n('blur','Blur amount',50,0,500,1),n('feather','Feather (px)',30,0,500,1)]},
 {number:66,id:'screen-replace',name:'Screen Replacement',help:'Select a replacement layer, optionally with four tracked nulls named TL, TR, BL, BR. Otherwise adjust Corner Pin points manually.',settings:[]}
 ]);
})(typeof $!=='undefined'&&$.global?$.global:this);
