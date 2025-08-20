document.addEventListener('DOMContentLoaded', function(){
  // Sticky Buy Bar
  const buyForm = document.querySelector('#product-buy-form');
  const buyBtn  = document.querySelector('#buybar-add');
  const priceEl = document.querySelector('#pd-price');
  const barPrice= document.querySelector('#buybar-price');
  if(buyForm && buyBtn){
    buyBtn.addEventListener('click', ()=> buyForm.requestSubmit());
  }
  if(priceEl && barPrice){
    const p = priceEl.dataset.productPrice || priceEl.textContent;
    barPrice.textContent = (p.startsWith('₺') ? p : `₺ ${p}`).trim();
  }

  // Quick Add to Cart (product list)
  const qaButtons = document.querySelectorAll('.qa-add');
  const getCSRF = () => (document.cookie.match(/csrftoken=([^;]+)/)||[])[1];
  qaButtons.forEach(btn=>{
    btn.addEventListener('click', async (e)=>{
      e.preventDefault();
      const pid = btn.dataset.id;
      try{
        const res = await fetch(`/shop/cart/add/${pid}/`,{
          method:'POST',
          headers:{'X-CSRFToken': getCSRF() || '', 'X-Requested-With':'XMLHttpRequest'}
        });
        if(res.ok){ btn.textContent='Eklendi ✓'; setTimeout(()=>btn.textContent='Sepete Ekle',1200); }
        else{ window.location.href=`/shop/products/${pid}/`; }
      }catch{ window.location.href=`/shop/products/${pid}/`; }
    });
  });

  // Navbar scroll shadow toggle
  var nav = document.querySelector('.site-navbar');
  if(nav) {
    // Scroll ile gölge/kayma eklemeyi kapattık
    nav.classList.remove('scrolled');
  }

  // Lazy reveal using IntersectionObserver
  try{
    const io = new IntersectionObserver((entries)=>{
      entries.forEach(e=>{ if(e.isIntersecting){ e.target.classList.add('is-in'); io.unobserve(e.target); } });
    },{root:null, rootMargin:'0px', threshold:.12});
    document.querySelectorAll('.reveal').forEach(el=> io.observe(el));
  }catch{ /* noop */ }

  // Hero parallax effect
  const heroLayers = Array.from(document.querySelectorAll('.hero-home .media, .hero-premium .hero-img, .hero-home .video-bg'));
  if(heroLayers.length){
    let ticking=false;
    const onScroll=()=>{
      if(!ticking){
        window.requestAnimationFrame(()=>{
          const y = window.scrollY || 0;
          heroLayers.forEach(el=>{ el.style.transform = `translateY(${Math.min(40, y*0.12)}px) scale(1.02)`; });
          ticking=false;
        });
        ticking=true;
      }
    };
    window.addEventListener('scroll', onScroll, {passive:true});
    onScroll();
  }

  // Scroll indicator smooth scroll
  const si = document.querySelector('.scroll-indicator');
  if(si){
    si.addEventListener('click', function(e){
      const target = document.querySelector(this.getAttribute('href'));
      if(target){ e.preventDefault(); target.scrollIntoView({behavior:'smooth'}); }
    });
  }

  // Hero video play toggle
  const hero = document.getElementById('hero');
  const playBtn = document.querySelector('.btn-play');
  if(hero && playBtn){
    const src = hero.getAttribute('data-hero-video');
    const videoWrap = hero.querySelector('.video-bg');
    if(!src){
      // Video yoksa butonu gizle
      playBtn.style.display = 'none';
    }else{
      let videoEl = null;
      const ensureVideo = ()=>{
        if(!videoEl){
          videoEl = document.createElement('video');
          videoEl.src = src;
          videoEl.autoplay = false;
          videoEl.muted = true;
          videoEl.loop = true;
          videoEl.playsInline = true;
          videoWrap.appendChild(videoEl);
        }
        return videoEl;
      };
      playBtn.addEventListener('click', ()=>{
        const v = ensureVideo();
        const isPlaying = hero.classList.toggle('playing');
        playBtn.classList.toggle('is-playing', isPlaying);
        if(isPlaying){ v.play().catch(()=>{}); }
        else{ v.pause(); }
      });
    }
  }
});