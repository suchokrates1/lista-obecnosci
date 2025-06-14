function applyTheme(theme) {
  document.documentElement.setAttribute('data-bs-theme', theme);
}

function applyContrast(enabled) {
  if (enabled) {
    document.body.classList.add('high-contrast');
  } else {
    document.body.classList.remove('high-contrast');
  }
}

function toggleTheme() {
  const current = document.documentElement.getAttribute('data-bs-theme') === 'dark';
  const next = current ? 'light' : 'dark';
  applyTheme(next);
  localStorage.setItem('theme', next);
}

function toggleContrast() {
  const active = document.body.classList.toggle('high-contrast');
  localStorage.setItem('contrast', active ? '1' : '0');
}

function togglePassword(id, btn) {
  const input = document.getElementById(id);
  if (!input) return;
  const icon = btn && btn.querySelector('i');
  const show = input.type === 'password';
  input.type = show ? 'text' : 'password';
  if (icon) {
    icon.classList.toggle('bi-eye', !show);
    icon.classList.toggle('bi-eye-slash', show);
  }
}

function handleParticipantPaste(e) {
  const data = (e.clipboardData || window.clipboardData).getData('text');
  if (data && /[\r\n]/.test(data)) {
    e.preventDefault();
    const lines = data.replace(/\r/g, '').split('\n');
    const first = lines.shift();
    e.target.value = first;
    lines.forEach(function(line) { addParticipantField(line); });
  }
}

function saveRegForm(clear) {
  if (clear === null) {
    localStorage.removeItem('registerForm');
    return;
  }
  const form = document.querySelector('form');
  const container = document.getElementById('participants-container');
  if (!form || !container) return;
  const data = {};
  form.querySelectorAll('input').forEach(function(inp) {
    if (inp.name === 'uczestnik') {
      if (!data.uczestnik) data.uczestnik = [];
      data.uczestnik.push(inp.value);
    } else if (inp.type !== 'file') {
      if (inp.id) data[inp.id] = inp.value;
    }
  });
  localStorage.setItem('registerForm', JSON.stringify(data));
}

function loadRegForm() {
  const form = document.querySelector('form');
  const container = document.getElementById('participants-container');
  if (!form || !container) return;
  const saved = localStorage.getItem('registerForm');
  if (!saved) return;
  let data;
  try { data = JSON.parse(saved); } catch(e) { return; }
  if (data.imie !== undefined) {
    const el = document.getElementById('imie');
    if (el) el.value = data.imie;
  }
  if (data.nazwisko !== undefined) {
    const el = document.getElementById('nazwisko');
    if (el) el.value = data.nazwisko;
  }
  if (data.numer_umowy !== undefined) {
    const el = document.getElementById('numer_umowy');
    if (el) el.value = data.numer_umowy;
  }
  if (data.login !== undefined) {
    const el = document.getElementById('login');
    if (el) el.value = data.login;
  }
  if (data.haslo !== undefined) {
    const el = document.getElementById('haslo');
    if (el) el.value = data.haslo;
  }
  if (Array.isArray(data.uczestnik)) {
    const groups = container.querySelectorAll('.participant-group');
    if (groups.length) {
      const firstInput = groups[0].querySelector('.participant-input');
      if (firstInput) firstInput.value = data.uczestnik[0] || '';
      Array.from(groups).slice(1).forEach(function(g){ g.remove(); });
    }
    for (let i = 1; i < data.uczestnik.length; i++) {
      addParticipantField(data.uczestnik[i]);
    }
  }
}

function addParticipantField(value = '') {
  const container = document.getElementById('participants-container');
  if (!container) return;
  const group = document.createElement('div');
  group.className = 'participant-group mb-2';

  const input = document.createElement('input');
  input.type = 'text';
  input.name = 'uczestnik';
  input.required = true;
  input.placeholder = 'Imię i nazwisko';
  input.className = 'form-control participant-input';
  input.value = value;
  input.addEventListener('paste', handleParticipantPaste);

  const removeBtn = document.createElement('button');
  removeBtn.type = 'button';
  removeBtn.className = 'btn btn-outline-secondary btn-sm remove-participant ms-2';
  removeBtn.textContent = 'Usuń';
  removeBtn.addEventListener('click', function(){ removeParticipantField(removeBtn); });

  group.appendChild(input);
  group.appendChild(removeBtn);
  container.appendChild(group);
  saveRegForm();
  return input;
}

function removeParticipantField(btn) {
  const group = btn.closest('.participant-group');
  if (!group) return;
  const container = document.getElementById('participants-container');
  if (!container) return;
  const groups = container.querySelectorAll('.participant-group');
  if (groups.length <= 1) return;
  group.remove();
  saveRegForm();
}

