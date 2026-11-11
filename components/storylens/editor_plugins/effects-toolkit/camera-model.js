(function(root){var m=typeof module!=='undefined'&&module.exports?require('./model.js'):root.SLToolkitModel,n=m.number;
 m.register({id:'camera',name:'Camera & 3D'},[
 {number:67,id:'camera-rig',name:'Camera + Null Rig',help:'Rig a selected static camera, or create a new camera if the composition has none.',settings:[]},
 {number:68,id:'camera-orbit',name:'Camera Orbit',help:'Rig a selected static camera and animate an orbit around the composition centre.',settings:[n('duration','Duration (s)',3,.1,60,.1),n('angle','Orbit angle',20,-180,180,1)]},
 {number:69,id:'parallax',name:'Parallax',help:'Select two or more unparented 2D planes. Creates a separate scene with depth compensation and camera movement.',settings:[n('depth','Depth spacing (px)',150,1,1000,1),n('travel','Camera travel (px)',80,-2000,2000,1),n('duration','Motion duration (s)',5,.1,60,.1)]},
 {number:70,id:'title-3d',name:'Extruded 3D Title',help:'Create a separate native Cinema 4D text scene. Existing caption designs and the current renderer stay unchanged.',settings:[{id:'title',label:'Title',type:'text',value:'YOUR TITLE',maxLength:100},n('depth','Extrusion (px)',40,1,300,1),n('angle','Y rotation',-15,-80,80,1),n('duration','Duration (s)',5,1,60,.1),{id:'color',label:'Text colour',type:'color',value:'#f4f4f4'}]},
 {number:71,id:'ground-shadow',name:'Ground & Shadow',help:'Create a separate 3D scene from selected unparented 2D layers, with a floor and shadow-casting light.',settings:[n('height','Floor position (%)',70,10,95,1),n('darkness','Shadow darkness (%)',65,0,100,1)]},
 {number:72,id:'focus-pull',name:'Focus Pull',help:'Animate focus distance on one selected camera. Depth of field and aperture become editable.',settings:[n('duration','Duration (s)',2,.1,60,.1),n('near','Start distance',1000,1,50000,1),n('far','End distance',1800,1,50000,1),n('aperture','Aperture',100,0,1000,1)]}
 ]);
})(typeof $!=='undefined'&&$.global?$.global:this);
