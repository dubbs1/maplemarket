// Renders every view of two versions of the site and checks the HTML is identical.
const {JSDOM,VirtualConsole}=require('jsdom'),fs=require('fs');
function run(file){const errs=[],vc=new VirtualConsole();vc.on('jsdomError',e=>errs.push(e.message));
 const realNow=Date.now;
 const d=new JSDOM(fs.readFileSync(file,'utf8'),{runScripts:'outside-only',url:'https://x.test/',virtualConsole:vc,pretendToBeVisual:true});
 const w=d.window;w.Date.now=()=>1760000000000;w.Math.random=()=>0.42;
 const html=fs.readFileSync(file,'utf8'),js=html.slice(html.indexOf('<script>')+8,html.lastIndexOf('</script>'));
 w.eval(js);const out=[],$=s=>w.document.querySelector(s);
 const A=w.App;A.importScan(fs.readFileSync(require('path').join(__dirname,'../fixtures/scan_2026-10-18_2027.txt'),'utf8'));
 for(const v of ['market','mine','browse','deals','sources']){$(`[data-nav=${v}]`).click();out.push(v+':'+$('#app').innerHTML)}
 $('[data-nav=browse]').click();const b=[...w.document.querySelectorAll('#list [data-open]')].slice(0,6);
 for(const x of b){x.click();out.push('item:'+$('#app').innerHTML);$('[data-nav=browse]').click()}
 return {out,errs}}
const a=run(process.argv[2]),b=run(process.argv[3]);let diff=0;
a.out.forEach((x,i)=>{if(x!==b.out[i]){diff++;const k=[...x].findIndex((c,j)=>c!==b.out[i][j]);console.log('DIFF view',i,x.slice(0,20),'\n A:',x.slice(k-80,k+80),'\n B:',b.out[i].slice(k-80,k+80))}});
console.log(a.errs[0]);console.log(a.out.length,'views compared,',diff,'differ; errors',a.errs.length,b.errs.length);
