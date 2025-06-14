const { JSDOM } = require('jsdom');
const fs = require('fs');

let data = '';
process.stdin.on('data', chunk => data += chunk);
process.stdin.on('end', () => {
  const html = data;
  const script = fs.readFileSync('static/theme.js', 'utf8');

  const dom1 = new JSDOM(html, { runScripts: 'dangerously', url: 'http://localhost' });
  const w1 = dom1.window;
  const d1 = w1.document;
  w1.matchMedia = w1.matchMedia || function(){ return {matches:false, addListener:function(){}, removeListener:function(){}}; };
  w1.eval(script);
  d1.dispatchEvent(new w1.Event('DOMContentLoaded'));
  d1.getElementById('imie').value = 'A';
  d1.getElementById('nazwisko').value = 'B';
  d1.getElementById('numer_umowy').value = '1';
  d1.getElementById('login').value = 'x@example.com';
  d1.getElementById('haslo').value = 'pass';
  const p1 = d1.querySelector('.participant-input');
  if (p1) p1.value = 'P1';
  w1.addParticipantField('P2');
  w1.saveRegForm();
  const stored = w1.localStorage.getItem('registerForm');

  const dom2 = new JSDOM(html, { runScripts: 'dangerously', url: 'http://localhost' });
  const w2 = dom2.window;
  const d2 = w2.document;
  w2.matchMedia = w2.matchMedia || function(){ return {matches:false, addListener:function(){}, removeListener:function(){}}; };
  w2.localStorage.setItem('registerForm', stored);
  w2.eval(script);
  d2.dispatchEvent(new w2.Event('DOMContentLoaded'));
  const values = {
    imie: d2.getElementById('imie').value,
    nazwisko: d2.getElementById('nazwisko').value,
    numer: d2.getElementById('numer_umowy').value,
    login: d2.getElementById('login').value,
    haslo: d2.getElementById('haslo').value,
    participants: Array.from(d2.querySelectorAll('.participant-input')).map(n => n.value)
  };
  console.log(JSON.stringify(values));
});
