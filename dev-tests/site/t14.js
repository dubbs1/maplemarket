// A shop seen whole again: listings the reader marks "gone" stop showing for sale; sold ones stay sold; one that comes back is for sale again
const {JSDOM}=require('jsdom'),fs=require('fs');
const d=new JSDOM(fs.readFileSync(require('path').join(__dirname,'../../MapleReader/shopreader/market.html'),'utf8'),{runScripts:'dangerously',url:'https://x.test/',pretendToBeVisual:true});
const w=d.window,A=w.App;let f=0;const ok=(n,c)=>{console.log(c?'PASS':'FAIL',n);if(!c)f++};
const at=m=>new Date(Date.now()-m*60e3).toISOString().slice(0,19)+'Z',L=(name,p,m,ex='')=>`${name} | ${p} | Gone Test Shop | 3 | 5 |${ex} c1 | @${at(m)}`;
A.importScan([L('Gone Test Stars',100,10),L('Gone Test Lutia',200,10),L('Gone Test Ore',300,10)].join('\n'));
A.importScan([L('Gone Test Stars',100,4,' sold |'),L('Gone Test Lutia',150,4),L('Gone Test Lutia',200,4,' gone |'),L('Gone Test Ore',300,4,' gone |')].join('\n'));
const mine=()=>A.analyze().rows.filter(o=>o.shop==='Gone Test Shop'),st=(n,p)=>{const o=mine().find(o=>o.price===p);return o&&o.st};
ok('G1 a listing seen sold is sold',st('Gone Test Stars',100)==='sold');
ok('G2 the old price of a re-priced listing is gone, the new one for sale',st('Gone Test Lutia',200)==='gone'&&st('Gone Test Lutia',150)==='sale');
ok('G3 a listing no longer in the shop is gone',st('Gone Test Ore',300)==='gone');
ok('G4 a gone line never makes a listing of its own',mine().length===4);
A.importScan(L('Gone Test Ore',300,1));
ok('G5 seen for sale again: for sale again',st('Gone Test Ore',300)==='sale');
console.log(f?f+' FAILED':'ALL PASS');process.exitCode=f?1:0;
