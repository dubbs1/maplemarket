// Rooms above 11, times with a time zone, and names that try to sneak HTML in (shared mode: anyone with a key)
const {JSDOM}=require('jsdom'),fs=require('fs');
const d=new JSDOM(fs.readFileSync(require('path').join(__dirname,'../../MapleReader/shopreader/market.html'),'utf8'),{runScripts:'dangerously',url:'https://x.test/',pretendToBeVisual:true});
const w=d.window,A=w.App,$=s=>w.document.querySelector(s);let f=0;const ok=(n,c)=>{console.log(c?'PASS':'FAIL',n);if(!c)f++};
const utc=new Date(Date.now()-120e3).toISOString().slice(0,19);   // two minutes ago, written in UTC
const r=A.importScan(`Room Twelve Blade | 900 | Far Shop | 12 | 3 | c1 | @${utc}Z\nRoom Forty Blade | 950 | Far Shop | 40 | 3 | c1 | @${utc}+00:00\n`+
 `Room Fortyone Blade | 950 | Far Shop | 41 | 3 | c1 | @${utc}Z\n<img src=x onerror=alert(1)> Sword | 5000 | <b id=pwn>Evil</b> "' | 1 | 3 | c1 | @${utc}Z`);
ok('R1 rooms 12 to 40 are kept, 41 is not ('+JSON.stringify(r)+')',r.added===3&&r.skipped===1);
const rows=A.S.scans.flatMap(s=>s.rows),t=rows.find(x=>x.room===12).t;
ok('R2 a time with a time zone is read as that moment',Math.abs(t-(Date.now()-120e3))<2000);
let bad=0;for(const v of ['market','mine','browse','deals','sources']){$(`[data-nav=${v}]`).click();bad+=w.document.querySelectorAll('img[onerror],#pwn').length}
$('[data-nav=browse]').click();for(const x of [...w.document.querySelectorAll('#list [data-open]')]){x.click();bad+=w.document.querySelectorAll('img[onerror],#pwn').length;$('[data-nav=browse]').click()}
ok('R3 item and shop names never become HTML',bad===0);
const it=[...w.document.querySelectorAll('#list [data-open]')].find(x=>/Room Twelve/.test(x.textContent));if(it)it.click();
ok('R4 the room picker offers a scanned room above 11',!!$('#lr option[value="12"]'));
console.log(f?f+' FAILED':'ALL PASS');process.exitCode=f?1:0;
