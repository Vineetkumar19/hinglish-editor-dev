const {test}=require('node:test'),fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
function harness(fail=false){
 const source=fs.readFileSync('hinglish_app/static/editor-panel.js','utf8'),a=source.indexOf('function createCaptionPatternView(){'),b=source.indexOf('\nasync function run(){',a);assert(a>=0&&b>a,'Production native loader must exist');
 let loads=0,created=0,removed=0;const controls={captionStyle:{value:'caption_2'},captionSettings:{querySelectorAll(){return [{remove(){removed++;}}];}},run:{}};
 const window={},c={window,host:'aftereffects',mode:'captions',generated:0,captionPatternView:{isSelected:()=>false,isRunning:()=>false},caption3dView:{isStandard:()=>true},$:id=>controls[id],native(){},error(e){throw e;},clearError(){},isEditingBusy:()=>false,setTimeout:()=>1,clearTimeout(){},document:{createElement:()=>({remove(){}}),head:{append(script){loads++;if(fail)return script.onerror();const factory=()=>{created++;return {supports:id=>id==='caption_2',isSelected:()=>true,sync(){},hasPending:()=>false,usesScriptTiming:()=>false,generateSpeech(){c.generated++;}}};factory.supportedStyles=['caption_1','caption_2'];window.storylensCaptionPatterns=factory;script.onload();}}}};
 vm.createContext(c);vm.runInContext(source.slice(a,b),c);return {c,get loads(){return loads},get created(){return created},get removed(){return removed}};
}
test('Generate upgrades a stale Caption 1-only module and restores Caption 2 controls',async()=>{const h=harness();await h.c.ensureNativeCaptionPattern();assert(h.c.captionPatternView.isSelected());assert.equal(h.loads,1);assert.equal(h.created,1);assert.equal(h.removed,1);await h.c.ensureNativeCaptionPattern();assert.equal(h.loads,1);});
test('Failed module loading stops with recovery advice instead of entering legacy analysis',async()=>{const h=harness(true);await assert.rejects(h.c.ensureNativeCaptionPattern(),/reopen|reload/i);assert.equal(h.created,0);});
test('Actual Generate dispatch recovers stale Caption 2 routing before any legacy capture',async()=>{
 const h=harness(),source=fs.readFileSync('hinglish_app/static/editor-panel.js','utf8');h.c.capture=()=>assert.fail('Readable narration must not enter legacy timeline flattening');
 vm.runInContext(source.slice(source.indexOf('async function run(){'),source.indexOf('\nfunction select(',source.indexOf('async function run(){'))),h.c);
 await h.c.run();assert.equal(h.c.generated,1);assert.equal(h.loads,1);
});
