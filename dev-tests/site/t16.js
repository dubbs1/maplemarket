// Design C (the app's simple layout): Home, the trend strip, Listings by kind with For sale / Sold, the item panel beside the list
const {JSDOM}=require('jsdom'),fs=require('fs');
const d=new JSDOM(fs.readFileSync(require('path').join(__dirname,'../../MapleReader/shopreader/market.html'),'utf8'),{runScripts:'dangerously',
 url:'https://x.test/',pretendToBeVisual:true,beforeParse(w){w.MAPLE={mode:'shared'};w.fetch=()=>Promise.reject(new Error('offline'));w.scrollTo=()=>{}}});
const w=d.window,A=w.App,$=s=>w.document.querySelector(s),$$=s=>[...w.document.querySelectorAll(s)];let f=0;
const ok=(n,c)=>{console.log(c?'PASS':'FAIL',n);if(!c)f++};
const p=n=>String(n).padStart(2,'0'),iso=t=>{const x=new Date(t);return '@'+x.getFullYear()+'-'+p(x.getMonth()+1)+'-'+p(x.getDate())+'T'+p(x.getHours())+':'+p(x.getMinutes())+':'+p(x.getSeconds())};
const H=36e5,now=Date.now(),L=[];
for(const [i,sh] of ['Star One','Star Two','Star Three'].entries())L.push(`Ilbi Throwing-Stars | 2500000 | ${sh} | ${2+i} | 4 | c1 | ${iso(now-(5-i)*24*H)}`);
L.push(`Ilbi Throwing-Stars | 2000000 | Lucky Stars | 3 | 5 | c1 | ${iso(now-60e3)}`);
for(const [i,sh] of ['Pots A','Pots B','Pots C'].entries())L.push(`Power Elixir | 9000 | ${sh} | ${1+i} | 2 | c1 | ${iso(now-(3-i)*H)}`);
L.push(`Scroll for Gloves for ATT 60% | 1800000 | Scroll Corner | 6 | 8 | sold | c1 | ${iso(now-2*H)}`);
A.importScan(L.join('\n'));
w.document.querySelector('[data-nav=home]').click();
const home=$('#app').textContent;
ok('C1 Home: a big search, today\'s numbers, just listed and the alerts',!!$('[data-tosearch]')&&/Seen today/.test(home)&&/Just listed/.test(home)&&
 /Ilbi Throwing-Stars/.test($('#home .feed').textContent)&&/No alerts yet/.test(home));
const chip=$$('#trend .chip').find(c=>/Ilbi/.test(c.textContent));
ok('C2 the trend strip: Ilbi is 20% under its usual price',!!chip&&/▼ 20%/.test(chip.textContent)&&!$$('#trend .chip').some(c=>/Power Elixir/.test(c.textContent)));
chip.click();
ok('C3 a trend chip opens its prices, with the history chart',$('[data-nav=browse]').getAttribute('aria-current')==='page'&&/Ilbi/.test($('#ipanel').textContent)&&
 /Price history/.test($('#ipanel').textContent)&&!!$('#ipanel svg polyline'));
$('[data-nav=market]').click();
const rail=$$('#rail [data-lc]').map(b=>b.textContent);
ok('C4 Listings: kinds of item down the side, biggest first, with counts (3-day-old ones hidden)',rail.join()==='All4,Potions and food3,Stars and arrows1');
$$('#rail [data-lc]').find(b=>/Potions/.test(b.textContent)).click();
ok('C5 a kind shows only its listings',$$('#mb .fr').length===3&&$$('#mb .fr').every(r=>/Power Elixir/.test(r.textContent)));
$('#rail [data-lc=""]').click();$('[data-lst=sold]').click();
ok('C6 Sold shows sold listings, tagged',$$('#mb .fr').length===1&&/Scroll for Gloves[\s\S]*Sold/.test($('#mb .fr').textContent)&&/sold 2 h ago/.test($('#mb').textContent));
$('[data-lst=sale]').click();$('[data-ls=deal]').click();
ok('C7 Best deal puts the furthest under its usual price first',/^\s*Ilbi[\s\S]*For sale/.test($('#mb .fr').textContent)&&/2,000,000/.test($('#mb .fr').textContent));
ok('C8 before a click, the panel asks for one',/Click a listing/.test($('#lpanel').textContent));
$('#mb .fr [data-open]').click();
const pn=$('#lpanel').textContent;
ok('C9 clicking a listing shows its item beside the list',$('[data-nav=market]').getAttribute('aria-current')==='page'&&/Ilbi Throwing-Stars/.test(pn)&&
 /Cheapest now/.test(pn)&&/7-day median/.test(pn)&&/Where to buy/.test(pn)&&/A good price: 20% below/.test(pn)&&$('#mb .card.picked')!==null);
$('#lpanel [data-hd="30"]').click();
ok('C10 the history switches to 30 days',$('#lpanel [data-hd="30"]').getAttribute('aria-pressed')==='true'&&/30 days ago/.test($('#lpanel').textContent));
$('#iam').value='2100000';$('#iago').click();$('[data-nav=home]').click();
ok('C11 an alert set there shows on Home, with the price hit',/Ilbi Throwing-Stars[\s\S]*under 2,100,000[\s\S]*Price hit/.test($('#home').textContent));
ok('C12 no EXP tab without the app',$('[data-nav=exp]').hidden);
console.log(f?f+' FAILED':'ALL PASS');process.exitCode=f?1:0;w.close();
