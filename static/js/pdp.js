// Basit PDP galeri kontrolü
(function(){
  const main = document.getElementById('pdpMainImage');
  if(!main) return;
  
  document.querySelectorAll('.thumb-btn').forEach(btn=>{
    btn.addEventListener('click', ()=>{
      const src = btn.getAttribute('data-src');
      if(src){ main.src = src; }
    });
  });
})();