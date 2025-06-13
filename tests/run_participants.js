const { JSDOM } = require('jsdom');
const fs = require('fs');

let data = '';
process.stdin.on('data', chunk => data += chunk);
process.stdin.on('end', () => {
  const dom = new JSDOM(data, { runScripts: 'dangerously', url: 'http://localhost' });
  const window = dom.window;
  const document = window.document;
  window.matchMedia = window.matchMedia || function(){ return {matches:false, addListener:function(){}, removeListener:function(){}}; };
  const script = fs.readFileSync('static/theme.js', 'utf8');
  window.eval(script);
  document.dispatchEvent(new window.Event('DOMContentLoaded'));
  const btn = document.querySelector('.remove-participant');
  if (btn) btn.click();
  const count = document.querySelectorAll('.participant-group').length;
  console.log(count.toString());
});
