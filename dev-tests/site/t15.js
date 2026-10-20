// Seeing shops again (app mode): a part-seen shop isn't marked gone, a sold and a for-sale copy seen together are two,
// the same listing seen 3 times isn't 3 copies, storage that's full makes room, and very old rows aren't stored
const {JSDOM}=require('jsdom'),fs=require('fs');
const html=fs.readFileSync(require('path').join(__dirname,'../../MapleReader/shopreader/market.html'),'utf8');
let f=0;const ok=(n,c)=>{console.log(c?'PASS':'FAIL',n);if(!c)f++};
const page=(extra)=>new JSDOM(html,{runScripts:'dangerously',url:'https://x.test/',pretendToBeVisual:true,
  beforeParse(w){w.MAPLE={mode:'shared'};w.fetch=()=>Promise.reject(new Error('offline'));if(extra)extra(w)}}).window;
const at=m=>new Date(Date.now()-m*60e3).toISOString().slice(0,19)+'Z';
const L=(name,p,m,ex='',shop='Part Shop')=>`${name} | ${p} | ${shop} | 3 | 5 |${ex} c1 | @${at(m)}`;
let w=page(),A=w.App;
A.importScan(['One','Two','Three'].map((n,i)=>L('Part '+n,100+i,300)).join('\n'));
A.importScan(L('Part One',100,10));
const st=p=>{const o=A.analyze().rows.find(o=>o.shop==='Part Shop'&&o.price===p);return o&&o.st};
ok('P1 a shop seen again only in part: the rest stay for sale',st(101)==='sale'&&st(102)==='sale');
A.importScan([L('Pair Hat',500,5,' sold |','Pair Shop'),L('Pair Hat',500,5,'','Pair Shop')].join('\n'));
const pr=A.analyze().rows.filter(o=>o.shop==='Pair Shop').map(o=>o.st).sort().join();
ok('P2 a sold and a for-sale copy seen together are two listings ('+pr+')',pr==='sale,sold');
A.importScan([L('Pair Cap',700,5,'','Pair Shop'),L('Pair Cap',700,5,' sold |','Pair Shop')].join('\n'));
const pc=A.analyze().rows.filter(o=>o.shop==='Pair Shop'&&o.price===700).map(o=>o.st).sort().join();
ok('P3 same, the other way round ('+pc+')',pc==='sale,sold');
A.importScan([1,2,3].map(m=>`Lone Ring | 900 | Ring Shop | 2 | 5 | @${at(m*8)}`).join('\n'));
ok('P4 one listing seen 3 times (old lines without c) is one copy',A.analyze().rows.filter(o=>o.shop==='Ring Shop').length===1);
const r=A.importScan(L('Ancient Axe',100,60*24*40,'','Old Shop'));
ok('P5 rows older than 30 days are not stored in the app',r.added===0&&!A.analyze().rows.some(o=>o.shop==='Old Shop'));
// a browser whose storage takes only so much: the oldest scans make room
let cap=0;
w=page(win=>{const real=win.Storage.prototype.setItem;
  win.Storage.prototype.setItem=function(k,v){if(cap&&String(v).length>cap)throw new Error('QuotaExceeded');return real.call(this,k,v)}});
A=w.App;
for(let d=20;d>=1;d--)A.importScan(Array.from({length:40},(_,i)=>`Fill Item ${i} | ${1000+i} | Fill Shop ${d} | 2 | 5 | c1 | @${at(d*60*12)}`).join('\n'));
cap=Math.floor(w.localStorage.getItem('mcm1').length*0.6);
const res=A.importScan(L('New Thing',5,1,'','New Shop'));
ok('P6 storage full: the oldest scans make room and the new rows are kept ('+JSON.stringify({full:res.full,added:res.added})+')',
  !res.full&&res.added===1&&A.analyze().rows.some(o=>o.shop==='New Shop')&&!A.analyze().rows.some(o=>o.shop==='Fill Shop 20'));
console.log(f?f+' FAILED':'ALL PASS');process.exit(f?1:0);
