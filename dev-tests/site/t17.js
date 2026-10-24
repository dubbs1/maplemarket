// One item, one name: misread W's ("Ink-and-vVYash", "-¥Wash", "-WYash"…) are fixed before Prices and Listings show them,
// both in new scans and in items an older page already saved in the browser
const {JSDOM}=require('jsdom'),fs=require('fs');
const HTML=fs.readFileSync(require('path').join(__dirname,'../../MapleReader/shopreader/market.html'),'utf8');
const page=(html,store)=>new JSDOM(html,{runScripts:'dangerously',url:'https://x.test/',pretendToBeVisual:true,beforeParse(w){
 w.MAPLE={mode:'local'};w.fetch=()=>Promise.reject(new Error('offline'));w.scrollTo=()=>{};if(store)w.localStorage.setItem('mcm1',store)}});
let f=0;const ok=(n,c)=>{console.log(c?'PASS':'FAIL',n);if(!c)f++};
const p=n=>String(n).padStart(2,'0'),iso=t=>{const x=new Date(t);return '@'+x.getFullYear()+'-'+p(x.getMonth()+1)+'-'+p(x.getDate())+'T'+p(x.getHours())+':'+p(x.getMinutes())+':'+p(x.getSeconds())};
const names=['Ink-and-Wash Thought','Ink-and-Wash Painting','Ink-and-vVYash Painting','Ink-and-¥Wash Thought','Ink-and-¥Vash Thought',
 'Ink-and-WYash Painting','Ink-and-v¥Vash Thought','Vvyvern Scale','Wyvern Scale'];
const lines=names.map((n,i)=>`${n} | ${949999+i} | Shop ${i} | ${1+i} | 4 | c1 | ${iso(Date.now()-(i+1)*60e3)}`).join('\n');
const shown=w=>[...w.document.querySelectorAll('#list .pc .t')].map(x=>x.textContent).sort().join(' / ');
// a page from before the fix saves each misread as its own item…
const old=page(HTML.replace('function fixName(n) {','function fixName(n) {\n  return n;'));
old.window.App.importScan(lines);old.window.document.querySelector('[data-nav=browse]').click();
ok('P1 (before the fix: 9 names, 9 items)',old.window.document.querySelectorAll('#list .pc').length===9);
const store=old.window.localStorage.getItem('mcm1');old.window.close();
// …this page folds them together when it opens
const w=page(HTML,store).window;w.document.querySelector('[data-nav=browse]').click();
ok('P2 items saved before the fix are folded into one each: '+shown(w),shown(w)==='Ink-and-Wash Painting / Ink-and-Wash Thought / Wyvern Scale');
ok('P3 their listings follow them (4 Thought, 3 Painting, 2 Wyvern)',['Ink-and-Wash Thought',4,'Ink-and-Wash Painting',3,'Wyvern Scale',2].every((x,i,a)=>
 i%2||w.App.analyze(w.App.ITEMS.find(it=>it.name===x).id).rows.length===a[i+1]));
w.close();
// and a fresh page reading the same scans never makes the extra items
const w2=page(HTML).window;w2.App.importScan(lines);w2.document.querySelector('[data-nav=browse]').click();
ok('P4 new scans: the same 3 items',shown(w2)==='Ink-and-Wash Painting / Ink-and-Wash Thought / Wyvern Scale');
w2.document.querySelector('[data-nav=market]').click();
ok('P5 Listings shows the fixed names only',!/vVY|¥|WYash|Vvyvern/.test(w2.document.querySelector('#mb').textContent));
console.log(f?f+' FAILED':'ALL PASS');process.exitCode=f?1:0;w2.close();
