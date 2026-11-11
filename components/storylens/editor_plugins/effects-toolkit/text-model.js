(function(root){var m=typeof module!=='undefined'&&module.exports?require('./model.js'):root.SLToolkitModel,n=m.number,d=n('duration','Duration (s)',1,.05,120,.05);
 m.register({id:'text',name:'Text Animation'},[
 {number:13,id:'masked-reveal',name:'Masked Reveal',help:'Reveal text through a moving rectangular mask. Use a text layer without existing masks.',settings:[d,n('feather','Feather (px)',2,0,100,1)]},
 {number:14,id:'tracking',name:'Tracking Expansion',help:'Letters settle from expanded spacing into the original text. Original wording and font stay editable.',settings:[d,n('amount','Initial tracking',80,-100,500,1)]},
 {number:15,id:'word-emphasis',name:'Word Emphasis',help:'Scale one chosen word. Word is counted from the start of this text layer.',settings:[n('word','Word number',1,1,1000,1),n('scale','Scale (%)',120,10,300,1)]},
 {number:16,id:'text-flip',name:'Text Flip',help:'A flat vertical character flip with a fade. No camera or 3D-layer changes.',settings:[d,n('stagger','Character stagger (%)',35,0,90,1)]},
 {number:17,id:'scramble',name:'Text Scramble',help:'Random letters resolve into the editable source text. Intended for text with one uniform style.',settings:[d,n('rate','Changes per second',12,1,60,1)]},
 {number:18,id:'line-reveal',name:'Line Reveal',help:'Reveal complete authored lines in reading order with upward motion and soft blur.',settings:[d,n('distance','Travel (px)',30,0,400,1),n('stagger','Line stagger (%)',45,0,90,1)]}
 ]);
})(typeof $!=='undefined'&&$.global?$.global:this);
