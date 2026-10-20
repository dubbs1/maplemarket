const {JSDOM,VirtualConsole}=require('jsdom'),fs=require('fs');
const errs=[],vc=new VirtualConsole();vc.on('jsdomError',e=>errs.push(e.message));
const d=new JSDOM(fs.readFileSync(require('path').join(__dirname,'../../MapleReader/shopreader/market.html'),'utf8'),{runScripts:'dangerously',url:'https://x.test/',virtualConsole:vc,pretendToBeVisual:true});
const w=d.window,$=s=>w.document.querySelector(s),A=w.App;let f=0;const ok=(n,c)=>{console.log(c?'PASS':'FAIL',n);if(!c)f++};
const n=()=>w.document.querySelectorAll('#mb [data-open]').length;
const before=n();
$('#sc').value=fs.readFileSync(require('path').join(__dirname,'../fixtures/scan_2026-10-18_2027.txt'),'utf8');$('#scgo').click();
const forSale=A.analyze().rows.filter(o=>o.st==='sale').length;
ok('M1 import message', /Imported 133/.test($('#e5').textContent));
ok('M2 Market list now shows scanned listings ('+before+' -> '+n()+')', n()>=before+100);
const ms=$('#ms');ms.value='squishy';ms.dispatchEvent(new w.Event('input'));
ok('M3 search finds scanned Squishy Shoes', n()>=5 && /ch 11/.test($('#mb').textContent) && /scanned/.test($('#mb').textContent));
ok('M4 sold rows not listed as for sale', ![...w.document.querySelectorAll('#mb .card')].some(c=>/Dark Guise/.test(c.textContent)));
ms.value='';ms.dispatchEvent(new w.Event('input'));
const fs_=$('#fs');fs_.value='low';fs_.dispatchEvent(new w.Event('change'));
const p=[...w.document.querySelectorAll('#mb .num')].map(x=>+x.textContent.replace(/,/g,''));ok('M5 sort by price works with scans',p.every((x,i)=>i==0||p[i-1]<=x));
ok('M6 no Copy whisper buttons',!w.document.querySelector('[data-wh]')&&!/Copy whisper/.test(w.document.body.textContent));
ok('no runtime errors',errs.filter(e=>!/scrollTo/.test(e)).length===0);console.log(errs.filter(e=>!/scrollTo/.test(e)));process.exit(f)
