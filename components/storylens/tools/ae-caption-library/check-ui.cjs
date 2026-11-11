const fs=require('fs'),path=require('path'),assert=require('assert/strict'),{chromium}=require('../../tools/rea-runtime/node_modules/playwright-core');
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe',args:['--disable-gpu','--disable-extensions','--disable-background-networking']});
 globalThis.checkBrowser=browser;const page=await browser.newPage({acceptDownloads:true,viewport:{width:1200,height:900}}),errors=[];page.on('pageerror',e=>errors.push(String(e)));
 await page.goto('http://127.0.0.1:8765/?tool=captions',{waitUntil:'domcontentloaded'});await page.waitForSelector('#autoCaptionPanel .c3-families');await page.locator('#assistantClose').evaluate(e=>e.click());if(await page.locator('#chatHistoryClose').count())await page.locator('#chatHistoryClose').evaluate(e=>e.click());
 const host=page.locator('#autoCaptionPanel');assert(await host.locator('.c3-sound input').isChecked());
 for(const family of ['3d1','3d2','3d3']){
  await host.locator('[data-family="'+family+'"]').click();assert.equal(await host.locator('.c3-card').count(),4);
  for(const width of [360,640,1200]){await page.setViewportSize({width,height:900});await page.locator('#assistantClose').evaluate(e=>e.click());if(await page.locator('#chatHistoryClose').count())await page.locator('#chatHistoryClose').evaluate(e=>e.click());await host.locator('.caption-3d').screenshot({path:path.join('output/ae-3d-caption-library',family+'-'+width+'.png')});assert(await host.evaluate(e=>e.scrollWidth<=e.clientWidth+1));}
 }
 await host.locator('[data-family="3d2"]').click();await host.locator('[data-variant=black]').click();
 await host.locator('textarea[aria-label="Title text"]').fill('This is my story');
 const downloadPromise=page.waitForEvent('download');await host.locator('.c3-add').click();const download=await downloadPromise;const exportPath='output/ae-3d-caption-library/download-3d2.jsx';await download.saveAs(exportPath);const source=fs.readFileSync(exportPath,'utf8');assert(source.includes('This'));assert(source.includes('story'));assert(source.includes('StorylensCaptionSounds'));assert(source.includes('base64'));assert(source.includes('sound_fx'));
 await host.locator('[data-family="3d3"]').click();await host.locator('[data-family=standard]').click();assert(await page.locator('#ac-form').isVisible());
 await host.locator('[data-family="3d2"]').click();await host.locator('textarea[aria-label="Title text"]').fill('too many words');await host.locator('.c3-add').click();assert((await host.locator('.c3-status').textContent()).length>0);
 // Real editor panel delivery, with a bounded host fixture only; no AE control.
 await page.setViewportSize({width:760,height:950});await page.goto('http://127.0.0.1:8765/editor-panel.html?host=aftereffects',{waitUntil:'domcontentloaded'});await page.waitForSelector('#tools [data-mode=captions]');await page.locator('#tools [data-mode=captions]').click();
 await page.locator('#captionSettings [data-family="3d2"]').click();assert(await page.locator('#run').isHidden());assert(await page.locator('#captionStyle').isHidden());
 await page.locator('#tools [data-mode=clean]').click();assert(await page.locator('#run').isVisible());await page.locator('#tools [data-mode=captions]').click();assert(await page.locator('#run').isHidden());
 await page.locator('#captionSettings').screenshot({path:'output/ae-3d-caption-library/editor-panel.png'});
 await page.locator('#captionSettings [data-family=standard]').click();assert(await page.locator('#run').isVisible());assert(await page.locator('#captionStyle').isVisible());
 assert.deepEqual(errors,[]);fs.writeFileSync('output/ae-3d-caption-library/browser-check.json',JSON.stringify({real_service:8765,families:3,variants:12,widths:[360,640,1200],jsx_download:true,normal_caption_restore:true,ae_rendered:false,errors},null,2));await browser.close();console.log('Live web gallery, download and panel switching checked. Native AE not used.');
})().catch(async e=>{console.error(e);await globalThis.checkBrowser?.close();process.exitCode=1;});
