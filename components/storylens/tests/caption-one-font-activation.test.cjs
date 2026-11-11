const {test}=require('node:test'),assert=require('node:assert/strict');
test('native insertion activates verified bundled fonts once per panel process with no shell',()=>{
 const fonts=require('../editor_plugins/caption-patterns/fonts.cjs');let calls=0;
 const options={platform:'win32',spawnSync:(exe,args,opts)=>{calls++;assert(exe.endsWith('python.exe'));assert(args[0].endsWith('activate_caption_one_fonts.py'));assert.equal(opts.shell,false);assert.equal(opts.windowsHide,true);return {status:0,stdout:'{}'};}};
 fonts.ensure(process.cwd(),options);fonts.ensure(process.cwd(),options);assert.equal(calls,1);
});
test('activation failure remains retryable with useful diagnostics',()=>{
 const fonts=require('../editor_plugins/caption-patterns/fonts.cjs'),root=require('path').join(process.cwd(),'retry-font-fixture');let calls=0;
 assert.throws(()=>fonts.ensure(root,{platform:'win32',spawnSync:()=>({status:1,stderr:'font unavailable'})}),/font unavailable/);
 fonts.ensure(root,{platform:'win32',spawnSync:()=>{calls++;return {status:0};}});assert.equal(calls,1);
});
test('Caption 2 separately activates its regular footer face even after Caption 1 activation',()=>{
 const fonts=require('../editor_plugins/caption-patterns/fonts.cjs'),root=require('path').join(process.cwd(),'caption-two-font-fixture'),calls=[];
 const options={platform:'win32',spawnSync:(exe,args)=>{calls.push(args);return {status:0};}};
 fonts.ensure(root,options);fonts.ensure(root,{...options,style:'caption_2'});fonts.ensure(root,{...options,style:'caption_2'});
 assert.equal(calls.length,2);assert(calls[1].includes('--caption-two'));
});
