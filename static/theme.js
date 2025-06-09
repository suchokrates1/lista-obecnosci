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
  });
})();
