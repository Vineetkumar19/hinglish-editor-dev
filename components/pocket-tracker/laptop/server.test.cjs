const test=require('node:test'),assert=require('node:assert/strict');
const {validate}=require('./server.cjs');
const p={host:'192.168.1.10',port:43821,fingerprint:'a'.repeat(64),token:'b'.repeat(44)};
test('only private phone endpoints allowed',()=>{assert.equal(validate(p).host,p.host);for(const host of ['8.8.8.8','127.0.0.1','169.254.169.254','192.168.999.1','example.com'])assert.throws(()=>validate({...p,host}));});
test('pairing requires certificate pin and long credential',()=>{assert.throws(()=>validate({...p,token:'1234'}));assert.throws(()=>validate({...p,fingerprint:''}));assert.throws(()=>validate({...p,port:80}));});
