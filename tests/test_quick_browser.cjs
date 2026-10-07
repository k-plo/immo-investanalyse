#!/usr/bin/env node
/* Optional visual/browser acceptance test. Uses Chromium + Playwright, temp data only.
 * PLAYWRIGHT_MODULE may point to an existing Playwright installation.
 */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const {spawn, spawnSync} = require('node:child_process');
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const root = path.resolve(__dirname,'..');
const fixture = path.join(root,'tests/fixtures/quick_analysis');
const tmp = fs.mkdtempSync(path.join(os.tmpdir(),'immo-browser-'));
const db = path.join(tmp,'test.db'), output = path.join(tmp,'pdfs');
const config = JSON.parse(fs.readFileSync(path.join(fixture,'config.json'),'utf8'));
config.local.mail_directory = path.join(fixture,'emails');
config.local.listing_directory = fixture;
config.local.rent_file = path.join(fixture,'rents.json');
const configPath = path.join(tmp,'config.json');
fs.writeFileSync(configPath,JSON.stringify(config));
const env = {...process.env,IMMO_DB_PATH:db,IMMO_QUICK_OUTPUT:output,IMMO_QUICK_CONFIG:configPath,IMMO_QUICK_HOME:path.join(tmp,'private')};
function python(args) {
  const result = spawnSync('python3',args,{cwd:root,env,encoding:'utf8'});
  assert.equal(result.status,0,result.stderr);
  return result.stdout;
}
python(['-c', `import sys,sqlite3;sys.path.insert(0,'tools');from db_manager import SCHEMA; c=sqlite3.connect(${JSON.stringify(db)});c.executescript(SCHEMA);c.execute("INSERT INTO objekte(name,public_id,status,state_json,kaufpreis,wohnflaeche) VALUES ('TEST regular','test-id','aktiv','{}',100000,50)");c.commit();c.close()`]);
python(['tools/quick_worker.py','--once']);
const port = Number(process.env.IMMO_TEST_PORT || 8878);
const server = spawn('python3',['tools/local_server.py',String(port)],{cwd:root,env,stdio:['ignore','pipe','pipe']});
let logs='';server.stdout.on('data',d=>logs+=d);server.stderr.on('data',d=>logs+=d);
const origin = `http://127.0.0.1:${port}`;
let browser;
(async () => {
  try {
    for(let i=0;i<100;i++) {
      try { if((await fetch(origin+'/api/health')).ok) break; } catch {}
      await new Promise(resolve=>setTimeout(resolve,50));
    }
    const before = await (await fetch(origin+'/api/quick-analyses')).json();
    assert.equal(before.items.length,7);
    assert(before.items.every(i=>i.pdf_status==='erstellt'));
    assert(before.items.every(i=>i.delivery_status==='lokal_getestet'));
    browser = await chromium.launch({headless:true,executablePath:process.env.IMMO_CHROMIUM || '/usr/bin/chromium',args:['--no-sandbox']});
    const page = await browser.newPage();
    const errors=[];page.on('pageerror',e=>errors.push(e.message));
    for(const width of [1440,768,390,320]) {
      await page.setViewportSize({width,height:1000});
      await page.goto(origin+'/portfolio.html');
      await page.waitForSelector('#qaGrid .qa-card');
      assert.equal(await page.locator('#grid .karte').count(),1);
      assert.equal(await page.locator('#qaGrid .qa-card').count(),7);
      assert.match(await page.locator('#qaConnections').textContent(),/Nicht verbunden/);
      assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true,`overflow at ${width}`);
      await page.locator('#qaGrid .qa-card').first().locator('details').first().evaluate(el=>el.open=true);
      assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true,`details overflow at ${width}`);
      await page.locator('#qaSettings > summary').click();
      await page.waitForFunction(()=>document.getElementById('qaInterval').value==='30');
      assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true,`settings overflow at ${width}`);
      await page.evaluate(()=>{document.documentElement.dataset.theme='light';localStorage.setItem('dashboard-theme','light');});
      await page.screenshot({path:path.join(tmp,`dashboard-${width}-light.png`),fullPage:true});
      await page.evaluate(()=>{document.documentElement.dataset.theme='dark';localStorage.setItem('dashboard-theme','dark');});
      await page.screenshot({path:path.join(tmp,`dashboard-${width}-dark.png`),fullPage:true});
    }
    await page.setViewportSize({width:1440,height:1000});
    await page.goto(origin+'/portfolio.html');await page.waitForSelector('#qaGrid .qa-card');
    await page.locator('.filter button').filter({hasText:'Besichtigung'}).click();
    assert.equal(await page.locator('#grid .karte:visible').count(),0);
    assert.equal(await page.locator('#qaGrid .qa-card:visible').count(),7);
    await page.locator('.filter button').filter({hasText:'Alle'}).click();
    assert.equal(await page.locator('#grid .karte:visible').count(),1);
    await page.locator('#qaRefresh').click();
    await page.waitForSelector('#qaGrid .qa-card');
    const download = page.waitForEvent('download');
    await page.locator('#qaGrid a').filter({hasText:'PDF herunterladen'}).first().click();
    assert((await download).suggestedFilename().endsWith('.pdf'));
    // Duplicate EML upload uses the API and cannot trigger processing by itself.
    await page.locator('#qaImport').setInputFiles(path.join(fixture,'emails/01-single.eml'));
    await page.waitForFunction(()=>document.getElementById('qaImportStatus').textContent.includes('0 Angebot'));
    const after = await (await fetch(origin+'/api/quick-analyses')).json();
    assert.deepEqual(after.jobs,before.jobs);
    // Source strings must stay inert in the DOM.
    await page.route('**/api/quick-analyses',async route=>{
      const data=structuredClone(after);
      data.items[0].result.fields.title.value='<img src=x onerror="window.sourceExecuted=true">';
      data.items[0].result.fields.other.evidence='<script>window.sourceExecuted=true</script>';
      await route.fulfill({json:data});
    });
    await page.locator('#qaRefresh').click();
    await page.waitForFunction(()=>document.querySelector('#qaGrid .karte-name').textContent.includes('<img'));
    assert.equal(await page.evaluate(()=>Boolean(window.sourceExecuted)),false);
    await page.unroute('**/api/quick-analyses');
    await page.goto(origin+'/portfolio.html');await page.waitForSelector('#qaGrid .qa-card');
    await page.locator('#qaSettings > summary').click();
    await page.waitForFunction(()=>document.getElementById('qaInterval').value==='30');
    assert.deepEqual((await (await fetch(origin+'/api/quick-analyses')).json()).jobs,before.jobs);
    // Configure with ordinary form values, including German number formats.
    await page.locator('#qaProfileName').fill('TEST browser menu');
    await page.locator('#qaEkValue').fill('30.000');
    await page.locator('#qaInterest').fill('4,60');
    await page.locator('#qaRepayment').fill('2');
    await page.locator('#qaMailDirectory').fill(path.join(tmp,'private','inbox'));
    await page.locator('#qaInterval').fill('1');
    await page.locator('#qaSaveSettings').click();
    await page.waitForFunction(()=>document.getElementById('qaSettingsStatus').textContent.includes('privat gespeichert'));
    const saved = JSON.parse(fs.readFileSync(configPath,'utf8'));
    assert.equal(saved.profile.ek,30000);assert.equal(saved.profile.zins,4.6);
    assert.equal(saved.local.notification,false);assert.equal(saved.local.auto_deliver_test,false);
    assert.deepEqual((await (await fetch(origin+'/api/quick-analyses')).json()).items,before.items);
    await page.locator('#qaStartWorker').click();
    await page.waitForFunction(()=>document.getElementById('qaWorkerState').textContent.startsWith('Worker läuft'));
    assert.equal(await page.locator('#qaSaveSettings').isDisabled(),true);
    await page.locator('#qaStopWorker').click();
    await page.waitForFunction(()=>document.getElementById('qaWorkerState').textContent.startsWith('Worker gestoppt'));
    assert.equal(await page.locator('#qaSaveSettings').isDisabled(),false);
    // Fresh synthetic EML + explicit single check uses the saved profile and creates its PDF.
    const freshEml=path.join(tmp,'TEST-menu.eml');
    fs.writeFileSync(freshEml,fs.readFileSync(path.join(fixture,'emails/01-single.eml'),'utf8').replace('single@example.invalid','TEST-menu@example.invalid'));
    await page.locator('#qaImport').setInputFiles(freshEml);
    await page.waitForFunction(()=>document.getElementById('qaImportStatus').textContent.includes('1 Angebot'));
    await page.locator('#qaCheckOnce').click();
    await page.waitForFunction(async()=>{
      const data=await (await fetch('/api/quick-analyses')).json();
      return data.items.length===8 && data.items.every(x=>x.pdf_status==='erstellt');
    });
    await page.waitForFunction(()=>document.getElementById('qaWorkerState').textContent.startsWith('Worker gestoppt'));
    await page.locator('#qaRefresh').click();
    await page.waitForFunction(()=>document.querySelectorAll('#qaGrid .qa-card').length===8);
    const menuResult=await (await fetch(origin+'/api/quick-analyses')).json();
    const newItem=menuResult.items.find(x=>!before.items.some(y=>y.id===x.id));
    assert(newItem);assert.equal(newItem.result.is_test,true);
    assert.equal(newItem.delivery_status,'nicht_verbunden');
    assert(Math.abs(newItem.result.calculation.basis.cashflowMonat-(-285))<1e-8);
    for(const oldItem of before.items)assert.deepEqual(menuResult.items.find(x=>x.id===oldItem.id),oldItem);
    assert.equal(await page.locator('#grid .karte').count(),1);
    const menuDownload=page.waitForEvent('download');
    await page.locator('#qaGrid a[href$="'+newItem.id+'"]').click();
    const pdfPath=path.join(tmp,'TEST-menu.pdf');await (await menuDownload).saveAs(pdfPath);
    assert(fs.readFileSync(pdfPath).subarray(0,4).equals(Buffer.from('%PDF')));
    await page.goto(origin+'/schnellanalyse.html');
    for(const [key,value] of Object.entries({kaufpreis:'300000',kaltmiete:'1500',zins:'4',tilgung:'2',ekAnteil:'10'})) await page.locator('#'+key).fill(value);
    await page.waitForFunction(()=>document.getElementById('results').textContent.includes('270.000'));
    assert.match(await page.locator('#results').textContent(),/−150|− 150|-150/);
    assert.deepEqual(errors,[]);
    console.log(JSON.stringify({ok:true,widths:[1440,768,390,320],items:8,regularItems:1,menuWorker:true,consoleErrors:errors,artifacts:tmp}));
  } finally {
    if(browser) await browser.close();
    try{await fetch(origin+'/api/quick-analyses/control',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({action:'stop-worker'})});}catch{}
    server.kill('SIGTERM');
  }
})().catch(error=>{console.error(error,logs);process.exitCode=1;});
