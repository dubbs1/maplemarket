// The app's simple layout: ages come from the last sighting, Listings hides week-old ones until asked, Prices groups by item
const {JSDOM}=require('jsdom'),fs=require('fs');
const d=new JSDOM(fs.readFileSync(require('path').join(__dirname,'../../MapleReader/shopreader/market.html'),'utf8'),{runScripts:'dangerously',
 url:'https://x.test/',pretendToBeVisual:true,beforeParse(w){w.MAPLE={mode:'local'};w.fetch=()=>Promise.reject(new Error('offline'))}});
const w=d.window,A=w.App,$=s=>w.document.querySelector(s);let f=0;const ok=(n,c)=>{console.log(c?'PASS':'FAIL',n);if(!c)f++};
const p=n=>String(n).padStart(2,'0'),iso=t=>{const x=new Date(t);return '@'+x.getFullYear()+'-'+p(x.getMonth()+1)+'-'+p(x.getDate())+'T'+p(x.getHours())+':'+p(x.getMinutes())+':'+p(x.getSeconds())};
const H=36e5,now=Date.now();
A.importScan([`Long Sword | 5000 | Old Shop | 2 | 4 | c1 | ${iso(now-120*H)}`,`Long Sword | 5000 | Old Shop | 2 | 4 | c1 | ${iso(now-H)}`,
 `Rusty Axe | 100 | Gone Shop | 3 | 4 | c1 | ${iso(now-100*H)}`,`Fresh Hat | 900 | New Shop | 1 | 4 | c1 | ${iso(now-60e3)}`].join('\n'));
ok('S1 tabs: Home, Prices, Listings, Options (no Scan or EXP without the app)',[...w.document.querySelectorAll('nav button:not([hidden])')].map(b=>b.textContent).join()==='Home,Prices,Listings,Options');
const opened=$('[data-nav=home]').getAttribute('aria-current')==='page';$('[data-nav=browse]').click();
ok('S2 opens on Home; Prices has one row per item',opened&&w.document.querySelectorAll('#list [data-open]').length===3);
$('[data-nav=market]').click();const txt=$('#mb').textContent;
ok('S3 a listing seen again today is not "may be gone"',/Long Sword/.test(txt)&&!/may be gone/.test(txt)&&/seen 1 h ago/.test(txt));
ok('S4 a listing nobody has seen for 4 days is hidden, with a button to show it',!/Rusty Axe/.test(txt)&&/Show 1 older listing/.test(txt));
ok('S5 a new one says just listed',/Fresh Hat[\s\S]*just listed/.test(txt));
$('[data-lold]').click();
ok('S6 the button shows the older one, marked may be gone',/Rusty Axe[\s\S]*may be gone/.test($('#mb').textContent));
$('[data-ls=low]').click();ok('S7 Cheapest puts the cheapest first',/^\s*Rusty Axe/.test($('#mb .fr').textContent));
$('[data-nav=browse]').click();[...w.document.querySelectorAll('#list [data-open]')].find(x=>/Long Sword/.test(x.textContent)).click();
ok('S8 its details show beside the cards, with an alert at the current price',/Long Sword/.test($('#ipanel').textContent)&&$('#iam')&&$('#iam').value==='5000');
$('#iam').value='4500';$('#iago').click();
ok('S9 one click sets it, and the page says so where it can be seen',A.S.alerts.some(a=>a.term==='Long Sword'&&a.max===4500)&&/Alert on/.test($('#app').textContent)&&/Alert set/.test($('#live').textContent));
$('[data-ra]').click();ok('S10 and removes it',!A.S.alerts.length&&!!$('#iago'));
console.log(f?f+' FAILED':'ALL PASS');process.exitCode=f?1:0;w.close();
