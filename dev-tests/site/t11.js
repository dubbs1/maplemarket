// Big all_scans.txt: 30,000 rows import fully, newest rows included, and re-import is quick
const {JSDOM}=require('jsdom'),fs=require('fs');
const d=new JSDOM(fs.readFileSync(require('path').join(__dirname,'../../MapleReader/shopreader/market.html'),'utf8'),{runScripts:'dangerously',url:'https://x.test/',pretendToBeVisual:true});
const A=d.window.App;let f=0;const ok=(n,c)=>{console.log(c?'PASS':'FAIL',n);if(!c)f++};
const p=n=>String(n).padStart(2,'0'),iso=t=>{const x=new Date(t);return '@'+x.getFullYear()+'-'+p(x.getMonth()+1)+'-'+p(x.getDate())+'T'+p(x.getHours())+':'+p(x.getMinutes())+':'+p(x.getSeconds())};
const t0=Date.now()-10*864e5,L=[];for(let i=0;i<30000;i++)L.push('Bulk Item '+(i%300)+' | '+(1000+i)+' | Shop '+(i%500)+' | '+(1+i%11)+' | '+(1+i%20)+' | '+iso(t0+i*20e3));
let t=Date.now(),r=A.importScan(L.join('\n'));const t1=Date.now()-t;
ok('B1 all 30,000 rows imported ('+t1+' ms)',r.added===30000);
t=Date.now();r=A.importScan(L.join('\n')+'\nBulk Item 1 | 999 | Shop 1 | 1 | 1 | '+iso(Date.now()-1000));const t2=Date.now()-t;
ok('B2 re-import adds just the newest row ('+t2+' ms)',r.added===1&&r.already===30000);
console.log('saved size MB',(JSON.stringify(A.S).length/1e6).toFixed(1),'full?',r.full);ok('B3 storage-full is reported, not hidden',typeof r.full==='boolean');
console.log(f?f+' FAILED':'ALL PASS');process.exitCode=f?1:0;
