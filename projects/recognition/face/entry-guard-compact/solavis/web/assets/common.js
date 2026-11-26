/* Solavis web helpers: icons, API, shell, tables, charts, dialogs. Styling lives in app.css (tokens only). */
const $=i=>document.getElementById(i);
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const ago=t=>{if(!t)return 'never';const s=Date.now()/1000-t;return s<60?Math.round(s)+' s ago':s<3600?Math.round(s/60)+' min ago':s<86400?Math.round(s/3600)+' h ago':Math.round(s/86400)+' d ago'};
const when=t=>t?new Date(t*1000).toLocaleString():'';
const dshort=t=>t?new Date(t*1000).toLocaleDateString(undefined,{day:'2-digit',month:'short',year:'numeric'}):'–';
const vnd=n=>new Intl.NumberFormat('vi-VN').format(n||0)+' ₫';
const initials=n=>String(n||'?').replace(/@.*/,'').split(/[\s._-]+/).filter(Boolean).slice(0,2).map(w=>w[0].toUpperCase()).join('')||'?';

/* ---------- icons (our own inline set, outline, stroke 1.75) ---------- */
const P={dashboard:'M3 11l9-8 9 8v9a1 1 0 01-1 1h-5v-6H9v6H4a1 1 0 01-1-1z',devices:'M4 7h16v10H4zM9 17v3h6v-3M12 11m-2 0a2 2 0 104 0 2 2 0 10-4 0',alerts:'M6 8a6 6 0 1112 0c0 7 3 8 3 8H3s3-1 3-8M10 20a2 2 0 004 0',
 visitors:'M16 11a4 4 0 10-8 0M4 21v-1a6 6 0 0112 0v1M17 7a3 3 0 010 6M21 21v-1a5 5 0 00-3-4.6',people:'M12 12a4 4 0 100-8 4 4 0 000 8M4 21a8 8 0 0116 0',reports:'M4 20V10M10 20V4M16 20v-8M22 20H2',
 activity:'M8 6h13M8 12h13M8 18h13M3 6h.01M3 12h.01M3 18h.01',billing:'M2 6h20v12H2zM2 10h20',support:'M12 17h.01M9.5 9a2.5 2.5 0 115 0c0 2-2.5 2-2.5 4M12 22a10 10 0 100-20 10 10 0 000 20',
 settings:'M12 15a3 3 0 100-6 3 3 0 000 6M19 12a7 7 0 00-.1-1.2l2-1.5-2-3.4-2.3.9a7 7 0 00-2-1.2L14.2 3h-4l-.4 2.6a7 7 0 00-2 1.2l-2.3-.9-2 3.4 2 1.5A7 7 0 005 12c0 .4 0 .8.1 1.2l-2 1.5 2 3.4 2.3-.9a7 7 0 002 1.2l.4 2.6h4l.4-2.6a7 7 0 002-1.2l2.3.9 2-3.4-2-1.5c.1-.4.1-.8.1-1.2',
 team:'M4 21V3h10v18M14 9h6v12M8 7h2M8 11h2M8 15h2M17 13h.01M17 17h.01M2 21h20',customers:'M4 21V3h10v18M14 9h6v12M8 7h2M8 11h2M8 15h2M17 13h.01M17 17h.01M2 21h20',inventory:'M21 8l-9-5-9 5v8l9 5 9-5zM3 8l9 5 9-5M12 13v8',
 tasks:'M9 11l3 3 8-8M20 12v7a2 2 0 01-2 2H6a2 2 0 01-2-2V7a2 2 0 012-2h9',staff:'M12 12a4 4 0 100-8 4 4 0 000 8M4 21a8 8 0 0116 0',audit:'M8 6h13M8 12h13M8 18h13M3 6h.01M3 12h.01M3 18h.01',system:'M4 4h16v6H4zM4 14h16v6H4zM8 7h.01M8 17h.01',
 coin:'M12 21a9 9 0 100-18 9 9 0 000 18M12 7v10M9.5 9.5c0-1 1.2-1.5 2.5-1.5s2.5.5 2.5 1.5-1.2 1.5-2.5 1.5-2.5.5-2.5 1.5 1.2 1.5 2.5 1.5 2.5-.5 2.5-1.5',
 lock:'M6 11V8a6 6 0 1112 0v3M5 11h14v10H5z',alert:'M12 9v4M12 17h.01M10.3 3.9L2 18a2 2 0 001.7 3h16.6A2 2 0 0022 18L13.7 3.9a2 2 0 00-3.4 0',check:'M20 6L9 17l-5-5',shield:'M12 3l8 3v6c0 5-3.5 8-8 9-4.5-1-8-4-8-9V6z',
 search:'M21 21l-4.3-4.3M11 18a7 7 0 100-14 7 7 0 000 14',menu:'M4 6h16M4 12h16M4 18h16',close:'M18 6L6 18M6 6l12 12',plus:'M12 5v14M5 12h14',logout:'M9 21H5a2 2 0 01-2-2V5a2 2 0 012-2h4M16 17l5-5-5-5M21 12H9',
 sun:'M12 17a5 5 0 100-10 5 5 0 000 10M12 1v2M12 21v2M4.2 4.2l1.4 1.4M18.4 18.4l1.4 1.4M1 12h2M21 12h2M4.2 19.8l1.4-1.4M18.4 5.6l1.4-1.4',moon:'M21 12.8A9 9 0 1111.2 3a7 7 0 009.8 9.8',
 chev:'M6 9l6 6 6-6',right:'M9 6l6 6-6 6',up:'M7 17L17 7M8 7h9v9',more:'M12 12h.01M19 12h.01M5 12h.01',inbox:'M22 12h-6l-2 3h-4l-2-3H2M5.5 5h13l3.5 7v6a2 2 0 01-2 2H4a2 2 0 01-2-2v-6z',
 download:'M12 3v12M7 10l5 5 5-5M5 21h14',invoice:'M6 2h9l5 5v15H6zM14 2v6h6M9 13h6M9 17h6',org:'M9 3h6v5H9zM3 16h6v5H3zM15 16h6v5h-6zM12 8v4M6 16v-4h12v4',secure:'M12 3l8 3v6c0 5-3.5 8-8 9-4.5-1-8-4-8-9V6zM9.5 12l2 2 3-4',face:'M4 8V6a2 2 0 012-2h2M16 4h2a2 2 0 012 2v2M20 16v2a2 2 0 01-2 2h-2M8 20H6a2 2 0 01-2-2v-2M9 10v1M15 10v1M9.5 15a3.5 3.5 0 005 0',key:'M7 14a4 4 0 100-8 4 4 0 000 8zM10 10h11M18 10v4M14 10v3',access:'M12 12a4 4 0 100-8 4 4 0 000 8M4 21a8 8 0 0113-6M17 17l2 2 3-4',
 ticket:'M3 8a2 2 0 002-2h14a2 2 0 002 2v2a2 2 0 000 4v2a2 2 0 00-2 2H5a2 2 0 00-2-2v-2a2 2 0 000-4z'};
