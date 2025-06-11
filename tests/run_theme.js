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
  const idCol = document.getElementById('admin-trainers-id');
  const nameCol = document.getElementById('admin-trainers-name');
  const warn = document.querySelector('.total-warning[data-table="admin_trainers"]');
  const result = {
    idWidth: idCol ? idCol.style.width : null,
    nameWidth: nameCol ? nameCol.style.width : null,
    warn: warn ? warn.textContent : null
  };
  console.log(JSON.stringify(result));
});
