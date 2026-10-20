const {JSDOM}=require('jsdom'),fs=require('fs');
const d=new JSDOM(fs.readFileSync(require('path').join(__dirname,'../../MapleReader/shopreader/market.html'),'utf8'),{runScripts:'dangerously',url:'https://x.test/',pretendToBeVisual:true});
const A=d.window.App;let f=0;const ok=(n,c)=>{console.log(c?'PASS':'FAIL',n);if(!c)f++};
A.importScan('Bunny Ears | 62999 | Cheapest NX <3 | 3 | 2\nBunny Ears | 62999 | Cheapest NX <3 | 3 | 2');
const id=A.ITEMS.find(i=>i.name==='Bunny Ears').id;ok('D1 two identical copies kept',A.analyze(id).sale===2);
A.importScan('Bunny Ears | 62999 | Cheapest NX <3 | 3 | 2');ok('D2 one copy sold or pulled -> 1 for sale, 1 gone',A.analyze(id).sale===1&&A.analyze(id).gone===1);
A.importScan('Red Cape | 5000 | LESS ry | 4 | 4');const rc=A.ITEMS.find(i=>i.name==='Red Cape').id;A.importScan('Red Cape | 5000 | LESSIE | 4 | 4');
ok('D3 misread shop name does not create a fake gone',A.analyze(rc).gone===0&&A.analyze(rc).sale===1);
process.exit(f)
