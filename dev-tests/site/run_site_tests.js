// One runner for every site check. Usage: node run_site_tests.js
const {execFileSync}=require('child_process');let pass=0,fail=0;
for(const t of ['t4','t5','t6','t7','t8','t9','t10','t11','t12','t13','t14']){let out;try{out=execFileSync('node',[__dirname+'/'+t+'.js'],{encoding:'utf8'})}catch(e){out=e.stdout||String(e)}
 const p=(out.match(/^PASS/gm)||[]).length,f=(out.match(/^FAIL.*/gm)||[]);pass+=p;fail+=f.length;console.log(t.padEnd(4),p,'pass',f.length?'\n  '+f.join('\n  '):'')}
console.log(`\n${pass} passed, ${fail} failed`);process.exitCode=fail?1:0;
