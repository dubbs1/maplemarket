// Easier import: all_scans.txt re-imported, sessions, shop-level gone, copies, drag and drop
const {JSDOM,VirtualConsole}=require('jsdom'),fs=require('fs');
const errs=[],vc=new VirtualConsole();vc.on('jsdomError',e=>{if(!/scrollTo/.test(e.message))errs.push(e.message)});
const html=fs.readFileSync(require('path').join(__dirname,'../../MapleReader/shopreader/market.html'),'utf8');
const d=new JSDOM(html,{runScripts:'dangerously',url:'https://x.test/',virtualConsole:vc,pretendToBeVisual:true});
const w=d.window,$=s=>w.document.querySelector(s),A=w.App;let f=0;const ok=(n,c)=>{console.log(c?'PASS':'FAIL',n);if(!c)f++};
const p=n=>String(n).padStart(2,'0'),iso=t=>{const x=new Date(t);return '@'+x.getFullYear()+'-'+p(x.getMonth()+1)+'-'+p(x.getDate())+'T'+p(x.getHours())+':'+p(x.getMinutes())+':'+p(x.getSeconds())};
const H=36e5,t0=Date.now()-30*H;
const L=(it,pr,shop,dt,x='')=>it+' | '+pr+' | '+shop+' | 2 | 7'+(x?' | '+x:'')+' | '+iso(t0+dt);
const id=n=>A.ITEMS.find(i=>i.name===n).id,an=n=>A.analyze(id(n));
// session 1: two shops, identical copies
let all=[L('Qa Ring',100,'Alpha',0),L('Qa Ring',100,'Alpha',0),L('Qb Cape',200,'Alpha',0),L('Qc Hat',300,'Beta',60e3)].join('\n');
let r=A.importScan(all);ok('E1 first import adds all rows',r.added===4);
let n0=A.S.scans.length;
r=A.importScan(all);ok('E2 importing the same file again adds nothing',r.added===0&&r.already===4&&r.dup);
// session 1 continues (file grew): one copy of the ring sells
all+='\n'+L('Qa Ring',100,'Alpha',5*60e3,'sold');
r=A.importScan(all);ok('E3 grown file adds only the new row',r.added===1&&r.already===4);
ok('E4 rows a few minutes apart join the same session',A.S.scans.length===n0);
let a=an('Qa Ring');ok('E5 one copy sold, one still for sale',a.sold===1&&a.sale===1&&a.gone===0);
// session 2, a day later: only shop Alpha revisited; one ring left, cape gone
all+='\n'+[L('Qa Ring',100,'alpha',24*H),L('Qa Ring',100,'alpha',24*H,'sold')].join('\n');
r=A.importScan(all);ok('E6 a later session becomes a new scan',r.added===2&&A.S.scans.length===n0+1);
a=an('Qa Ring');ok('E7 revisit keeps 1 sold + 1 for sale (shop name case ignored)',a.sold===1&&a.sale===1&&a.gone===0);
ok('E8 cape missing from the revisited shop is gone',an('Qb Cape').gone===1);
ok('E9 hat in a shop not revisited stays for sale',an('Qc Hat').sale===1);
// older file imported later goes in time order
r=A.importScan(L('Qd Belt',50,'Gamma',-48*H));const ix=n=>A.S.scans.findIndex(s=>s.rows.some(x=>x.item===id(n)));ok('E10 older rows sorted into place',r.added===1&&ix('Qd Belt')<ix('Qa Ring'));
// drag and drop a file onto the page while on another tab
$('[data-nav=deals]').click();
const file=new w.File([all+'\n'+L('Qe Glove',70,'Delta',25*H)],'all_scans.txt',{type:'text/plain'});
const ev=new w.Event('drop',{bubbles:true,cancelable:true});ev.dataTransfer={files:[file],types:['Files']};
w.document.body.dispatchEvent(ev);
setTimeout(()=>{
  ok('E11 dropping a file imports only the new row',/Imported 1 new row\./.test($('#e5')?.textContent||'')&&/already here/.test($('#e5').textContent));
  ok('E12 drop switches to the Market tab',$('[data-nav=market]').getAttribute('aria-current')==='page');
  ok('E13 help text names all_scans.txt',/all_scans\.txt/.test($('#app').textContent));
  ok('E14 no page errors',errs.length===0);
  console.log(f?f+' FAILED':'ALL PASS');process.exitCode=f?1:0;
},300);