const ico=(n,c='')=>`<svg class="i ${c}" viewBox="0 0 24 24" aria-hidden="true"><path d="${P[n]||P.dashboard}"/></svg>`;

/* ---------- theme (light default; dark follows the OS until the user chooses) ---------- */
function themeNow(){let t=null;try{t=localStorage.getItem('sv-theme')}catch(e){}return t||(matchMedia('(prefers-color-scheme: dark)').matches?'dark':'light')}
function applyTheme(t){document.documentElement.setAttribute('data-theme',t);const m=document.querySelector('meta[name=theme-color]');if(m)m.content=getComputedStyle(document.documentElement).getPropertyValue('--sv-bg').trim()}
function toggleTheme(){const t=themeNow()==='dark'?'light':'dark';try{localStorage.setItem('sv-theme',t)}catch(e){}applyTheme(t);if(window.rerender)rerender()}
applyTheme(themeNow());

/* ---------- API ---------- */
async function api(path,opt={}){
  opt.credentials='same-origin';opt.headers={...(opt.headers||{})};
  if(opt.json!==undefined){opt.headers['Content-Type']='application/json';opt.body=JSON.stringify(opt.json);opt.method=opt.method||'POST'}
  const r=await fetch(path,opt);let j=null;try{j=await r.json()}catch(e){}
  if(r.status===428&&j&&j.detail==='face_reverify'&&!opt._retried){await faceReverify();return api(path,{...opt,_retried:true})}
  if(!r.ok){const m=(j&&(typeof j.detail==='string'?j.detail:JSON.stringify(j.detail)))||('Error '+r.status);const e=new Error(m);e.status=r.status;throw e}
  return j}
async function guard(fn){try{return await fn()}catch(e){toast(e.message,'danger');throw e}}

/* ---------- small components ---------- */
const KIND={success:['armed','known','active','paid','confirmed','ok','solved','online','connected','done','in_stock','owner'],warning:['mounting','service','uncertain','past_due','pending','high','watchlist','rma','sent'],
  danger:['locked','critical','suspended','revoked','overdue','fail','failed','unpaid'],info:['unclaimed','lead','trial','info','unknown','open','new','assigned','member','draft','low','normal'],neutral:['closed','void','retired','dismissed']};
