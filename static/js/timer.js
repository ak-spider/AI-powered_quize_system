(function(){
  const el = document.getElementById('timer');
  if(!el) return;
  let remaining = parseInt(el.dataset.duration, 10) || 60;
  const form = document.getElementById('quiz-form');
  function tick(){
    el.textContent = remaining + 's';
    if(remaining <= 10) el.classList.add('warning');
    if(remaining <= 0){
      if(form) form.submit();
      return;
    }
    remaining--;
    setTimeout(tick, 1000);
  }
  tick();
})();
