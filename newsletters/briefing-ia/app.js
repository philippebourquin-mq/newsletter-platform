// ─── BRIEFING IA — app.js ────────────────────────────────────────────────────
// Logique partagée — commune à toutes les newsletters de la plateforme.
// SOURCES_DEFAULT est défini dans le fichier data.js de chaque newsletter (chargé en premier).

// ─── FEEDBACK ICONS ──────────────────────────────────────────────────────────
const ICON_UP=`<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 9V5a3 3 0 0 0-3-3l-4 9v11h11.28a2 2 0 0 0 2-1.7l1.38-9a2 2 0 0 0-2-2.3H14z"/><path d="M7 22H4a2 2 0 0 1-2-2v-7a2 2 0 0 1 2-2h3"/></svg>`;
const ICON_DOWN=`<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M10 15v4a3 3 0 0 0 3 3l4-9V2H5.72a2 2 0 0 0-2 1.7l-1.38 9a2 2 0 0 0 2 2.3H10z"/><path d="M17 2h2.67A2.31 2.31 0 0 1 22 4v7a2.31 2.31 0 0 1-2.33 2H17"/></svg>`;

// ─── ARCHIVE FULL ARTICLE HELPERS ────────────────────────────────────────────
function getFullArticle(id){
  const datePart=id.slice(0,10);
  if(datePart===TODAY.date){
    const art=TODAY.news.find(n=>n.id===id);
    if(art)return {...art};
  }
  const nl=ARCHIVE_FULL[datePart];
  if(nl){const art=nl.articles.find(a=>a.id===id);if(art)return {...art};}
  return null;
}