const kindOf=s=>Object.keys(KIND).find(k=>KIND[k].includes(String(s)))||'neutral';
const badge=(s,label)=>`<span class="badge ${kindOf(s)}">${esc(label??String(s).replace(/_/g,' '))}</span>`;
const avatar=(n,c='')=>`<span class="avatar ${c}" aria-hidden="true">${esc(initials(n))}</span>`;
const batt=p=>p==null?'<span class="muted">–</span>':`<span class="batt ${p<20?'low':''}"><i style="right:${100-Math.max(5,p)}%"></i></span>${p}%`;
const usage=(l,a,b)=>`<div class="usage"><div class="row"><span>${esc(l)}</span><div class="sp"></div><span class="muted">${a} / ${b}</span></div><div class="bar ${a>=b?'bad':''}"><i style="width:${Math.min(100,100*a/Math.max(1,b))}%"></i></div></div>`;
const empty=({icon='inbox',title='Nothing here',text='',action=''}={})=>`<div class="empty"><div class="ring">${ico(icon)}</div><h2>${esc(title)}</h2>${text?`<div class="sec">${esc(text)}</div>`:''}${action}</div>`;
const kpi=({label,value,foot='',icon='dashboard',tone='',valueStyle=''})=>`<div class="card kpi c3"><div class="top"><span class="lbl">${esc(label)}</span><span class="tile ${tone}">${ico(icon)}</span></div><div class="val" ${valueStyle?`style="${valueStyle}"`:''}>${value}</div><div class="foot">${foot}</div></div>`;
const seg=(opts,cur,fn)=>`<div class="seg" role="tablist">${opts.map(([k,l,n])=>`<button role="tab" aria-selected="${k===cur}" class="${k===cur?'on':''}" onclick="${fn}('${k}')">${esc(l)}${n!=null?` <span class="n">${n}</span>`:''}</button>`).join('')}</div>`;
const pageHead=(html='')=>html?`<div class="pagehead"><div class="sp"></div>${html}</div>`:'';
const skeleton=()=>`<div class="grid"><div class="skel c3" style="height:120px"></div><div class="skel c3" style="height:120px"></div><div class="skel c3" style="height:120px"></div><div class="skel c3" style="height:120px"></div><div class="skel c12" style="height:260px"></div></div>`;
const field=(label,input,help='')=>`<div class="field"><label>${esc(label)}</label>${input}${help?`<div class="help">${esc(help)}</div>`:''}</div>`;
const thread=(msgs,mine)=>`<div class="thread">${msgs.map(m=>`<div class="msg ${m.author_type===mine?'me':''} ${m.internal?'internal':''}"><small>${esc(m.author)}${m.internal?' · internal note':''} · ${when(m.created)}</small>${esc(m.body)}</div>`).join('')}</div>`;

/* ---------- data table with toolbar and pagination ---------- */
const PG={};
function dtable({id,head,rows,size=10,toolbar='',emptyState,rowClick}){
  const n=rows.length,pages=Math.max(1,Math.ceil(n/size));let p=Math.min(PG[id]||1,pages);PG[id]=p;const slice=rows.slice((p-1)*size,p*size);
  const body=n?`<div class="tw"><table class="dt"><thead><tr>${head.map(h=>`<th class="${h.num?'num':''}">${esc(h.l)}</th>`).join('')}</tr></thead><tbody>${slice.map(r=>`<tr class="${r.click?'click':''}" ${r.click?`onclick="${r.click}" tabindex="0" onkeydown="if(event.key==='Enter')${r.click}"`:''}>${r.cells.map((c,i)=>`<td class="${head[i]?.num?'num':''}">${c}</td>`).join('')}</tr>`).join('')}</tbody></table></div>`
    :`<div>${emptyState?empty(emptyState):empty()}</div>`;
  const pager=n>size?`<div class="pager"><span>Showing ${(p-1)*size+1}–${Math.min(n,p*size)} of ${n}</span><div class="pgs"><button aria-label="Previous page" ${p<=1?'disabled':''} onclick="pgTo('${id}',${p-1})">‹</button>${Array.from({length:pages},(_,i)=>i+1).filter(i=>i===1||i===pages||Math.abs(i-p)<=1).map((i,k,a)=>`${k&&i-a[k-1]>1?'<span>…</span>':''}<button class="${i===p?'on':''}" onclick="pgTo('${id}',${i})">${i}</button>`).join('')}<button aria-label="Next page" ${p>=pages?'disabled':''} onclick="pgTo('${id}',${p+1})">›</button></div></div>`:(n?`<div class="pager"><span>Showing ${n} of ${n}</span></div>`:'');
  return `<div class="card flush">${toolbar?`<div class="toolbar">${toolbar}</div>`:''}${body}${pager}</div>`}
const pgTo=(id,n)=>{PG[id]=n;if(window.rerender)rerender()};