(function() {
  let theme = localStorage.getItem('theme');
  if (!theme) {
    theme = window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
  }
  applyTheme(theme);

  const contrast = localStorage.getItem('contrast') === '1';
  applyContrast(contrast);

  document.addEventListener('DOMContentLoaded', function() {
    const darkBtn = document.getElementById('darkModeToggle');
    if (darkBtn) darkBtn.addEventListener('click', toggleTheme);
    const contrastBtn = document.getElementById('contrastToggle');
    if (contrastBtn) contrastBtn.addEventListener('click', toggleContrast);

    const sigInput = document.getElementById('podpis');
    const sigPreview = document.getElementById('podpisPreview');
    if (sigInput && sigPreview) {
      sigInput.addEventListener('change', function () {
        const file = this.files && this.files[0];
        if (file && file.type.startsWith('image/')) {
          const reader = new FileReader();
          reader.onload = function (e) {
            sigPreview.src = e.target.result;
            sigPreview.classList.remove('d-none');
          };
          reader.readAsDataURL(file);
        } else {
          sigPreview.classList.add('d-none');
          sigPreview.removeAttribute('src');
        }
      });
    }

    const addBtn = document.getElementById('addParticipant');
    if (addBtn) addBtn.addEventListener('click', function(){ addParticipantField(); });
    document.querySelectorAll('.participant-input').forEach(function(inp){
      inp.addEventListener('paste', handleParticipantPaste);
    });
    document.querySelectorAll('.remove-participant').forEach(function(btn){
      btn.addEventListener('click', function(){ removeParticipantField(btn); });
    });
    loadRegForm();

    const widthInputs = document.querySelectorAll('[data-column]');

    function updateTotals(tableKey) {
      const inputs = Array.from(document.querySelectorAll('[data-table="' + tableKey + '"]'));
      let total = inputs.reduce(function(s, o){ return s + parseFloat(o.value || 0); }, 0);
      const diff = 100 - total;
      const warn = document.querySelector('.total-warning[data-table="' + tableKey + '"]');
      if (warn) {
        if (diff !== 0) {
          warn.textContent = diff.toFixed(1);
          warn.classList.add('text-danger');
        } else {
          warn.textContent = '';
          warn.classList.remove('text-danger');
        }
      }
      return diff;
    }

    function applyWidth(inp) {
      const tableKey = inp.dataset.table;
      const colKey = inp.dataset.column;
      const tableId = tableKey.replace(/_/g, '-');
      const classPrefix = tableKey.replace('_', '-', 1);

      let val = parseFloat(inp.value);
      if (isNaN(val)) val = 0;
      if (val < 0) val = 0;
      if (val > 100) val = 100;
      inp.value = val;

      const table = document.getElementById(tableId);
      if (table) {
        table.style.width = '100%';
        const inputs = Array.from(document.querySelectorAll('[data-table="' + tableKey + '"]'));
        const index = inputs.indexOf(inp) + 1;
        let targets = [];
        const colById = document.getElementById(tableId + '-' + colKey);
        if (colById) targets.push(colById);
        targets = targets.concat(Array.from(table.querySelectorAll('col.col-' + classPrefix + '-' + colKey + ', th.col-' + classPrefix + '-' + colKey)));
        if (!targets.length && index > 0) {
          const col = table.querySelector('col:nth-child(' + index + ')');
          const th = table.querySelector('th:nth-child(' + index + ')');
          targets = [];
          if (col) targets.push(col);
          if (th) targets.push(th);
        }
        targets.forEach(function(el) { el.style.width = val + '%'; });
      }

      // ensure total per table <= 100
      const others = Array.from(document.querySelectorAll('[data-table="' + tableKey + '"]'));
      let total = others.reduce(function(s, o){ return s + parseFloat(o.value || 0); },0);
      if (total > 100) {
        const over = total - 100;
        let newVal = val - over;
        if (newVal < 0) newVal = 0;
        inp.value = newVal;
        if (table) {
          const index = others.indexOf(inp) + 1;
          let targets = [];
          const colById = document.getElementById(tableId + '-' + colKey);
          if (colById) targets.push(colById);
          targets = targets.concat(Array.from(table.querySelectorAll('col.col-' + classPrefix + '-' + colKey + ', th.col-' + classPrefix + '-' + colKey)));
          if (!targets.length && index > 0) {
            const col = table.querySelector('col:nth-child(' + index + ')');
            const th = table.querySelector('th:nth-child(' + index + ')');
            targets = [];
            if (col) targets.push(col);
            if (th) targets.push(th);
          }
          targets.forEach(function(el) { el.style.width = newVal + '%'; });
        }
      }

      updateTotals(tableKey);
    }

    function adjustLastColumn(tableKey) {
      const inputs = Array.from(document.querySelectorAll('[data-table="' + tableKey + '"]'));
      if (!inputs.length) return;
      const last = inputs[inputs.length - 1];
      const othersSum = inputs.slice(0, -1).reduce(function(s, o){ return s + parseFloat(o.value || 0); }, 0);
      let newVal = 100 - othersSum;
      if (newVal < 0) newVal = 0;
      if (newVal > 100) newVal = 100;
      last.value = newVal;
      applyWidth(last);
    }
    const tableKeys = new Set();
    widthInputs.forEach(function(inp){
      tableKeys.add(inp.dataset.table);
      inp.addEventListener('input', function(){
        const key = inp.dataset.table;
        const inputs = Array.from(document.querySelectorAll('[data-table="' + key + '"]'));
        if (inp === inputs[inputs.length - 1]) {
          adjustLastColumn(key);
        } else {
          applyWidth(inp);
        }
      });
      applyWidth(inp);
    });

    const form = document.querySelector('form');
    if (form) {
      form.addEventListener('submit', function(){
        tableKeys.forEach(function(key){
          adjustLastColumn(key);
        });
        saveRegForm(null);
      });
      form.addEventListener('input', function(){ saveRegForm(); });
    }

    const resetButtons = document.querySelectorAll('.reset-widths');
    resetButtons.forEach(function(btn) {
      btn.addEventListener('click', function() {
        const key = btn.getAttribute('data-table');
        const inputs = document.querySelectorAll('input[data-table="' + key + '"]');
        if (!inputs.length) return;
        const val = 100 / inputs.length;
        inputs.forEach(function(inp) {
          inp.value = val;
          applyWidth(inp);
        });
      });
    });
  });
})();