function renderArchiveCard(art,dateLongue,fichier,searchQ){
  const fb=getFeedback(art.id);
  const titleHtml=searchQ?highlight(art.titre,searchQ):art.titre;
  const src=(art.sources||[]).map(s=>`<a href="${s.url}" target="_blank">${s.nom}</a>`).join('');
  const esc=s=>s.replace(/'/g,"&#39;").replace(/"/g,'&quot;');
  return `<div class="news-item ${catClass(art.categorie)}" data-cat="${art.categorie}">
    <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:10px;">
      <div class="news-meta"><span class="cat-badge">${art.num}</span><span class="cat-label">${art.label}</span></div>
      <span style="font-family:'Inter',sans-serif;font-size:11px;color:var(--sand-300);">${dateLongue}</span>
    </div>
    <h2 class="news-title" style="cursor:pointer;" onclick="openNewsletter('${fichier}','${dateLongue}')">${titleHtml}</h2>
    <p class="news-body">${art.body}</p>
    <div class="news-sources"><span class="news-confiance-badge">${art.confiance||''}</span>${src}</div>
    <div class="news-actions">
      <button class="btn-action btn-thumb${fb==='up'?' active-up':''}" data-id="${art.id}" data-type="up" onclick="saveFeedback('${art.id}','up')">${fb==='up'?ICON_UP+' Pertinent':ICON_UP}</button>
      <button class="btn-action btn-thumb${fb==='down'?' active-down':''}" data-id="${art.id}" data-type="down" onclick="saveFeedback('${art.id}','down')">${fb==='down'?ICON_DOWN+' Moins utile':ICON_DOWN}</button>
      <button class="btn-action" onclick="shareArchiveNews('${esc(art.titre)}','${dateLongue}')">✉️ Partager</button>
    </div>
  </div>`;
}

let sourcesState=null;
function getSourcesState(){
  if(sourcesState)return sourcesState;
  try{const s=localStorage.getItem('sources_state');if(s){sourcesState=JSON.parse(s);return sourcesState;}}catch(e){}
  sourcesState=JSON.parse(JSON.stringify(SOURCES_DEFAULT));
  return sourcesState;
}
function saveSourcesState(){localStorage.setItem('sources_state',JSON.stringify(sourcesState));}

// ─── GITHUB CONFIG ────────────────────────────────────────────────────────────
const _GH_DEFAULTS={token:'',owner:'philbourquin',repo:'newsletter-platform',branch:'main'};
function getGithubConfig(){
  try{const s=localStorage.getItem('github_config');return s?{..._GH_DEFAULTS,...JSON.parse(s)}:{..._GH_DEFAULTS};}
  catch(e){return{..._GH_DEFAULTS};}
}
function saveGithubConfig(cfg){localStorage.setItem('github_config',JSON.stringify(cfg));}

// ─── GITHUB API ───────────────────────────────────────────────────────────────
async function githubPushFile(path,contentObj,message){
  const cfg=getGithubConfig();
  if(!cfg.token)return{ok:false,error:'Token non configuré — ajoute-le dans Paramètres → GitHub'};
  const headers={
    'Authorization':`Bearer ${cfg.token}`,
    'Accept':'application/vnd.github.v3+json',
    'Content-Type':'application/json',
    'X-GitHub-Api-Version':'2022-11-28'
  };
  const apiUrl=`https://api.github.com/repos/${cfg.owner}/${cfg.repo}/contents/${path}`;
  // Récupérer le SHA actuel (requis pour mise à jour)
  let sha=null;
  try{
    const r=await fetch(`${apiUrl}?ref=${cfg.branch}`,{headers});
    if(r.ok){const d=await r.json();sha=d.sha;}
  }catch(e){}
  // Encoder le contenu en base64 UTF-8
  const contentB64=btoa(unescape(encodeURIComponent(JSON.stringify(contentObj,null,2))));
  const body={message,content:contentB64,branch:cfg.branch};
  if(sha)body.sha=sha;
  try{
    const r=await fetch(apiUrl,{method:'PUT',headers,body:JSON.stringify(body)});
    if(!r.ok){const err=await r.json().catch(()=>({}));return{ok:false,error:err.message||`HTTP ${r.status}`};}
    return{ok:true};
  }catch(e){return{ok:false,error:e.message};}
}

function showGithubToast(filename,result){
  if(result.ok){
    const t=document.getElementById('toast');
    t.classList.add('toast-wide');
    t.innerHTML=
      `<div class="toast-check">✓</div>`+
      `<div class="toast-body">`+
        `<div class="toast-body-title">${filename} publié sur GitHub</div>`+
        `<div class="toast-body-sub">Pris en compte à la prochaine génération (07h10).</div>`+
      `</div>`;
    _triggerToast(t,5000);
  }else{
    showToast(`Erreur GitHub : ${result.error||'inconnue'}`);
  }
}

function saveGithubSettings(){
  const cfg={
    token:(document.getElementById('gh_token')?.value||'').trim(),
    owner:(document.getElementById('gh_owner')?.value||'philbourquin').trim(),
    repo:(document.getElementById('gh_repo')?.value||'newsletter-platform').trim(),
    branch:(document.getElementById('gh_branch')?.value||'main').trim()
  };
  saveGithubConfig(cfg);
  const s=document.getElementById('gh_status');
  if(s)s.textContent=cfg.token?'✓ Token enregistré':'Token non configuré';
  showToast('✓ Config GitHub enregistrée');
}

// ─── NAV ─────────────────────────────────────────────────────────────────────
function showTab(tab, btn) {
  document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.nav-tab').forEach(b => b.classList.remove('active'));
  document.getElementById('tab-'+tab).classList.add('active');
  btn.classList.add('active');
  if (tab==='today' && !document.getElementById('tab-today').innerHTML) renderToday();
  if (tab==='archive' && !document.getElementById('tab-archive').innerHTML) renderArchive();
  if (tab==='sources') renderSources();
  if (tab==='settings' && !document.getElementById('tab-settings').innerHTML) renderSettings();
}

// ─── FEEDBACK ────────────────────────────────────────────────────────────────
function getFeedback(id){return localStorage.getItem('fb_'+id)||null;}
function saveFeedback(id,type){
  const c=getFeedback(id);
  if(c===type){localStorage.removeItem('fb_'+id);updateButtons(id,null);}
  else{localStorage.setItem('fb_'+id,type);updateButtons(id,type);}
  // Mise à jour du compteur + bouton export dans le header
  const fbCount=TODAY.news.filter(n=>getFeedback(n.id)).length;
  const iconBubble=`<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>`;
  const countEl=document.getElementById('today-fb-count');
  if(countEl)countEl.innerHTML=iconBubble+' '+(fbCount>0?fbCount+'/'+TODAY.news.length+' évalué'+(fbCount>1?'s':''):'Aucun feedback');
  const exportBtn=document.getElementById('btn-export-fb');
  if(exportBtn)exportBtn.style.opacity=fbCount>0?'1':'0.4';
}
function updateButtons(id,type){
  const up=document.querySelector(`[data-id="${id}"][data-type="up"]`);
  const dn=document.querySelector(`[data-id="${id}"][data-type="down"]`);
  if(!up)return;
  up.className='btn-action btn-thumb'+(type==='up'?' active-up':'');
  dn.className='btn-action btn-thumb'+(type==='down'?' active-down':'');
  up.innerHTML=type==='up'?ICON_UP+' Pertinent':ICON_UP;
  dn.innerHTML=type==='down'?ICON_DOWN+' Moins utile':ICON_DOWN;
}

// ─── SHARE ────────────────────────────────────────────────────────────────────
function shareNews(id){
  const n=TODAY.news.find(x=>x.id===id);if(!n)return;
  const s=n.sources[0];
  window.location.href=`mailto:?subject=${encodeURIComponent('À lire : '+n.titre)}&body=${encodeURIComponent(n.body+'\n\nSource : '+s.url+'\n\nBriefing IA du '+TODAY.date_longue)}`;
}
function shareArchiveNews(titre,dateLongue){
  window.location.href=`mailto:?subject=${encodeURIComponent('À lire : '+titre)}&body=${encodeURIComponent('Lu dans le Briefing IA du '+dateLongue+'\n\n'+titre)}`;
}

// ─── CAT CLASS ───────────────────────────────────────────────────────────────
function catClass(c){const m={societal:'cat-societal',economie:'cat-economie',fonctionnel:'cat-fonctionnel',use_cases:'cat-use_cases',fun_facts:'cat-fun_facts',focus_retail:'cat-focus_retail'};return m[c]||'cat-default';}

// ─── READING TIME ─────────────────────────────────────────────────────────────
function calcReadTime(){
  const words=TODAY.news.reduce((s,n)=>s+n.body.split(' ').length,0)+(TODAY.radar||[]).reduce((s,r)=>s+(r.desc||'').split(' ').length,0);
  return Math.max(3,Math.round(words/180));
}

// ─── CATEGORY FILTER ─────────────────────────────────────────────────────────
let activeFilter='all';
function setFilter(cat,btn){
  activeFilter=cat;
  document.querySelectorAll('.cat-chip').forEach(c=>c.classList.remove('active-all','active-cat'));
  btn.classList.add(cat==='all'?'active-all':'active-cat');
  document.querySelectorAll('.news-item[data-cat]').forEach(el=>{
    const match=cat==='all'||el.dataset.cat===cat;
    el.classList.toggle('news-filtered',!match);
  });
  document.querySelectorAll('.nl-sep[data-idx]').forEach(sep=>{
    const idx=parseInt(sep.dataset.idx);
    const prevItem=document.querySelector(`.news-item[data-idx="${idx}"]`);
    const nextItem=document.querySelector(`.news-item[data-idx="${idx+1}"]`);
    const hide=(!prevItem||prevItem.classList.contains('news-filtered'))&&(!nextItem||nextItem.classList.contains('news-filtered'));
    sep.classList.toggle('filtered',hide);
  });
}

// ─── RENDER TODAY ────────────────────────────────────────────────────────────
function renderToday(){
  const readMin=calcReadTime();
  const fbCount=TODAY.news.filter(n=>getFeedback(n.id)).length;
  const fbText=fbCount>0?`${fbCount}/${TODAY.news.length} évalué${fbCount>1?'s':''}`:'Aucun feedback';

  // Chips filtres (catégories uniques)
  const cats=[...new Set(TODAY.news.map(n=>n.categorie))];
  const chips=`<div class="cat-chips">
    <button class="cat-chip active-all" onclick="setFilter('all',this)">Tout</button>
    ${cats.map(c=>`<button class="cat-chip" data-cat="${c}" onclick="setFilter('${c}',this)">${TODAY.news.find(n=>n.categorie===c).label}</button>`).join('')}
  </div>`;

  const iconClock=`<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>`;
  const iconBubble=`<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>`;
  const iconDl=`<svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>`;
  const exportBtn=`<button class="btn-action" id="btn-export-fb" onclick="downloadFeedback()" style="font-size:11px;padding:3px 10px;color:var(--sand-500);${fbCount===0?'opacity:.4;':''}">${iconDl} feedback.json</button>`;

  let h=`<div class="page-header">
    <h1 class="page-heading">${TODAY.date_longue}</h1>
    <p class="page-sub">L'essentiel de l'IA · ${readMin} min de lecture</p>
  </div>
  <p class="nl-chapeau">${TODAY.chapeau}</p>
  <div class="today-meta">
    <span class="today-meta-item">${iconClock} ${readMin} min</span>
    <div class="today-meta-sep"></div>
    <span class="today-meta-item" id="today-fb-count">${iconBubble} ${fbText}</span>
    <div class="today-meta-sep"></div>
    ${exportBtn}
  </div>
  ${chips}`;

  TODAY.news.forEach((n,i)=>{
    const fb=getFeedback(n.id);
    const src=n.sources.map(s=>`<a href="${s.url}" target="_blank">${s.nom}</a>`).join('');
    if(i>0)h+=`<div class="nl-sep" data-idx="${i}"></div>`;
    h+=`<div class="news-item ${catClass(n.categorie)}" data-cat="${n.categorie}" data-idx="${i}">
      <div class="news-meta"><span class="cat-badge">${n.num}</span><span class="cat-label">${n.label}</span></div>
      <h2 class="news-title">${n.titre}</h2>
      <p class="news-body">${n.body}</p>
      <div class="news-sources"><span class="news-confiance-badge">${n.confiance}</span>${src}</div>
      <div class="news-actions">
        <button class="btn-action btn-thumb${fb==='up'?' active-up':''}" data-id="${n.id}" data-type="up" onclick="saveFeedback('${n.id}','up')">${fb==='up'?ICON_UP+' Pertinent':ICON_UP}</button>
        <button class="btn-action btn-thumb${fb==='down'?' active-down':''}" data-id="${n.id}" data-type="down" onclick="saveFeedback('${n.id}','down')">${fb==='down'?ICON_DOWN+' Moins utile':ICON_DOWN}</button>
        <button class="btn-action" onclick="shareNews('${n.id}')">✉️ Partager</button>
      </div></div>`;
  });
  h+=`<div class="nl-sep"></div><div class="radar-section"><div class="radar-heading">📋 Aussi sur le radar</div><ul class="radar-list">`;
  TODAY.radar.forEach(r=>{h+=`<li class="radar-item"><div class="radar-dot"></div><div class="radar-text"><strong>${r.titre}</strong>${r.desc?' — '+r.desc:''} <a href="${r.url}" target="_blank">Lire →</a></div></li>`;});
  h+=`</ul></div>`;
  document.getElementById('tab-today').innerHTML=h;
}

// ─── CAT COLOR MAP ────────────────────────────────────────────────────────────
const CAT_COLORS={societal:'#C45D3E',economie:'#3B6B9B',fonctionnel:'#4A7A5A',use_cases:'#6B5B8A',focus_retail:'#8B6B4A',fun_facts:'#9A7A3A'};

// ─── RENDER ARCHIVE ──────────────────────────────────────────────────────────
let arcFilter='all';

function renderArchive(){
  // Collect all unique categories across all newsletters
  const allCats=[...new Set(ARCHIVE.flatMap(nl=>nl.categories||[]))];

  const chips=`<div class="cat-chips" id="arc-chips">
    <button class="cat-chip active-all" onclick="setArcFilter('all',this)">Tout</button>
    ${allCats.map(c=>{
      const nl=ARCHIVE.find(n=>(n.categories||[]).includes(c));
      const item=nl&&nl.news?(nl.news.find(x=>x.categorie===c)||null):null;
      const label=item?item.label:c;
      return `<button class="cat-chip" data-cat="${c}" onclick="setArcFilter('${c}',this)">${label}</button>`;
    }).join('')}
  </div>`;

  const totalNews=ARCHIVE.reduce((s,nl)=>s+(nl.news||[]).length,0);
  let h=`<div class="page-header"><h1 class="page-heading">Archives</h1><p class="page-sub">${ARCHIVE.length} éditions · ${totalNews} articles</p></div>
  <div class="arc-search-wrap">
    <svg class="arc-search-icon" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
    <input class="arc-search" id="arc-search-input" type="text" placeholder="Rechercher un article ou une date…" oninput="filterArchive(this.value)" autocomplete="off">
  </div>
  ${chips}
  <div id="archive-cards-view">
    <div class="archive-grid" id="archive-grid">`;

  ARCHIVE.forEach(nl=>{
    const newsHtml=(nl.news||[]).map(n=>`<li data-cat="${n.categorie}">${n.titre}</li>`).join('');
    h+=`<div class="archive-card" data-cats="${(nl.categories||[]).join(',')}" onclick="openNewsletter('${nl.fichier}','${nl.date_longue}')">
      <div class="arc-date ${nl.is_today?'arc-today':''}">${nl.is_today?'Aujourd\'hui · ':''}${nl.date_longue}</div>
      <ul class="arc-titles">${newsHtml}</ul>
      <div class="arc-link">Lire l'édition →</div>
    </div>`;
  });

  h+=`</div></div>
  <div id="archive-search-view" style="display:none">
    <div class="arc-results" id="arc-results"></div>
    <div class="arc-empty" id="arc-empty" style="display:none">Aucun résultat pour cette recherche.</div>
  </div>`;

  document.getElementById('tab-archive').innerHTML=h;
  arcFilter='all';
}

function setArcFilter(cat,btn){
  arcFilter=cat;
  document.querySelectorAll('#arc-chips .cat-chip').forEach(c=>c.classList.remove('active-all','active-cat'));
  btn.classList.add(cat==='all'?'active-all':'active-cat');
  const q=(document.getElementById('arc-search-input')||{}).value||'';
  filterArchive(q);
}

function filterArchive(query){
  const q=query.toLowerCase().trim();
  const cardsView=document.getElementById('archive-cards-view');
  const searchView=document.getElementById('archive-search-view');
  if(!cardsView||!searchView)return;

  // Vue cartes uniquement si aucun filtre ET aucune recherche
  if(!q && arcFilter==='all'){
    cardsView.style.display='';
    searchView.style.display='none';
    return;
  }

  // Vue résultats individuels — pour toute catégorie sélectionnée OU toute recherche
  cardsView.style.display='none';
  searchView.style.display='';
  const resultsEl=document.getElementById('arc-results');
  const emptyEl=document.getElementById('arc-empty');

  let results=[];
  ARCHIVE.forEach(nl=>{
    (nl.news||[]).forEach((n,ni)=>{
      const catMatch=arcFilter==='all'||n.categorie===arcFilter;
      const textMatch=!q||(n.titre.toLowerCase().includes(q)||nl.date_longue.toLowerCase().includes(q));
      if(catMatch&&textMatch){
        results.push({...n,id:`${nl.date}-${String(ni+1).padStart(3,'0')}`,date_longue:nl.date_longue,fichier:nl.fichier});
      }
    });
  });

  if(results.length===0){
    resultsEl.innerHTML='';
    emptyEl.style.display='block';
  } else {
    emptyEl.style.display='none';
    const color=cat=>CAT_COLORS[cat]||'var(--sand-700)';
    resultsEl.innerHTML=results.map((r,ri)=>{
      const full=getFullArticle(r.id);
      if(full){
        const sep=ri>0?'<div class="nl-sep"></div>':'';
        return sep+renderArchiveCard(full,r.date_longue,r.fichier,q);
      }
      const fbUp=getFeedback(r.id)==='up',fbDn=getFeedback(r.id)==='down';
      return `<div class="arc-result-item">
        <span class="arc-result-badge" style="background:${color(r.categorie)};flex-shrink:0">${r.label.slice(0,2)}</span>
        <span class="arc-result-title" style="flex:1" onclick="openNewsletter('${r.fichier}','${r.date_longue}')">${highlight(r.titre,q)}</span>
        <div style="display:flex;align-items:center;gap:4px;flex-shrink:0;margin-left:8px;" onclick="event.stopPropagation()">
          <button class="btn-action btn-thumb${fbUp?' active-up':''}" data-id="${r.id}" data-type="up" onclick="saveFeedback('${r.id}','up')" style="padding:3px 8px;">${fbUp?ICON_UP+' Pertinent':ICON_UP}</button>
          <button class="btn-action btn-thumb${fbDn?' active-down':''}" data-id="${r.id}" data-type="down" onclick="saveFeedback('${r.id}','down')" style="padding:3px 8px;">${fbDn?ICON_DOWN+' Moins utile':ICON_DOWN}</button>
        </div>
        <span class="arc-result-date" style="flex-shrink:0">${r.date_longue}</span>
      </div>`;
    }).join('');
  }
}

function highlight(text,query){
  if(!query)return text;
  const re=new RegExp('('+query.replace(/[.*+?^${}()|[\]\\]/g,'\\$&')+')','gi');
  return text.replace(re,'<mark style="background:rgba(196,93,62,.15);color:var(--accent);border-radius:2px;padding:0 1px">$1</mark>');
}

// ─── NEWSLETTER OVERLAY ───────────────────────────────────────────────────────
function openNewsletter(fichier,titre){
  const scroll=document.getElementById('nl-scroll');
  const frame=document.getElementById('nl-frame');
  const content=document.getElementById('nl-content');

  // Extraire la date depuis le nom de fichier (ex: newsletter-2026-04-23.html)
  const dateMatch=fichier.match(/(\d{4}-\d{2}-\d{2})/);
  const date=dateMatch?dateMatch[1]:null;

  // Chercher les données pour rendu inline
  let nlData=null;
  if(date){
    if(date===TODAY.date){
      nlData={chapeau:TODAY.chapeau,news:TODAY.news,date_longue:TODAY.date_longue};
    } else if(ARCHIVE_FULL[date]&&(ARCHIVE_FULL[date].articles||[]).length>0){
      const arc=ARCHIVE.find(a=>a.date===date);
      nlData={chapeau:ARCHIVE_FULL[date].chapeau,news:ARCHIVE_FULL[date].articles,date_longue:arc?arc.date_longue:titre};
    }
  }

  if(nlData){
    frame.style.display='none';
    scroll.style.display='';
    content.innerHTML=renderNewsletterInline(nlData);
    scroll.scrollTop=0;
  } else {
    scroll.style.display='none';
    frame.style.display='';
    frame.src=fichier.startsWith('newsletters/')?fichier:'newsletters/'+fichier;
  }

  document.getElementById('nl-topbar-title').textContent=titre||'';
  document.getElementById('nl-overlay').classList.add('open');
  window.scrollTo(0,0);
}

function renderNewsletterInline(data){
  const esc=s=>(s||'').replace(/'/g,"&#39;").replace(/"/g,'&quot;');
  let h=`<div class="page-header">
    <h1 class="page-heading">${data.date_longue}</h1>
    <p class="page-sub">L'essentiel de l'IA</p>
  </div>
  <p class="nl-chapeau">${data.chapeau||''}</p>`;

  (data.news||[]).forEach((n,i)=>{
    const fb=getFeedback(n.id);
    const src=(n.sources||[]).map(s=>`<a href="${s.url}" target="_blank">${s.nom}</a>`).join('');
    if(i>0)h+=`<div class="nl-sep"></div>`;
    h+=`<div class="news-item ${catClass(n.categorie)}" data-cat="${n.categorie}">
      <div class="news-meta"><span class="cat-badge">${n.num||i+1}</span><span class="cat-label">${n.label}</span></div>
      <h2 class="news-title">${n.titre}</h2>
      <p class="news-body">${n.body}</p>
      <div class="news-sources"><span class="news-confiance-badge">${n.confiance||''}</span>${src}</div>
      <div class="news-actions">
        <button class="btn-action btn-thumb${fb==='up'?' active-up':''}" data-id="${n.id}" data-type="up" onclick="saveFeedback('${n.id}','up')">${fb==='up'?ICON_UP+' Pertinent':ICON_UP}</button>
        <button class="btn-action btn-thumb${fb==='down'?' active-down':''}" data-id="${n.id}" data-type="down" onclick="saveFeedback('${n.id}','down')">${fb==='down'?ICON_DOWN+' Moins utile':ICON_DOWN}</button>
        <button class="btn-action" onclick="shareArchiveNews('${esc(n.titre)}','${esc(data.date_longue)}')">✉️ Partager</button>
      </div>
    </div>`;
  });
  return h;
}

function closeNewsletter(){
  document.getElementById('nl-overlay').classList.remove('open');
  setTimeout(()=>{
    document.getElementById('nl-frame').src='about:blank';
    document.getElementById('nl-content').innerHTML='';
  },300);
}

// ─── SETTINGS : état des catégories ─────────────────────────────────────────
let catState=[];

function renderSettings(){
  catState=JSON.parse(JSON.stringify(CONFIG.contenu.categories_actives));
  const ghCfg=getGithubConfig();
  const niveaux=['debutant','intermediaire','experimente','expert'];
  const langues=['fr','en','es','de'];
  const tons={accessible_expert:'Accessible expert',vulgarise:'Vulgarisé',editorial:'Éditorial',analytique:'Analytique'};
  const pc={fraicheur:'Fraîcheur',reprise_multi_sources:'Multi-sources',impact_sectoriel:'Impact sectoriel',originalite:'Originalité',engagement_potentiel:'Engagement'};
  const nOpts=niveaux.map(v=>`<option value="${v}" ${CONFIG.destinataire.niveau_expertise===v?'selected':''}>${v.charAt(0).toUpperCase()+v.slice(1)}</option>`).join('');
  const lOpts=langues.map(v=>`<option value="${v}" ${CONFIG.format.langue===v?'selected':''}>${v.toUpperCase()}</option>`).join('');
  const tOpts=Object.entries(tons).map(([k,v])=>`<option value="${k}" ${CONFIG.format.ton===k?'selected':''}>${v}</option>`).join('');
  const sHtml=Object.entries(pc).map(([k,l])=>`<div class="slider-row"><span class="slider-name">${l}</span><input type="range" id="poids_${k}" min="0" max="100" value="${CONFIG.scoring.poids[k]}" oninput="onSliderInput('${k}')"><span class="slider-val" id="val_${k}">${CONFIG.scoring.poids[k]}</span></div>`).join('');

  // Summary card
  const activeCatsCount=CONFIG.contenu.categories_actives.filter(c=>c.actif).length;
  const ton={accessible_expert:'Accessible expert',vulgarise:'Vulgarisé',editorial:'Éditorial',analytique:'Analytique'};
  const summaryCard=`<div class="settings-summary-card">
    <div class="ssc-item"><span class="ssc-label">Destinataire</span><span class="ssc-val">${CONFIG.destinataire.nom}</span></div>
    <div class="ssc-item"><span class="ssc-label">News / Radar</span><span class="ssc-val">${CONFIG.contenu.nb_news_principal} + ${CONFIG.contenu.nb_news_radar}</span></div>
    <div class="ssc-item"><span class="ssc-label">Catégories</span><span class="ssc-val">${activeCatsCount} actives</span></div>
    <div class="ssc-item"><span class="ssc-label">Langue</span><span class="ssc-val">${CONFIG.format.langue.toUpperCase()}</span></div>
    <div class="ssc-item"><span class="ssc-label">Ton</span><span class="ssc-val">${ton[CONFIG.format.ton]||CONFIG.format.ton}</span></div>
  </div>`;

  const iconUser=`<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="8" r="4"/><path d="M4 20c0-4 3.6-7 8-7s8 3 8 7"/></svg>`;
  const iconContent=`<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/></svg>`;
  const iconFormat=`<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="4 7 4 4 20 4 20 7"/><line x1="9" y1="20" x2="15" y2="20"/><line x1="12" y1="4" x2="12" y2="20"/></svg>`;
  const iconScoring=`<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/></svg>`;
  const iconEmail=`<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"/><polyline points="22,6 12,13 2,6"/></svg>`;

  document.getElementById('tab-settings').innerHTML=`
  <div class="page-header"><h1 class="page-heading">Paramètres</h1><p class="page-sub">Configure ta newsletter, puis télécharge le fichier <code>config.json</code> et remplace-le dans le dossier VEILLE IA.</p></div>
  ${summaryCard}

  <!-- 1. DESTINATAIRE & LIVRAISON -->
  <div class="settings-section">
    <div class="settings-title"><span class="settings-section-icon">${iconUser} Destinataire & livraison</span></div>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:0 28px;flex-wrap:wrap;" class="settings-grid-2">
      <div class="form-row"><label class="form-label">Prénom / nom</label><input class="form-input" id="s_nom" value="${CONFIG.destinataire.nom}"></div>
      <div class="form-row"><label class="form-label">Niveau d'expertise</label><select class="form-select" id="s_niveau">${nOpts}</select><div class="form-hint">Influence la profondeur des résumés</div></div>
      <div class="form-row"><label class="form-label">Adresse email</label><input class="form-input" id="s_email" type="email" value="${CONFIG.destinataire.email}"></div>
      <div class="form-row"><label class="form-label">Préfixe du sujet</label><input class="form-input" id="s_email_prefix" value="${CONFIG.email.objet_prefix}"><div class="form-hint">Ex. ☀️ Briefing IA —</div></div>
    </div>
  </div>

  <!-- 2. CONTENU -->
  <div class="settings-section">
    <div class="settings-title"><span class="settings-section-icon">${iconContent} Contenu</span></div>

    <div style="display:flex;gap:32px;flex-wrap:wrap;margin-bottom:24px;">
      <div class="form-row"><label class="form-label">Articles principaux</label><input class="form-number" id="s_nb_news" type="number" value="${CONFIG.contenu.nb_news_principal}" min="1" max="10"><div class="form-hint">Recommandé : 4 à 7</div></div>
      <div class="form-row"><label class="form-label">Articles radar</label><input class="form-number" id="s_nb_radar" type="number" value="${CONFIG.contenu.nb_news_radar}" min="0" max="10"><div class="form-hint">0 pour désactiver</div></div>
      <div class="form-row" style="display:flex;align-items:center;gap:12px;padding-top:22px;">
        <label class="toggle"><input type="checkbox" id="s_panachage" ${CONFIG.contenu.panachage_categories?'checked':''}><div class="toggle-slider"></div></label>
        <div><div class="form-label" style="margin-bottom:2px;">Panachage de catégories</div><div class="form-hint">Au moins 3 catégories différentes par édition</div></div>
      </div>
    </div>

    <div class="form-row"><label class="form-label" style="margin-bottom:12px;">Catégories <span style="font-family:Inter,sans-serif;font-size:11px;color:var(--sand-500);font-weight:400;margin-left:6px;">— priorité 1 = mise en avant maximale</span></label>
      <div id="cat-list"></div>
    </div>

    <div style="display:grid;grid-template-columns:1fr 1fr;gap:0 28px;margin-top:20px;" class="settings-grid-2">
      <div class="form-row"><label class="form-label">Thèmes à favoriser</label><input class="form-input" id="s_themes_fav" value="${CONFIG.contenu.themes_favoris.join(', ')}" placeholder="agents IA, robotique…"><div class="form-hint">Séparés par des virgules</div></div>
      <div class="form-row"><label class="form-label">Thèmes à exclure</label><input class="form-input" id="s_themes_excl" value="${CONFIG.contenu.themes_exclus.join(', ')}" placeholder="crypto, NFT…"><div class="form-hint">Séparés par des virgules</div></div>
    </div>
  </div>

  <!-- 3. FORMAT -->
  <div class="settings-section">
    <div class="settings-title"><span class="settings-section-icon">${iconFormat} Format éditorial</span></div>
    <div style="display:flex;gap:24px;flex-wrap:wrap;">
      <div class="form-row"><label class="form-label">Langue</label><select class="form-select" id="s_langue">${lOpts}</select></div>
      <div class="form-row"><label class="form-label">Ton</label><select class="form-select" id="s_ton">${tOpts}</select></div>
      <div class="form-row"><label class="form-label">Longueur max</label><div style="display:flex;align-items:center;gap:8px;"><input class="form-number" id="s_longueur" type="number" value="${CONFIG.format.longueur_max_mots}" min="300" max="3000" style="width:90px;"><span style="font-family:'Inter',sans-serif;font-size:12px;color:var(--sand-500);">mots</span></div></div>
    </div>
  </div>

  <!-- 4. SCORING -->
  <div class="settings-section">
    <div class="settings-title"><span class="settings-section-icon">${iconScoring} Scoring — pondération des critères</span></div>
    <div class="form-hint" style="margin-bottom:18px;margin-top:-8px;">Le total doit être égal à 100. L'ajustement est automatique.</div>
    <div class="slider-group">${sHtml}</div>
    <div class="slider-total slider-ok" id="slider_total">✓ Total : 100 / 100</div>

    <div style="display:flex;gap:20px;flex-wrap:wrap;margin-top:28px;padding-top:20px;border-top:1px solid var(--sand-100);">
      <div class="form-row"><label class="form-label">Décroissance / jour</label><div style="display:flex;align-items:center;gap:8px;"><input class="form-number" id="s_decro" type="number" value="${CONFIG.scoring.decroissance_quotidienne_pct}" min="0" max="50" style="width:64px;"><span style="font-family:'Inter',sans-serif;font-size:12px;color:var(--sand-500);">%</span></div><div class="form-hint">Score perdu chaque jour dans le backlog</div></div>
      <div class="form-row"><label class="form-label">Score min. backlog</label><input class="form-number" id="s_scoremin" type="number" value="${CONFIG.scoring.score_minimum_backlog}" min="0" max="50"><div class="form-hint">Seuil en dessous duquel un article est retiré</div></div>
      <div class="form-row"><label class="form-label">Bonus feedback</label><div style="display:flex;align-items:center;gap:8px;"><input class="form-number" id="s_bonus" type="number" value="${CONFIG.scoring.bonus_feedback_pts}" min="0" max="30"><span style="font-family:'Inter',sans-serif;font-size:12px;color:var(--sand-500);">pts</span></div><div class="form-hint">Ajouté aux articles ayant eu un retour positif</div></div>
    </div>
  </div>

  <!-- GITHUB -->
  <div class="settings-section" style="margin-top:32px;">
    <div class="settings-title"><span class="settings-section-icon">
      <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M9 19c-5 1.5-5-2.5-7-3m14 6v-3.87a3.37 3.37 0 0 0-.94-2.61c3.14-.35 6.44-1.54 6.44-7A5.44 5.44 0 0 0 20 4.77 5.07 5.07 0 0 0 19.91 1S18.73.65 16 2.48a13.38 13.38 0 0 0-7 0C6.27.65 5.09 1 5.09 1A5.07 5.07 0 0 0 5 4.77a5.44 5.44 0 0 0-1.5 3.78c0 5.42 3.3 6.61 6.44 7A3.37 3.37 0 0 0 9 18.13V22"/></svg>
      GitHub — publication automatique
    </span></div>
    <p class="form-hint" style="margin-bottom:18px;margin-top:-6px;">Configure un token pour publier <code>sources.json</code> et <code>feedback_ui.json</code> directement sur GitHub, sans téléchargement ni commit manuel.</p>
    <div class="form-row">
      <label class="form-label">Personal Access Token
        <a href="https://github.com/settings/personal-access-tokens/new" target="_blank" style="font-size:11px;color:var(--accent);text-decoration:none;margin-left:6px;">Créer →</a>
      </label>
      <input class="form-input" id="gh_token" type="password" value="${ghCfg.token}" placeholder="github_pat_… ou ghp_…" autocomplete="off">
      <div class="form-hint">Token Fine-grained avec <strong>Contents → Read and write</strong> sur ce repo uniquement</div>
    </div>
    <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:0 20px;" class="settings-grid-gh">
      <div class="form-row"><label class="form-label">Owner</label><input class="form-input" id="gh_owner" value="${ghCfg.owner}"></div>
      <div class="form-row"><label class="form-label">Repo</label><input class="form-input" id="gh_repo" value="${ghCfg.repo}"></div>
      <div class="form-row"><label class="form-label">Branche</label><input class="form-input" id="gh_branch" value="${ghCfg.branch}"></div>
    </div>
    <div style="display:flex;align-items:center;gap:12px;margin-top:4px;">
      <button class="btn-action" onclick="saveGithubSettings()" style="font-size:12px;padding:7px 16px;">Enregistrer</button>
      <span id="gh_status" style="font-family:Inter,sans-serif;font-size:12px;color:var(--sand-500);">${ghCfg.token?'✓ Token configuré':'Aucun token — publication manuelle active'}</span>
    </div>
  </div>

  <!-- ACTION -->
  <div style="padding-top:4px;">
    <button class="btn-save" onclick="openConfirmModal()">Enregistrer les modifications →</button>
    <div class="save-note">Après téléchargement, remplace <code>config.json</code> dans ton dossier <strong>VEILLE IA</strong> sur Dropbox.<br>La prochaine newsletter utilisera automatiquement ces paramètres.</div>
  </div>`;

  // CSS responsive pour les grilles 2 colonnes sur mobile
  const style=document.getElementById('settings-grid-style')||document.createElement('style');
  style.id='settings-grid-style';
  style.textContent='@media(max-width:560px){.settings-grid-2{grid-template-columns:1fr!important;}.settings-grid-gh{grid-template-columns:1fr!important;}}';
  document.head.appendChild(style);

  renderCatList();
  originalSettings=buildConfig();
}

// ─── CATÉGORIES : rendu trié par priorité + mise à jour dynamique ────────────
function renderCatList(){
  const sorted=[...catState].sort((a,b)=>a.priorite-b.priorite);
  const html=sorted.map((cat,i)=>{
    const origIdx=catState.findIndex(c=>c.id===cat.id);
    const col=CAT_COLORS[cat.id]||'var(--sand-700)';
    return `<div class="cat-row" id="cat-row-${cat.id}" style="border-left:2px solid ${cat.actif?col:'var(--sand-200)'};padding-left:10px;">
      <label class="toggle toggle-${cat.id}"><input type="checkbox" id="cat_active_${origIdx}" ${cat.actif?'checked':''} onchange="catState[${origIdx}].actif=this.checked;renderCatList()"><div class="toggle-slider"></div></label>
      <span class="cat-row-label" style="${cat.actif?'color:var(--sand-900)':'color:var(--sand-300)'}">${cat.label}</span>
      <span class="cat-row-desc" style="${cat.actif?'':'opacity:.4'}">${cat.description}</span>
      <span class="cat-prio-wrap">
        <input type="number" class="form-number" id="cat_prio_${origIdx}" value="${cat.priorite}" min="1" max="5" style="width:52px;"
          oninput="catState[${origIdx}].priorite=Math.max(1,Math.min(5,parseInt(this.value)||1));renderCatList()">
      </span>
    </div>`;
  }).join('');
  const el=document.getElementById('cat-list');
  if(el) el.innerHTML=html;
}

// ─── SLIDERS : ajustement proportionnel automatique ─────────────────────────
function onSliderInput(changedKey){
  const keys=['fraicheur','reprise_multi_sources','impact_sectoriel','originalite','engagement_potentiel'];
  const changedVal=Math.min(100,Math.max(0,parseInt(document.getElementById('poids_'+changedKey).value)||0));
  document.getElementById('val_'+changedKey).textContent=changedVal;
  const otherKeys=keys.filter(k=>k!==changedKey);
  const remaining=Math.max(0,100-changedVal);
  const currentOtherVals=otherKeys.map(k=>Math.max(0,parseInt(document.getElementById('poids_'+k).value)||0));
  const currentOtherTotal=currentOtherVals.reduce((a,b)=>a+b,0);
  let distributed=0;
  otherKeys.forEach((k,i)=>{
    let newVal;
    if(i===otherKeys.length-1){
      newVal=Math.max(0,remaining-distributed);
    } else if(currentOtherTotal===0){
      newVal=Math.floor(remaining/otherKeys.length);
    } else {
      newVal=Math.round(currentOtherVals[i]/currentOtherTotal*remaining);
    }
    distributed+=newVal;
    document.getElementById('poids_'+k).value=newVal;
    document.getElementById('val_'+k).textContent=newVal;
  });
  const el=document.getElementById('slider_total');
  const total=keys.reduce((s,k)=>s+(parseInt(document.getElementById('poids_'+k).value)||0),0);
  el.textContent=total===100?'✓ Total : 100 / 100':`Total : ${total} / 100`;
  el.className='slider-total'+(total===100?' slider-ok':'');
}

// ─── MODAL CONFIRMATION ──────────────────────────────────────────────────────
let pendingConfig=null;
let originalSettings=null;

function detectChanges(orig,mod){
  const changes=[];
  function diff(label,a,b){if(String(a)!==String(b))changes.push({label,from:String(a),to:String(b)});}
  diff('Nom destinataire',orig.destinataire.nom,mod.destinataire.nom);
  diff('Email',orig.destinataire.email,mod.destinataire.email);
  diff('Niveau expertise',orig.destinataire.niveau_expertise,mod.destinataire.niveau_expertise);
  diff('News principales',orig.contenu.nb_news_principal,mod.contenu.nb_news_principal);
  diff('News radar',orig.contenu.nb_news_radar,mod.contenu.nb_news_radar);
  diff('Panachage catégories',orig.contenu.panachage_categories,mod.contenu.panachage_categories);
  diff('Thèmes favoris',orig.contenu.themes_favoris.join(', ')||'—',mod.contenu.themes_favoris.join(', ')||'—');
  diff('Thèmes exclus',orig.contenu.themes_exclus.join(', ')||'—',mod.contenu.themes_exclus.join(', ')||'—');
  diff('Langue',orig.format.langue,mod.format.langue);
  diff('Ton',orig.format.ton,mod.format.ton);
  diff('Longueur max (mots)',orig.format.longueur_max_mots,mod.format.longueur_max_mots);
  const plabels={fraicheur:'Poids fraîcheur',reprise_multi_sources:'Poids multi-sources',impact_sectoriel:'Poids impact',originalite:'Poids originalité',engagement_potentiel:'Poids engagement'};
  Object.entries(plabels).forEach(([k,l])=>diff(l,orig.scoring.poids[k],mod.scoring.poids[k]));
  diff('Décroissance quotidienne (%)',orig.scoring.decroissance_quotidienne_pct,mod.scoring.decroissance_quotidienne_pct);
  diff('Score minimum backlog',orig.scoring.score_minimum_backlog,mod.scoring.score_minimum_backlog);
  diff('Bonus feedback (pts)',orig.scoring.bonus_feedback_pts,mod.scoring.bonus_feedback_pts);
  diff('Préfixe email',orig.email.objet_prefix,mod.email.objet_prefix);
  orig.contenu.categories_actives.forEach((oc,i)=>{
    const mc=mod.contenu.categories_actives[i];if(!mc)return;
    if(oc.actif!==mc.actif)diff(`${oc.label} — actif`,oc.actif?'oui':'non',mc.actif?'oui':'non');
    if(String(oc.priorite)!==String(mc.priorite))diff(`${oc.label} — priorité`,oc.priorite,mc.priorite);
  });
  return changes;
}

function openConfirmModal(){
  pendingConfig=buildConfig();
  const changes=originalSettings?detectChanges(originalSettings,pendingConfig):[];
  let summaryHtml;
  if(changes.length===0){
    summaryHtml=`<div style="font-family:'Inter',sans-serif;font-size:13px;color:var(--sand-500);text-align:center;padding:12px 0;line-height:1.6;">Aucune modification détectée.<br>Les paramètres actuels seront téléchargés.</div>`;
  } else {
    summaryHtml=changes.map(({label,from,to})=>`<div class="modal-summary-item"><span>${label}</span><strong><span style="color:var(--sand-500);text-decoration:line-through;font-weight:400;margin-right:4px;">${from}</span>→ ${to}</strong></div>`).join('');
  }
  document.getElementById('modal-summary').innerHTML=summaryHtml;
  document.getElementById('modal-overlay').classList.add('open');
}

function closeModal(e){if(e.target===document.getElementById('modal-overlay'))closeModalDirect();}
function closeModalDirect(){document.getElementById('modal-overlay').classList.remove('open');pendingConfig=null;}

function confirmDownload(){
  if(!pendingConfig)return;
  const blob=new Blob([JSON.stringify(pendingConfig,null,2)],{type:'application/json'});
  const a=document.createElement('a');
  a.href=URL.createObjectURL(blob);
  a.download='config.json';
  a.click();
  URL.revokeObjectURL(a.href);
  closeModalDirect();
  showToast();
}

const _toastDefault='✓ config.json téléchargé — remplace-le dans ton dossier VEILLE IA';
let _toastTimer=null;

function showToast(msg){
  const t=document.getElementById('toast');
  t.classList.remove('toast-wide');
  t.textContent=msg||_toastDefault;
  _triggerToast(t,4000);
}

function showSourceAddedToast(nom){
  const t=document.getElementById('toast');
  t.classList.add('toast-wide');
  t.innerHTML=
    `<div class="toast-check">✓</div>`+
    `<div class="toast-body">`+
      `<div class="toast-body-title">${nom} ajouté</div>`+
      `<div class="toast-body-sub">Pour activer dès demain, télécharge <strong>sources.json</strong> et commite-le sur GitHub.</div>`+
    `</div>`+
    `<button class="btn-toast-action" onclick="downloadSources()">`+
      `<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>`+
      `sources.json`+
    `</button>`;
  _triggerToast(t,9000);
}

function _triggerToast(t,duration){
  if(_toastTimer)clearTimeout(_toastTimer);
  t.classList.add('show');
  _toastTimer=setTimeout(()=>{
    t.classList.remove('show');
    setTimeout(()=>{t.classList.remove('toast-wide');t.textContent=_toastDefault;},400);
  },duration);
}

// ─── FEEDBACK EXPORT ─────────────────────────────────────────────────────────
async function downloadFeedback(){
  const notes={};
  for(let i=0;i<localStorage.length;i++){
    const key=localStorage.key(i);
    if(key&&key.startsWith('fb_')){
      const id=key.slice(3);
      const val=localStorage.getItem(key);
      if(val==='up')notes[id]=5;
      else if(val==='down')notes[id]=1;
    }
  }
  if(Object.keys(notes).length===0){showToast('Aucun feedback à exporter pour l\'instant');return;}
  const count=Object.keys(notes).length;
  const payload={
    derniere_maj:new Date().toISOString().slice(0,10),
    statut:'en_attente',
    notes
  };
  const cfg=getGithubConfig();
  if(cfg.token){
    showToast('⏳ Envoi des feedbacks…');
    const result=await githubPushFile(
      'newsletters/briefing-ia/feedback_ui.json',
      payload,
      `feat(feedback): ${count} note(s) ${payload.derniere_maj}`
    );
    if(result.ok){
      showGithubToast('feedback_ui.json',result);
    }else{
      // Fallback : téléchargement local
      _downloadBlob(JSON.stringify(payload,null,2),'feedback_ui.json');
      showFeedbackExportedToast(count);
    }
  }else{
    _downloadBlob(JSON.stringify(payload,null,2),'feedback_ui.json');
    showFeedbackExportedToast(count);
  }
}

function _downloadBlob(content,filename){
  const blob=new Blob([content],{type:'application/json'});
  const a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download=filename;a.click();URL.revokeObjectURL(a.href);
}

function showFeedbackExportedToast(count){
  const t=document.getElementById('toast');
  t.classList.add('toast-wide');
  t.innerHTML=
    `<div class="toast-check">✓</div>`+
    `<div class="toast-body">`+
      `<div class="toast-body-title">${count} feedback${count>1?'s':''} exporté${count>1?'s':''}</div>`+
      `<div class="toast-body-sub">Commite <strong>feedback_ui.json</strong> sur GitHub pour qu'il soit pris en compte dès demain.</div>`+
    `</div>`+
    `<button class="btn-toast-action" onclick="downloadFeedback()">`+
      `<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>`+
      `feedback_ui.json`+
    `</button>`;
  _triggerToast(t,9000);
}

// ─── BUILD CONFIG ────────────────────────────────────────────────────────────
function buildConfig(){
  const keys=['fraicheur','reprise_multi_sources','impact_sectoriel','originalite','engagement_potentiel'];
  const poids={};
  keys.forEach(k=>{poids[k]=parseInt(document.getElementById('poids_'+k).value)||0;});
  return {
    _doc:"Fichier de configuration de la newsletter IA.",
    destinataire:{nom:document.getElementById('s_nom').value,email:document.getElementById('s_email').value,niveau_expertise:document.getElementById('s_niveau').value},
    contenu:{
      nb_news_principal:parseInt(document.getElementById('s_nb_news').value)||6,
      nb_news_radar:parseInt(document.getElementById('s_nb_radar').value)||6,
      categories_actives:catState.map((cat,i)=>({...cat,actif:document.getElementById('cat_active_'+i)?document.getElementById('cat_active_'+i).checked:cat.actif,priorite:parseInt(document.getElementById('cat_prio_'+i)?.value)||cat.priorite})),
      panachage_categories:document.getElementById('s_panachage').checked,
      themes_favoris:document.getElementById('s_themes_fav').value.split(',').map(s=>s.trim()).filter(Boolean),
      themes_exclus:document.getElementById('s_themes_excl').value.split(',').map(s=>s.trim()).filter(Boolean)
    },
    format:{langue:document.getElementById('s_langue').value,ton:document.getElementById('s_ton').value,longueur_max_mots:parseInt(document.getElementById('s_longueur').value)||1200,chapeau:true,inclure_emoji:true,format_resume_news:"4-5 lignes",inclure_score_confiance:true,inclure_section_retour:true},
    scoring:{poids,decroissance_quotidienne_pct:parseInt(document.getElementById('s_decro').value)||15,score_minimum_backlog:parseInt(document.getElementById('s_scoremin').value)||10,bonus_feedback_pts:parseInt(document.getElementById('s_bonus').value)||10},
    email:{objet_prefix:document.getElementById('s_email_prefix').value,format_html:true},
    fichiers:CONFIG.fichiers
  };
}

// ─── SCROLL PROGRESS ─────────────────────────────────────────────────────────
window.addEventListener('scroll',()=>{
  const el=document.getElementById('scroll-progress');
  if(!el)return;
  const h=document.documentElement.scrollHeight-window.innerHeight;
  el.style.width=(h>0?Math.min(100,(window.scrollY/h*100)):0)+'%';
},{passive:true});

// ─── SOURCES ─────────────────────────────────────────────────────────────────
const TYPE_LABELS={blog_officiel:'Blog officiel',media_tech:'Média tech',newsletter:'Newsletter',newsletter_fr:'Newsletter FR',academique:'Académique'};
function typeClass(t){const m={blog_officiel:'type-blog_officiel',media_tech:'type-media_tech',newsletter:'type-newsletter',newsletter_fr:'type-newsletter_fr',academique:'type-academique'};return m[t]||'type-default';}

function scoreDots(val,max=5){
  let h='<div class="score-dots">';
  for(let i=1;i<=max;i++)h+=`<div class="score-dot${i<=val?' filled':''}"></div>`;
  return h+'</div>';
}

function renderSourceCard(src,type,idx){
  const trashIcon=`<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14H6L5 6"/><path d="M10 11v6M14 11v6"/><path d="M9 6V4h6v2"/></svg>`;
  if(type==='primaire'){
    const score=src.score_global!=null?parseFloat(src.score_global).toFixed(1):'—';
    return `<div class="source-card">
      <button class="source-delete" onclick="deleteSource('primaire',${idx})" title="Supprimer">${trashIcon}</button>
      <div style="display:flex;align-items:flex-start;gap:12px;margin-bottom:12px;">
        <div style="flex:1;min-width:0;">
          <div style="margin-bottom:8px;"><span class="source-type-badge ${typeClass(src.type)}">${TYPE_LABELS[src.type]||src.type}</span></div>
          <div class="source-name">${src.url?`<a href="${src.url}" target="_blank">${src.nom}</a>`:src.nom}</div>
        </div>
        <div style="text-align:right;flex-shrink:0;padding-right:22px;">
          <div class="source-score-main">${score}</div>
          <div class="source-score-label">Score<br>global</div>
        </div>
      </div>
      <div class="source-scores">
        <div class="score-mini"><div class="score-mini-label">Fiabilité</div>${scoreDots(src.fiabilite)}</div>
        <div class="score-mini"><div class="score-mini-label">Primauté</div>${scoreDots(src.primaute)}</div>
        <div class="score-mini"><div class="score-mini-label">Clarté</div>${scoreDots(src.clarte)}</div>
        <div class="score-mini"><div class="score-mini-label">Pertinence</div>${scoreDots(src.pertinence)}</div>
      </div>
      ${src.notes?`<div class="source-notes" style="margin-top:10px;">${src.notes}</div>`:''}
    </div>`;
  } else {
    const platform=src.plateforme||'';
    const platformFirst=platform.split(' ')[0];
    const pClass=platformFirst==='LinkedIn'?'type-media_tech':platformFirst==='Instagram'||platformFirst==='YouTube'?'type-newsletter':'type-default';
    return `<div class="source-card">
      <button class="source-delete" onclick="deleteSource('relais',${idx})" title="Supprimer">${trashIcon}</button>
      <div style="display:flex;align-items:flex-start;gap:12px;margin-bottom:8px;">
        <div style="flex:1;min-width:0;">
          <div style="margin-bottom:7px;"><span class="source-type-badge ${pClass}">${platform}</span></div>
          <div class="source-name" style="font-size:15px;">${src.url?`<a href="${src.url}" target="_blank">${src.nom}</a>`:src.nom}</div>
        </div>
        <div style="text-align:right;flex-shrink:0;padding-right:22px;">
          <div class="source-score-main">${parseFloat(src.score_relais).toFixed(1)}</div>
          <div class="source-score-label">Score<br>global</div>
        </div>
      </div>
      <div class="source-scores">
        <div class="score-mini"><div class="score-mini-label">Score relais</div>${scoreDots(src.score_relais)}</div>
      </div>
      ${src.recherche_web?`<div class="source-notes" style="margin-top:8px;">🔍 ${src.recherche_web}</div>`:''}
      ${src.notes?`<div class="source-notes"${src.recherche_web?' style="margin-top:3px;"':''}>${src.notes}</div>`:''}
    </div>`;
  }
}

function renderSources(){
  const data=getSourcesState();
  const sorted_p=[...data.sources_primaires].sort((a,b)=>b.score_global-a.score_global);
  const sorted_r=[...data.sources_relais].sort((a,b)=>b.score_relais-a.score_relais);
  const primHtml=sorted_p.map(src=>renderSourceCard(src,'primaire',data.sources_primaires.indexOf(src))).join('');
  const relaisHtml=sorted_r.map(src=>renderSourceCard(src,'relais',data.sources_relais.indexOf(src))).join('');
  document.getElementById('tab-sources').innerHTML=`
  <div style="display:flex;align-items:flex-start;justify-content:space-between;flex-wrap:wrap;gap:12px;margin-bottom:36px;">
    <div>
      <h1 class="page-heading">Sources</h1>
      <p class="page-sub">${data.sources_primaires.length} sources primaires · ${data.sources_relais.length} sources relais</p>
    </div>
    <button class="btn-download-sources" onclick="downloadSources()" style="margin-top:6px;">
      <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
      sources.json
    </button>
  </div>
  <div class="sources-section">
    <div class="sources-section-title">Sources primaires</div>
    <div class="sources-grid">${primHtml}</div>
    <button class="btn-add-source" onclick="openAddSource('primaire')">
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
      Ajouter une source primaire
    </button>
  </div>
  <div class="sources-section">
    <div class="sources-section-title">Sources relais</div>
    <div class="sources-grid">${relaisHtml}</div>
    <button class="btn-add-source" onclick="openAddSource('relais')">
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
      Ajouter une source relais
    </button>
  </div>`;
}

function deleteSource(type,idx){
  const data=getSourcesState();
  const arr=type==='primaire'?data.sources_primaires:data.sources_relais;
  const name=arr[idx].nom;
  if(!confirm(`Supprimer « ${name} » ?`))return;
  arr.splice(idx,1);
  saveSourcesState();
  renderSources();
  const _ghCfg=getGithubConfig();
  if(_ghCfg.token){
    pushSourcesToGitHub();
  }else{
    showToast(`✓ ${name} supprimé — télécharge sources.json pour le rendre permanent`);
  }
}

let _addSourceType='primaire';
function openAddSource(type){
  _addSourceType=type;
  const isPrim=type==='primaire';
  document.getElementById('modal-sources-title').textContent=isPrim?'Ajouter une source primaire':'Ajouter une source relais';
  document.getElementById('modal-sources-form').innerHTML=isPrim?`
    <div class="modal-form-row"><label>Nom</label><input id="add_nom" placeholder="Ex. Wired AI" autocomplete="off"></div>
    <div class="modal-form-row"><label>URL</label><input id="add_url" type="url" placeholder="https://..."></div>
    <div class="modal-form-row"><label>Type</label>
      <select id="add_type">
        <option value="blog_officiel">Blog officiel</option>
        <option value="media_tech" selected>Média tech</option>
        <option value="newsletter">Newsletter</option>
        <option value="newsletter_fr">Newsletter FR</option>
        <option value="academique">Académique</option>
      </select>
    </div>
    <div class="modal-form-row"><label>Scores (sur 5)</label>
      <div class="score-input-row">
        <div class="score-input-item"><label>Fiabilité</label><input id="add_fiabilite" type="number" value="4" min="1" max="5"></div>
        <div class="score-input-item"><label>Primauté</label><input id="add_primaute" type="number" value="3" min="1" max="5"></div>
        <div class="score-input-item"><label>Clarté</label><input id="add_clarte" type="number" value="4" min="1" max="5"></div>
        <div class="score-input-item"><label>Pertinence</label><input id="add_pertinence" type="number" value="4" min="1" max="5"></div>
      </div>
    </div>
    <div class="modal-form-row"><label>Notes (optionnel)</label><textarea id="add_notes" placeholder="Description, spécificité…"></textarea></div>
  `:`
    <div class="modal-form-row"><label>Nom / Handle</label><input id="add_nom" placeholder="Ex. @ia_daily" autocomplete="off"></div>
    <div class="modal-form-row"><label>Plateforme</label><input id="add_plateforme" placeholder="LinkedIn / Instagram / YouTube…"></div>
    <div class="modal-form-row"><label>URL (optionnel)</label><input id="add_url" type="url" placeholder="https://..."></div>
    <div class="modal-form-row"><label>Recherche web</label><input id="add_recherche_web" placeholder="Terme pour retrouver via recherche…"></div>
    <div class="modal-form-row"><label>Score relais (1–5)</label><input id="add_score_relais" type="number" value="3" min="1" max="5" style="width:80px;text-align:center;"></div>
    <div class="modal-form-row"><label>Notes (optionnel)</label><textarea id="add_notes" placeholder="Description…"></textarea></div>
  `;
  document.getElementById('modal-sources').classList.add('open');
  setTimeout(()=>document.getElementById('add_nom')?.focus(),60);
}

function closeAddSource(){document.getElementById('modal-sources').classList.remove('open');}

function confirmAddSource(){
  const data=getSourcesState();
  const nom=(document.getElementById('add_nom')?.value||'').trim();
  if(!nom){alert('Le nom est requis.');return;}
  if(_addSourceType==='primaire'){
    const f=Math.min(5,Math.max(1,parseInt(document.getElementById('add_fiabilite').value)||4));
    const p=Math.min(5,Math.max(1,parseInt(document.getElementById('add_primaute').value)||3));
    const c=Math.min(5,Math.max(1,parseInt(document.getElementById('add_clarte').value)||4));
    const r=Math.min(5,Math.max(1,parseInt(document.getElementById('add_pertinence').value)||4));
    data.sources_primaires.push({nom,url:(document.getElementById('add_url')?.value||'').trim(),type:document.getElementById('add_type')?.value||'media_tech',fiabilite:f,primaute:p,clarte:c,pertinence:r,score_global:Math.round((f+p+c+r)/4*10)/10,notes:(document.getElementById('add_notes')?.value||'').trim()});
  } else {
    data.sources_relais.push({nom,plateforme:(document.getElementById('add_plateforme')?.value||'').trim(),url:(document.getElementById('add_url')?.value||'').trim(),recherche_web:(document.getElementById('add_recherche_web')?.value||'').trim(),score_relais:Math.min(5,Math.max(1,parseInt(document.getElementById('add_score_relais')?.value)||3)),notes:(document.getElementById('add_notes')?.value||'').trim()});
  }
  saveSourcesState();
  closeAddSource();
  renderSources();
  const _ghCfg=getGithubConfig();
  if(_ghCfg.token){
    pushSourcesToGitHub();
  }else{
    showSourceAddedToast(nom);
  }
}

async function pushSourcesToGitHub(){
  const data=getSourcesState();
  if(!data.meta)data.meta={};
  data.meta.last_updated=new Date().toISOString().slice(0,10);
  saveSourcesState();
  showToast('⏳ Publication sur GitHub…');
  const result=await githubPushFile(
    'newsletters/briefing-ia/sources.json',
    data,
    `feat(sources): mise à jour ${data.meta.last_updated}`
  );
  showGithubToast('sources.json',result);
  return result.ok;
}

async function downloadSources(){
  const cfg=getGithubConfig();
  if(cfg.token){
    await pushSourcesToGitHub();
  }else{
    const data=getSourcesState();
    if(!data.meta)data.meta={};
    data.meta.last_updated=new Date().toISOString().slice(0,10);
    const blob=new Blob([JSON.stringify(data,null,2)],{type:'application/json'});
    const a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download='sources.json';a.click();URL.revokeObjectURL(a.href);
    showToast('✓ sources.json téléchargé — remplace-le dans VEILLE IA');
  }
}

// ─── INIT ─────────────────────────────────────────────────────────────────────
renderToday();
