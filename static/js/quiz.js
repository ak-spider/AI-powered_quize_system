(function(){
  const form = document.getElementById('quiz-form');
  if(!form) return;
  form.addEventListener('submit', e => {
    const btn = form.querySelector('button[type="submit"]');
    if(btn){ btn.disabled = true; btn.textContent = 'Submitting…'; }
  });
})();