/* ---------- popover menu for row actions ---------- */
const MENUS={};let menuN=0;
const rowMenu=(items,label='More actions')=>{const id='m'+(++menuN);MENUS[id]=items;return `<button class="iconbtn flat" aria-label="${esc(label)}" aria-haspopup="menu" onclick="event.stopPropagation();openMenu(this,'${id}')">${ico('more')}</button>`};
function openMenu(btn,id){closePop();const r=btn.getBoundingClientRect();const d=document.createElement('div');d.className='pop';d.setAttribute('role','menu');
  d.innerHTML=MENUS[id].map((it,i)=>`<button role="menuitem" class="${it.danger?'bad':''}" data-i="${i}">${esc(it.label)}</button>`).join('');
  d.style.top=(r.bottom+scrollY+4)+'px';d.style.left=Math.max(8,Math.min(r.right+scrollX-190,innerWidth-200))+'px';document.body.appendChild(d);
  d.onclick=e=>{const b=e.target.closest('button');if(b){const it=MENUS[id][+b.dataset.i];closePop();it.run()}};setTimeout(()=>d.querySelector('button')?.focus(),0)}
function closePop(){document.querySelectorAll('.pop').forEach(x=>x.remove())}
document.addEventListener('click',e=>{if(!e.target.closest('.pop'))closePop()});

/* ---------- toast, modal (focus trap, Esc), dialogs ---------- */
function toast(msg,type='success'){let c=document.querySelector('.toasts');if(!c){c=document.createElement('div');c.className='toasts';c.setAttribute('role','status');document.body.appendChild(c)}
  const t=document.createElement('div');t.className='toast';t.innerHTML=`<span class="tile ${type==='danger'?'danger':'success'}" style="width:32px;height:32px">${ico(type==='danger'?'alert':'check','s18')}</span><span>${esc(msg)}</span><button class="iconbtn flat" aria-label="Dismiss">${ico('close','s16')}</button>`;
  t.querySelector('button').onclick=()=>t.remove();c.appendChild(t);if(type!=='danger')setTimeout(()=>t.remove(),5000)}
function modal(html,{wide=false,title=''}={}){const prev=document.activeElement;const bg=document.createElement('div');bg.className='modalbg';
  bg.innerHTML=`<div class="modal ${wide?'wide':''}" role="dialog" aria-modal="true" aria-label="${esc(title)}">${html}</div>`;document.body.appendChild(bg);
  const close=()=>{bg.remove();document.removeEventListener('keydown',key);prev?.focus?.()};bg.close=close;
  function key(e){if(e.key==='Escape'){close();return}if(e.key==='Tab'){const f=[...bg.querySelectorAll('button,input,select,textarea,a[href]')].filter(x=>!x.disabled&&x.offsetParent!==null);if(!f.length)return;
    const a=f[0],z=f[f.length-1];if(e.shiftKey&&document.activeElement===a){e.preventDefault();z.focus()}else if(!e.shiftKey&&document.activeElement===z){e.preventDefault();a.focus()}}}
  document.addEventListener('keydown',key);bg.onmousedown=e=>{if(e.target===bg)close()};return bg}
const closeModal=el=>el.closest('.modalbg').close();
const mhead=t=>`<div class="modal-h"><h2>${esc(t)}</h2><button class="iconbtn flat" aria-label="Close" onclick="closeModal(this)">${ico('close')}</button></div>`;
function ask({title,fields=[],submit='Save',onSubmit,note,danger,wide}){
  const f=fields.map(x=>{const v=x.value??'';const w='';
    const input=x.type==='select'?`<select id="f_${x.id}">${x.options.map(o=>{const [k,l]=Array.isArray(o)?o:[o,o];return `<option value="${esc(k)}" ${String(k)===String(v)?'selected':''}>${esc(l)}</option>`}).join('')}</select>`
     :x.type==='textarea'?`<textarea id="f_${x.id}" rows="${x.rows||3}" placeholder="${esc(x.placeholder||'')}">${esc(v)}</textarea>`
     :x.type==='checkbox'?`<label class="check"><input type="checkbox" id="f_${x.id}" ${v?'checked':''}> ${esc(x.label)}</label>`
     :`<input id="f_${x.id}" type="${x.type||'text'}" value="${esc(v)}" placeholder="${esc(x.placeholder||'')}">`;
    return x.type==='checkbox'?`<div class="field">${input}${x.hint?`<div class="help">${esc(x.hint)}</div>`:''}</div>`:field(x.label,input,x.hint)}).join('');
  const m=modal(`${mhead(title)}${note?`<p class="sec" style="margin-bottom:var(--sv-space-4)">${note}</p>`:''}${f}<div class="err" id="ask_err" role="alert"></div><div class="modal-f"><button class="btn" id="ask_x">Cancel</button><button class="btn ${danger?'danger':'primary'}" id="ask_go">${esc(submit)}</button></div>`,{wide,title});
  m.querySelector('#ask_x').onclick=()=>m.close();
  const go=async()=>{const vals={};for(const x of fields){const el=m.querySelector('#f_'+x.id);vals[x.id]=x.type==='checkbox'?el.checked:el.value}
    try{await onSubmit(vals);m.close()}catch(e){m.querySelector('#ask_err').textContent=e.message}};
  m.querySelector('#ask_go').onclick=go;m.addEventListener('keydown',e=>{if(e.key==='Enter'&&e.target.matches('input:not([type=checkbox])'))go()});
  m.querySelector('input,textarea,select')?.focus();return m}
