(function(root){var m=typeof module!=='undefined'&&module.exports?require('./model.js'):root.SLToolkitModel,n=m.number,c=m.choice;function color(id,label,value){return {id:id,label:label,type:'color',value:value};}
 m.register({id:'styling',name:'Layer Styling'},[
 {number:25,id:'shadow',name:'Drop Shadow',help:'Add or update an editable native shadow on selected visual layers.',settings:[n('opacity','Opacity (%)',60,0,100,1),n('distance','Distance (px)',10,0,500,1),n('softness','Softness (px)',25,0,500,1),n('angle','Direction (degrees)',135,-360,360,1),color('color','Shadow colour','#000000')]},
 {number:26,id:'outline',name:'Outline',help:'Create a coloured alpha expansion behind selected transparent artwork. Original layers stay intact.',settings:[n('width','Thickness (px)',6,1,100,1),color('color','Outline colour','#ffffff')]},
 {number:27,id:'light-sweep',name:'Light Sweep',help:'Animate native CC Light Sweep across selected layers. Requires that bundled effect to be available.',settings:[n('duration','Duration (s)',1,.1,30,.1),n('width','Sweep width',80,1,500,1),n('intensity','Intensity',50,0,200,1)]},
 {number:28,id:'glow',name:'Glow',help:'Add or update native Glow radius and intensity. All other Glow controls remain available in AE.',settings:[n('radius','Radius (px)',20,0,500,1),n('intensity','Intensity',.8,0,10,.1)]},
 {number:29,id:'rgb-split',name:'RGB Split',help:'Create separate red, green and blue layers with a horizontal offset. Keep the original disabled for recovery.',settings:[n('distance','Separation (px)',8,0,200,1)]},
 {number:30,id:'effect-stack',name:'Copy / Paste Effect Stack',help:'Copy supported effect properties and keys, then paste onto selected layers in this composition.',settings:[c('mode','Action','copy',['copy','paste'])]}
 ]);
 m.register({id:'colour',name:'Colour'},[
 {number:55,id:'exposure-contrast',name:'Exposure & Contrast',help:'Editable native exposure and contrast effects; tune by eye for your footage.',settings:[n('exposure','Exposure (stops)',.25,-5,5,.05),n('contrast','Contrast',10,-100,100,1)]},
 {number:56,id:'white-balance',name:'White Balance',help:'Adjust midtone red/blue balance and green tint. Review skin tones after applying.',settings:[n('temperature','Warm / cool',10,-100,100,1),n('tint','Magenta / green',0,-100,100,1)]},
 {number:57,id:'saturation',name:'Saturation',help:'Adjust native Master Saturation without replacing other colour effects.',settings:[n('amount','Saturation adjustment',15,-100,100,1)]},
 {number:58,id:'duotone',name:'Duotone',help:'Map shadows and highlights to two editable colours.',settings:[color('shadows','Shadows','#151a36'),color('highlights','Highlights','#ffdf8c'),n('amount','Strength (%)',100,0,100,1)]},
 {number:59,id:'spot-color',name:'Black & White + Spot Colour',help:'Use native Leave Color. Choose the colour to keep, then refine tolerance on the actual footage.',settings:[color('color','Colour to keep','#ff0000'),n('tolerance','Tolerance (%)',15,0,100,1),n('softness','Edge softness (%)',10,0,100,1)]},
 {number:60,id:'color-look',name:'Colour Looks',help:'Editable warm, cool, soft or monochrome starting looks. Review and tune for each shot.',settings:[c('look','Look','warm',['warm','cool','soft','monochrome']),n('amount','Strength (%)',60,0,100,1)]}
 ]);
})(typeof $!=='undefined'&&$.global?$.global:this);
