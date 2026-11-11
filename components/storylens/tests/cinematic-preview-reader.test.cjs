const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),os=require('node:os'),zlib=require('node:zlib');
const signature=Buffer.from('89504e470d0a1a0a','hex');
function crc(bytes){let n=0xffffffff;for(const byte of bytes){n^=byte;for(let k=0;k<8;k++)n=n&1?(n>>>1)^0xedb88320:n>>>1;}return (n^0xffffffff)>>>0;}
function chunk(name,data){const type=Buffer.from(name),out=Buffer.alloc(data.length+12);out.writeUInt32BE(data.length);type.copy(out,4);data.copy(out,8);out.writeUInt32BE(crc(Buffer.concat([type,data])),data.length+8);return out;}
function png(){const header=Buffer.alloc(13);header.writeUInt32BE(1);header.writeUInt32BE(1,4);header[8]=8;header[9]=6;return Buffer.concat([signature,chunk('IHDR',header),chunk('IDAT',zlib.deflateSync(Buffer.from([0,255,255,255,255]))),chunk('IEND',Buffer.alloc(0))]);}
test('legacy CEP Buffer subarray returning Uint8Array still produces a readable preview',()=>{
 const dir=fs.mkdtempSync(path.join(os.tmpdir(),'sl-preview-reader-')),file=path.join(dir,'1.png'),original=fs.readFileSync;fs.writeFileSync(file,png());
 try{fs.readFileSync=function(p,...rest){const b=original.call(this,p,...rest);if(p===file)b.subarray=(start,end)=>new Uint8Array(b.buffer,b.byteOffset+start,end-start);return b;};const result=require('../editor_plugins/cinematic-text/bridge.cjs').image(file);assert(result.startsWith('data:image/png;base64,'));assert.deepEqual(Buffer.from(result.split(',')[1],'base64'),png());}
 finally{fs.readFileSync=original;fs.rmSync(dir,{recursive:true,force:true});}
});
test('signature-only, missing IEND, bad CRC and excessive dimensions are never accepted as ready previews',()=>{
 const {image}=require('../editor_plugins/cinematic-text/bridge.cjs'),dir=fs.mkdtempSync(path.join(os.tmpdir(),'sl-preview-invalid-')),file=path.join(dir,'1.png');try{
  const badCRC=png();badCRC[30]^=1;const largeHeader=Buffer.alloc(13);largeHeader.writeUInt32BE(100000);largeHeader.writeUInt32BE(1,4);largeHeader[8]=8;largeHeader[9]=6;
  for(const b of [signature,png().subarray(0,-12),badCRC,Buffer.concat([signature,chunk('IHDR',largeHeader),chunk('IDAT',Buffer.from([1])),chunk('IEND',Buffer.alloc(0))])]){fs.writeFileSync(file,b);assert.throws(()=>image(file),/preview/i);}
 }finally{fs.rmSync(dir,{recursive:true,force:true});}
});
module.exports={png};
test('runtime diagnostics distinguish container validity from encoding failures without returning pixels',()=>{
 const dir=fs.mkdtempSync(path.join(os.tmpdir(),'sl-preview-diagnostic-')),file=path.join(dir,'1.png');fs.writeFileSync(file,png());try{
  const reader=require('../editor_plugins/cinematic-text/png-preview.cjs');const report=reader.diagnose(file);assert.equal(report.valid,true);assert.equal(report.encoding_ok,true);assert(report.runtime.node);assert.deepEqual(report.signature,[137,80,78,71,13,10,26,10]);assert.equal(report.chunks[0].type,'IHDR');assert(!JSON.stringify(report).includes('data:image'));
 }finally{fs.rmSync(dir,{recursive:true,force:true});}
});
test('disposable test images do not overwrite the real CEP diagnostic file',()=>{
 const dir=fs.mkdtempSync(path.join(os.tmpdir(),'sl-preview-no-live-log-')),file=path.join(dir,'1.png'),log=path.resolve('cache/editor-panel/cinematic-preview-reader-diagnostic.json'),before=fs.existsSync(log)?fs.readFileSync(log):null;fs.writeFileSync(file,signature);try{assert.equal(require('../editor_plugins/cinematic-text/png-preview.cjs').read(file),null);const after=fs.existsSync(log)?fs.readFileSync(log):null;assert.deepEqual(after,before);}finally{fs.rmSync(dir,{recursive:true,force:true});}
});
test('CRC-valid corrupt compressed pixels, wrong row length and invalid filters are rejected',()=>{
 const {imagePNG}=require('./fixtures/png-preview.cjs'),reader=require('../editor_plugins/cinematic-text/png-preview.cjs');
 for(const options of [{compressed:Buffer.from([1,2,3,4])},{raw:Buffer.from([0,0])},{width:1,height:1,raw:Buffer.from([5,0,0,0,0])}])assert.equal(reader.valid(imagePNG(options)),false);
});
test('stored, fixed and dynamic deflate preserve Adam7, packed samples and 16-bit AE-compatible PNGs',()=>{
 const {imagePNG}=require('./fixtures/png-preview.cjs'),reader=require('../editor_plugins/cinematic-text/png-preview.cjs');
 for(const options of [{level:0},{strategy:zlib.constants.Z_FIXED},{level:9}])for(const interlace of [0,1])for(const [color,depth] of [[0,1],[0,16],[2,16],[3,1],[4,16],[6,8],[6,16]])assert.equal(reader.valid(imagePNG({color,depth,interlace,options})),true,JSON.stringify({options,color,depth,interlace}));
});
test('over-expanding streams are rejected before native inflate even if the runtime ignores its limit option',()=>{
 const {imagePNG}=require('./fixtures/png-preview.cjs'),reader=require('../editor_plugins/cinematic-text/png-preview.cjs'),original=zlib.inflateSync;let calls=0;const bomb=imagePNG({width:1,height:1,raw:Buffer.alloc(1024*1024)});
 try{zlib.inflateSync=function(...args){calls++;return original.apply(this,args);};assert.equal(reader.valid(bomb),false);assert.equal(calls,0);}finally{zlib.inflateSync=original;}
});
test('dynamic Huffman and split IDAT chunks validate; invalid Adler checksum is rejected',()=>{
 const {imagePNG}=require('./fixtures/png-preview.cjs'),reader=require('../editor_plugins/cinematic-text/png-preview.cjs'),width=128,height=128,raw=Buffer.alloc(height*(1+width*4));let random=12345;
 for(let i=0;i<raw.length;i++){random^=random<<13;random^=random>>>17;random^=random<<5;raw[i]=i%(1+width*4)===0?0:(i%3?random&255:0);}
 const compressed=zlib.deflateSync(raw,{strategy:zlib.constants.Z_HUFFMAN_ONLY});assert.equal((compressed[2]>>>1)&3,2,'Actually exercise a dynamic-Huffman block');const good=imagePNG({width,height,compressed});assert.equal(reader.valid(good),true);
 const split=Buffer.concat([good.subarray(0,33),chunk('IDAT',compressed.subarray(0,1)),chunk('IDAT',compressed.subarray(1)),chunk('IEND',Buffer.alloc(0))]);assert.equal(reader.valid(split),true);
 const checksum=Buffer.from(compressed);checksum[checksum.length-1]^=1;assert.equal(reader.valid(imagePNG({width,height,compressed:checksum})),false);
});
test('declared raw image size is capped before native decompression',()=>{
 const {imagePNG}=require('./fixtures/png-preview.cjs'),reader=require('../editor_plugins/cinematic-text/png-preview.cjs'),original=zlib.inflateSync;let calls=0;
 try{zlib.inflateSync=function(...args){calls++;return original.apply(this,args);};assert.equal(reader.valid(imagePNG({width:4096,height:4096,depth:16,raw:Buffer.from([0])})),false);assert.equal(calls,0);}finally{zlib.inflateSync=original;}
});