const shown=(title,html)=>modal(`${mhead(title)}${html}<div class="modal-f"><button class="btn primary" onclick="closeModal(this)">Done</button></div>`,{title});
const sure=(title,text,fn,{label='Confirm',danger=true}={})=>ask({title,note:text,submit:label,danger,onSubmit:async()=>fn()});

/* ---------- charts (token colors only) ---------- */
const TIP=document.createElement('div');TIP.className='ctip';TIP.style.display='none';document.addEventListener('DOMContentLoaded',()=>document.body.appendChild(TIP));
document.addEventListener('mouseover',e=>{const t=e.target.closest('[data-tip]');if(!t||t.classList.contains('nav')){TIP.style.display='none';return}TIP.textContent=t.dataset.tip;TIP.style.display='block'});
document.addEventListener('mousemove',e=>{if(TIP.style.display==='block'){TIP.style.left=(e.clientX+14)+'px';TIP.style.top=(e.clientY+14)+'px'}});
const SER=['c1','c2','c3f','c4f','c5f','c6f'],LEG=['--sv-chart-1','--sv-chart-2','--sv-chart-3','--sv-chart-4','--sv-chart-5','--sv-chart-6'];
const short=n=>n>=1e6?(n/1e6).toFixed(1).replace('.0','')+'M':n>=1e3?(n/1e3).toFixed(1).replace('.0','')+'k':String(n);
const topRound=(x,y,w,h,r)=>{r=Math.min(r,h,w/2);return `M${x},${y+h}V${y+r}Q${x},${y} ${x+r},${y}H${x+w-r}Q${x+w},${y} ${x+w},${y+r}V${y+h}Z`};
function stackedBars(days,keys,labels,idx){const W=640,H=200,L=34,B=24,T=10,plotH=H-B-T,max=Math.max(1,...days.map(d=>keys.reduce((s,k)=>s+d[k],0)));
  const steps=[0,.5,1].map(f=>Math.round(max*f));const bw=(W-L)/days.length,w=Math.min(32,bw*.6);
  const grid=steps.map(v=>{const y=T+plotH-plotH*v/max;return `<line class="grid-l" x1="${L}" x2="${W}" y1="${y}" y2="${y}"/><text x="${L-8}" y="${y+4}" text-anchor="end">${short(v)}</text>`}).join('');
  const bars=days.map((d,i)=>{let y=T+plotH;const x=L+i*bw+(bw-w)/2;const present=keys.filter(k=>d[k]>0);
    const segs=present.map((k,j)=>{const h=plotH*d[k]/max;y-=h;const top=j===present.length-1;const j2=keys.indexOf(k);
      return `<path class="${SER[idx?idx[j2]:j2]}" d="${top?topRound(x,y,w,h,6):`M${x},${y}h${w}v${h}h${-w}Z`}" data-tip="${d.date}: ${d[k]} ${labels[j2]}"/>`}).join('');
    return segs+(i%Math.ceil(days.length/7)===0?`<text x="${x+w/2}" y="${H-6}" text-anchor="middle">${d.date.slice(5)}</text>`:'')}).join('');
  return `<svg class="chart" viewBox="0 0 ${W} ${H}" role="img" aria-label="Visitors per day, ${days.reduce((s,d)=>s+keys.reduce((a,k)=>a+d[k],0),0)} in total">${grid}${bars}</svg>`}
