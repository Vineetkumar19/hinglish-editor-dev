const test=require('node:test'),assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs');
test('Downloader remains available to its Adobe browser iframe when module exists',()=>{
 const context={window:{},module:{exports:{}},URL};vm.createContext(context);
 vm.runInContext(fs.readFileSync('hinglish_app/static/downloader-model.js','utf8'),context);
 assert.equal(typeof context.window.storylensDownloader.platform,'function');
 assert.equal(context.window.storylensDownloader.platform('https://youtu.be/abc123'),'youtube');
 assert.equal(context.module.exports.platform,context.window.storylensDownloader.platform);
});
