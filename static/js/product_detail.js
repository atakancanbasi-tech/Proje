document.addEventListener('DOMContentLoaded', () => {
  const main = document.querySelector('[data-main-image]');
  if (!main) return;
  const buttons = document.querySelectorAll('[data-thumb-btn]');
  buttons.forEach(btn => {
    btn.addEventListener('click', () => {
      const url = btn.getAttribute('data-src');
      const alt = btn.getAttribute('data-alt') || '';
      main.src = url;
      main.alt = alt;
      buttons.forEach(b => b.classList.remove('is-active'));
      btn.classList.add('is-active');
    });
    btn.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        btn.click();
      }
    });
  });
});