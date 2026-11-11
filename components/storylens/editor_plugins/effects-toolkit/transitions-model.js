(function(root){var m=typeof module!=='undefined'&&module.exports?require('./model.js'):root.SLToolkitModel,n=m.number,c=m.choice,d=n('duration','Duration (s)',.5,.1,5,.05);
 m.register({id:'transitions',name:'Transitions'},[
 {number:31,id:'whip',name:'Whip Transition',help:'Select two overlapping 2D clips. The upper layer enters; the lower layer leaves around the playhead.',settings:[d,c('direction','Direction','left',['left','right','up','down'])]},
 {number:32,id:'zoom-transition',name:'Zoom Transition',help:'Select two overlapping clips. Zoom and dissolve into the upper layer.',settings:[d,n('amount','Zoom (%)',30,1,150,1)]},
 {number:33,id:'flash-transition',name:'Flash Transition',help:'Select two overlapping clips. A white flash covers their transition at the playhead.',settings:[d,n('amount','Flash opacity (%)',100,0,100,1)]},
 {number:34,id:'blur-transition',name:'Directional Blur Transition',help:'Select two overlapping clips. Crossfade through native directional blur.',settings:[d,n('amount','Blur length',80,0,500,1),n('angle','Blur direction',90,-360,360,1)]},
 {number:35,id:'glitch-transition',name:'Glitch Transition',help:'Select two overlapping clips. Add short horizontal jolts, blur and a flickering dissolve.',settings:[d,n('amount','Displacement (px)',50,0,500,1),n('rate','Flickers per second',18,2,60,1)]},
 {number:36,id:'shape-reveal',name:'Shape Reveal Transition',help:'Select two overlapping clips. Reveal the upper clip through a rectangular mask; use an unmasked incoming layer.',settings:[d,c('direction','Reveal from','left',['left','right','up','down'])]}
 ]);
})(typeof $!=='undefined'&&$.global?$.global:this);