const legend=(labels,idx)=>`<div class="legend">${labels.map((l,i)=>`<span><i style="background:var(${LEG[idx?idx[i]:i]})"></i>${esc(l)}</span>`).join('')}</div>`;
function hourBars(h){const max=Math.max(1,...h);return `<svg class="chart" viewBox="0 0 480 110" role="img" aria-label="Visitors by hour of day">${[0,.5,1].map(f=>{const y=10+70-70*f;return `<line class="grid-l" x1="0" x2="480" y1="${y}" y2="${y}"/>`}).join('')}${h.map((v,i)=>`<path class="c1" d="${topRound(i*20+3,80-70*v/max,14,Math.max(1,70*v/max),6)}" opacity="${v?1:.25}" data-tip="${i}:00 · ${v} visitors"/>${i%3===0?`<text x="${i*20+10}" y="100" text-anchor="middle">${i}</text>`:''}`).join('')}</svg>`}
function donut(parts,centerLabel){const total=parts.reduce((s,p)=>s+p.v,0)||1;let a=-Math.PI/2;const R=58,r=40;
  const arcs=parts.filter(p=>p.v>0).map(p=>{const f=p.v/total,b=a+f*2*Math.PI;const lg=f>.5?1:0;const pt=(ang,rad)=>[75+rad*Math.cos(ang),75+rad*Math.sin(ang)];
    const [x1,y1]=pt(a,R),[x2,y2]=pt(b,R),[x3,y3]=pt(b-.0001,r),[x4,y4]=pt(a,r);a=b;
    return f>=.9999?`<circle cx="75" cy="75" r="${(R+r)/2}" fill="none" stroke-width="${R-r}" style="stroke:var(${p.var})" data-tip="${esc(p.l)}: ${p.v}"/>`:`<path class="${p.c}" d="M${x1},${y1}A${R},${R} 0 ${lg} 1 ${x2},${y2}L${x3},${y3}A${r},${r} 0 ${lg} 0 ${x4},${y4}Z" data-tip="${esc(p.l)}: ${p.v} (${Math.round(f*100)}%)"/>`}).join('');
  return `<div class="donut"><svg viewBox="0 0 150 150" role="img" aria-label="${esc(centerLabel)}: ${total}">${arcs}<text class="ctr" x="75" y="76" text-anchor="middle">${total}</text><text class="cap" x="75" y="94" text-anchor="middle">${esc(centerLabel)}</text></svg>
  <div class="stack">${parts.map(p=>`<div class="row nowrap"><span class="dot" style="background:var(${p.var})"></span><span class="sec">${esc(p.l)}</span><b style="margin-left:auto;padding-left:16px">${p.v}</b></div>`).join('')}</div></div>`}

