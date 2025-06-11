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

    const widthInputs = document.querySelectorAll('[data-column]');
    function applyWidth(inp) {
      const table = inp.dataset.table;
      const col = inp.dataset.column;
      let val = parseFloat(inp.value);
      if (isNaN(val)) val = 0;
      if (val < 0) val = 0;
      if (val > 100) val = 100;
      inp.value = val;
      document.querySelectorAll('.col-' + table + '-' + col).forEach(function(el) {
        el.style.width = val + '%';
      });
      // ensure total per table <= 100
      const others = Array.from(document.querySelectorAll('[data-table="' + table + '"]'));
      let total = others.reduce(function(s, o){ return s + parseFloat(o.value || 0); },0);
      if (total > 100) {
        const over = total - 100;
        inp.value = val - over;
        document.querySelectorAll('.col-' + table + '-' + col).forEach(function(el){
          el.style.width = (val - over) + '%';
        });
      }
    }
    widthInputs.forEach(function(inp){
      inp.addEventListener('input', function(){ applyWidth(inp); });
      applyWidth(inp);
    });
  });
})();