/* ---------- routing ---------- */
const route=()=>{const h=(location.hash||'').replace(/^#\/?/,'').split('/');return {page:h[0]||'',id:h[1]||'',sub:h[2]||''}};
const nav=h=>{location.hash='#/'+h};

/* ---------- app shell: collapsible sidebar, top bar, drawer ---------- */
function mountShell({root,brandSub,groups,user,onNav,search}){
  let pref=null;try{pref=localStorage.getItem('sv-nav')}catch(e){}
  const collapsed=pref?pref==='1':innerWidth<1280;
  root.innerHTML=`<div class="shell ${collapsed?'collapsed':''}" id="shell"><nav class="sidebar" aria-label="Main"><div class="logo"><span class="mark">${ico('sun')}</span><div><b>Solavis</b><small>${esc(brandSub||'')}</small></div></div><div id="nav"></div>
   <div class="userrow" id="userrow" tabindex="0" role="button" aria-haspopup="menu" aria-label="Account menu" style="margin-top:auto">${avatar(user.name||user.email)}<div><b>${esc(user.name||user.email.split('@')[0])}</b><small>${esc(user.roleLabel)}</small></div></div>
   <a class="nav logoutrow" data-tip="Log out" tabindex="0" role="button" onclick="logout()" onkeydown="if(event.key==='Enter')logout()">${ico('logout')}<span class="lbl">Log out</span></a></nav>
   <button class="sbtoggle" id="sbtoggle" aria-label="Collapse or expand the sidebar" aria-expanded="${!collapsed}">${ico('chev')}</button>
   <div class="scrim" id="scrim"></div><div class="main"><header class="topbar" id="topbar"><button class="iconbtn menubtn" id="menubtn" aria-label="Open menu">${ico('menu')}</button><div class="ttl"><h1 id="ttl"></h1><div class="sub" id="sub"></div></div><div class="sp"></div>
   ${search?`<label class="search">${ico('search','s18')}<input id="gs" placeholder="${esc(search.placeholder)}" aria-label="${esc(search.placeholder)}"><kbd>⌘K</kbd></label>`:''}
   <button class="iconbtn" id="themebtn" aria-label="Toggle dark mode">${ico(themeNow()==='dark'?'sun':'moon')}</button><button class="iconbtn" id="bellbtn" aria-label="Alerts">${ico('alerts')}<span class="dotbad hide" id="belldot"></span></button>${avatar(user.name||user.email,'s40')}</header>
   <main class="content" id="pg" tabindex="-1"></main></div></div>`;
  const sh=$('shell');$('menubtn').onclick=()=>sh.classList.add('open');$('scrim').onclick=()=>sh.classList.remove('open');
  $('sbtoggle').onclick=()=>{const c=sh.classList.toggle('collapsed');$('sbtoggle').setAttribute('aria-expanded',String(!c));try{localStorage.setItem('sv-nav',c?'1':'0')}catch(e){}};
  $('themebtn').onclick=()=>{toggleTheme();$('themebtn').innerHTML=ico(themeNow()==='dark'?'sun':'moon')};
  $('bellbtn').onclick=()=>onNav.bell();
  addEventListener('scroll',()=>$('topbar').classList.toggle('scrolled',scrollY>4),{passive:true});
  $('userrow').onclick=e=>{e.stopPropagation();closePop();const r=$('userrow').getBoundingClientRect();const d=document.createElement('div');d.className='pop';d.innerHTML=`<button data-a="theme">${ico('moon','s18')} Toggle dark mode</button><button data-a="out" class="bad">${ico('logout','s18')} Log out</button>`;
    d.style.left=r.left+'px';d.style.top=(r.top+scrollY-92)+'px';document.body.appendChild(d);d.onclick=ev=>{const b=ev.target.closest('button');if(!b)return;closePop();b.dataset.a==='out'?logout():($('themebtn').click())}};
  if(search){addEventListener('keydown',e=>{if((e.metaKey||e.ctrlKey)&&e.key.toLowerCase()==='k'){e.preventDefault();$('gs').focus()}});$('gs').onkeydown=e=>{if(e.key==='Enter')search.run(e.target.value)}}
  return {renderNav(page,items){$('nav').innerHTML=groups(items).map(g=>`${g.label?`<div class="navgroup">${esc(g.label)}</div>`:''}${g.items.map(([k,l,i,badge])=>`<a class="nav ${k===page?'on':''}" data-tip="${esc(l)}" tabindex="0" role="link" aria-current="${k===page?'page':'false'}" onclick="nav('${k}');document.getElementById('shell').classList.remove('open')" onkeydown="if(event.key==='Enter')this.click()">${ico(i)}<span class="lbl">${esc(l)}</span>${badge?`<span class="cnt">${badge}</span><span class="badgedot"></span>`:''}</a>`).join('')}`).join('')},
    setTitle(t,s){$('ttl').textContent=t;$('sub').textContent=s||'';document.title=t+' · Solavis'}}}

/* ---------- live face capture (webcam) for the President ---------- */
function faceCapture({title,steps,done}){
  return new Promise((resolve,reject)=>{let stream=null,i=0;const frames=[];
    const m=modal(`${mhead(title)}<div class="faceview"><video id="fv" autoplay playsinline muted></video><div class="ovl"><div class="oval"></div></div></div><div class="steps" id="fst">${steps.map(()=>'<i></i>').join('')}</div>
      <div id="fmsg" style="font-weight:600">${esc(steps[0])}</div><div class="caption" id="fhint">Keep your face inside the oval, good light, no hat or mask.</div><div class="err" id="ferr" role="alert"></div>
      <div class="modal-f"><button class="btn" id="fx">Cancel</button><button class="btn primary" id="fgo" disabled>Capture</button></div>`,{title});
    const stop=()=>{stream?.getTracks().forEach(t=>t.stop())};const orig=m.close;m.close=()=>{stop();orig()};
    m.querySelector('#fx').onclick=()=>{m.close();reject(new Error('Cancelled'))};
    const upd=()=>{[...m.querySelectorAll('#fst i')].forEach((e,k)=>e.classList.toggle('on',k<=i));$('fmsg').textContent=steps[i];$('fgo').textContent=i===steps.length-1?'Capture and finish':'Capture'};upd();
    navigator.mediaDevices?.getUserMedia?.({video:{width:640,height:480,facingMode:'user'}}).then(s=>{stream=s;const v=$('fv');v.srcObject=s;v.onloadedmetadata=()=>{$('fgo').disabled=false}}).catch(()=>{$('ferr').textContent='The camera could not be opened. Allow camera access for this site in your browser, then try again.'});
    m.querySelector('#fgo').onclick=async()=>{const v=$('fv');const cv=document.createElement('canvas');cv.width=v.videoWidth;cv.height=v.videoHeight;cv.getContext('2d').drawImage(v,0,0);
      const blob=await new Promise(r=>cv.toBlob(r,'image/jpeg',.92));frames.push(blob);i++;
      if(i<steps.length){upd();return}
      $('fgo').disabled=true;$('fmsg').textContent='Checking…';try{await done(frames);m.close();resolve(true)}catch(e){$('ferr').textContent=e.message;frames.length=0;i=0;upd();$('fgo').disabled=false}}})}
const faceForm=(frames,extra={})=>{const f=new FormData();frames.forEach((b,k)=>f.append('images',b,`f${k}.jpg`));Object.entries(extra).forEach(([k,v])=>f.append(k,v));return f};
const faceVerify=()=>faceCapture({title:'Confirm it is you',steps:['Look straight at the camera','Turn your head slightly to the left or right'],done:async fr=>{await api('/api/auth/face/verify',{method:'POST',body:faceForm(fr)})}});
const faceEnroll=(code)=>faceCapture({title:'Enrol your face',steps:['Look straight at the camera','Turn your head slightly to the left','Turn your head slightly to the right'],done:async fr=>{await api('/api/auth/face/enroll',{method:'POST',body:faceForm(fr,code?{code}:{})})}});
let _reverify=null;
function faceReverify(){if(!_reverify){_reverify=new Promise((res,rej)=>{const m=modal(`${mhead('Face check required')}<p class="sec">This action needs a fresh face check.</p><div class="modal-f"><button class="btn" id="rv_x">Cancel</button><button class="btn primary" id="rv_go">${ico('face','s18')} Start camera</button></div>`,{title:'Face check required'});
  m.querySelector('#rv_x').onclick=()=>{m.close();rej(new Error('Face check cancelled'))};m.querySelector('#rv_go').onclick=async()=>{m.close();try{await faceVerify();res()}catch(e){rej(e)}}}).finally(()=>{_reverify=null})}return _reverify}

/* ---------- login + forced password change ---------- */
function mountAuth(root,{title,role,onReady}){
  root.innerHTML=`<div class="loginwrap"><div class="login"><div class="logo"><span class="mark">${ico('sun')}</span><b>Solavis</b></div><div class="card"><h2 style="font-size:18px;line-height:28px;margin-bottom:4px">Sign in</h2><p class="sec" style="margin-bottom:var(--sv-space-5)">${esc(title)}</p>
  ${field('Email','<input id="a_em" type="email" autocomplete="username">')}${field('Password','<input id="a_pw" type="password" autocomplete="current-password">')}<div class="err" id="a_err" role="alert"></div><button class="btn primary" id="a_go" style="width:100%">Sign in</button></div></div></div>`;
  const go=async()=>{$('a_err').textContent='';try{const u=await api('/api/auth/login',{json:{email:$('a_em').value,password:$('a_pw').value}});await after(u)}catch(e){$('a_err').textContent=e.message}};
  $('a_go').onclick=go;$('a_pw').onkeydown=e=>{if(e.key==='Enter')go()};$('a_em').focus();
  async function after(u){
    if(role&&u.role!==role&&!(role==='customer'&&u.role!=='staff')){await api('/api/auth/logout',{method:'POST'});throw new Error(role==='staff'?'This console is for Solavis staff. Use the customer app.':'Staff accounts sign in at /admin')}
    if(u.must_change_pw)return forceChange(u);
    if(u.face_pending||(u.face&&u.face.required))return faceStep(u);
    onReady(u)}
  async function faceStep(u){const st=await api('/api/auth/face/status');
    root.innerHTML=`<div class="loginwrap"><div class="login"><div class="logo"><span class="mark">${ico('sun')}</span><b>Solavis</b></div><div class="card"><div class="row nowrap" style="margin-bottom:var(--sv-space-3)"><span class="tile">${ico('face')}</span><h2 style="font-size:18px;line-height:28px">Face verification</h2></div>
     <p class="sec" style="margin-bottom:var(--sv-space-4)">${st.enrolled?'Your account requires a live face check in addition to your password. Every attempt is recorded.':'First sign-in: enrol your face. Enter the one-time enrollment code from your administrator.'}</p>
     ${st.enrolled?'':field('Enrollment code','<input id="fc" autocomplete="off" placeholder="XXXX-XXXX-XXXX">')}<div class="err" id="f_err" role="alert"></div><button class="btn primary" id="f_go" style="width:100%">${ico('face','s18')} Start camera</button>
     <button class="btn ghost" id="f_out" style="width:100%;margin-top:var(--sv-space-2)">Cancel and sign out</button></div></div></div>`;
    $('f_out').onclick=()=>logout();
    $('f_go').onclick=async()=>{$('f_err').textContent='';try{if(st.enrolled)await faceVerify();else{const c=$('fc').value.trim();if(!c){$('f_err').textContent='Enter the enrollment code';return}await faceEnroll(c)}
      const me=await api('/api/auth/me');onReady(me)}catch(e){if(e.message!=='Cancelled')$('f_err').textContent=e.message}}}
  function forceChange(u){root.innerHTML=`<div class="loginwrap"><div class="login"><div class="logo"><span class="mark">${ico('sun')}</span><b>Solavis</b></div><div class="card"><h2 style="font-size:18px;line-height:28px;margin-bottom:4px">Choose a new password</h2><p class="sec" style="margin-bottom:var(--sv-space-5)">Replace the temporary password to continue.</p>
    ${field('Temporary password','<input id="c0" type="password">')}${field('New password','<input id="c1" type="password">','8+ characters with a letter and a number')}<div class="err" id="c_err" role="alert"></div><button class="btn primary" id="c_go" style="width:100%">Save password</button></div></div></div>`;
    $('c_go').onclick=async()=>{try{await api('/api/auth/password',{json:{current:$('c0').value,new:$('c1').value}});u.must_change_pw=false;after(u)}catch(e){$('c_err').textContent=e.message}}}
  api('/api/auth/me').then(u=>after(u).catch(()=>{})).catch(()=>{})}
async function logout(){await api('/api/auth/logout',{method:'POST'}).catch(()=>{});location.reload()}
