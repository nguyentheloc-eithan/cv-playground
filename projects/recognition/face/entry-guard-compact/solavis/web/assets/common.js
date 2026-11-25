const $=i=>document.getElementById(i);
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const pill=t=>`<span class="pill ${esc(t)}">${esc(String(t).replace('_',' '))}</span>`;
const ago=t=>{if(!t)return 'never';const s=Date.now()/1000-t;return s<60?Math.round(s)+' s ago':s<3600?Math.round(s/60)+' min ago':s<86400?Math.round(s/3600)+' h ago':Math.round(s/86400)+' d ago'};
const when=t=>t?new Date(t*1000).toLocaleString():'';
async function api(path,opt={}){
  opt.credentials='same-origin';opt.headers={...(opt.headers||{})};
  if(opt.json!==undefined){opt.headers['Content-Type']='application/json';opt.body=JSON.stringify(opt.json);opt.method=opt.method||'POST'}
  const r=await fetch(path,opt);let j=null;try{j=await r.json()}catch(e){}
  if(!r.ok){const m=(j&&(typeof j.detail==='string'?j.detail:JSON.stringify(j.detail)))||('Error '+r.status);const e=new Error(m);e.status=r.status;throw e}
  return j}
function toast(msg,ms=3500){const t=document.createElement('div');t.className='toast';t.textContent=msg;document.body.appendChild(t);setTimeout(()=>t.remove(),ms)}
function modal(html){const m=document.createElement('div');m.className='modal';m.innerHTML=`<div class="card">${html}</div>`;m.onclick=e=>{if(e.target===m)m.remove()};document.body.appendChild(m);return m}
async function guard(fn){try{return await fn()}catch(e){toast(e.message);throw e}}
// Shared login + forced password change. onReady(user) runs once the user is fully signed in.
function mountAuth(root,{title,hint,role,onReady}){
  root.innerHTML=`<div class="login"><div class="brand">Sol<span>avis</span></div><p class="mut" style="margin:2px 0 16px">${esc(title)}</p>
  <div class="card"><label>Email</label><input id="a_em" type="email" autocomplete="username" style="width:100%">
  <label>Password</label><input id="a_pw" type="password" autocomplete="current-password" style="width:100%">
  <div class="row"><button class="p" id="a_go" style="width:100%">Log in</button></div><div class="err" id="a_err"></div></div>${hint?`<p class="mut">${hint}</p>`:''}</div>`;
  const go=async()=>{$('a_err').textContent='';try{const u=await api('/api/auth/login',{json:{email:$('a_em').value,password:$('a_pw').value}});await after(u)}catch(e){$('a_err').textContent=e.message}};
  $('a_go').onclick=go;$('a_pw').onkeydown=e=>{if(e.key==='Enter')go()};
  async function after(u){
    if(role&&u.role!==role&&!(role==='customer'&&u.role!=='staff')){await api('/api/auth/logout',{method:'POST'});throw new Error(role==='staff'?'This console is for Solavis staff. Use the customer app.':'Staff accounts sign in at /admin')}
    if(u.must_change_pw)return forceChange(u);
    onReady(u)}
  function forceChange(u){root.innerHTML=`<div class="login"><div class="brand">Sol<span>avis</span></div><p class="mut">Choose your own password to continue.</p><div class="card">
    <label>Current (temporary) password</label><input id="c0" type="password" style="width:100%"><label>New password (8+ characters, letters and a number)</label><input id="c1" type="password" style="width:100%">
    <div class="row"><button class="p" id="c_go" style="width:100%">Save password</button></div><div class="err" id="c_err"></div></div></div>`;
    $('c_go').onclick=async()=>{try{await api('/api/auth/password',{json:{current:$('c0').value,new:$('c1').value}});u.must_change_pw=false;onReady(u)}catch(e){$('c_err').textContent=e.message}}}
  api('/api/auth/me').then(u=>after(u).catch(()=>{})).catch(()=>{})}
async function logout(){await api('/api/auth/logout',{method:'POST'}).catch(()=>{});location.reload()}

/* ===== v2 helpers ===== */
const P={home:'M3 11l9-8 9 8v9a1 1 0 01-1 1h-5v-6H9v6H4a1 1 0 01-1-1z',device:'M4 7h16v10H4zM9 17v3h6v-3M12 11m-2 0a2 2 0 104 0 2 2 0 10-4 0',bell:'M6 8a6 6 0 1112 0c0 7 3 8 3 8H3s3-1 3-8M10 20a2 2 0 004 0',
 users:'M16 11a4 4 0 10-8 0M4 21v-1a6 6 0 0112 0v1M17 7a3 3 0 010 6M21 21v-1a5 5 0 00-3-4.6',person:'M12 12a4 4 0 100-8 4 4 0 000 8M4 21a8 8 0 0116 0',chart:'M4 20V10M10 20V4M16 20v-8M22 20H2',
 list:'M8 6h13M8 12h13M8 18h13M3 6h.01M3 12h.01M3 18h.01',card:'M2 6h20v12H2zM2 10h20',help:'M12 17h.01M9.5 9a2.5 2.5 0 115 0c0 2-2.5 2-2.5 4M12 22a10 10 0 100-20 10 10 0 000 20',
 gear:'M12 15a3 3 0 100-6 3 3 0 000 6M19 12a7 7 0 00-.1-1.2l2-1.5-2-3.4-2.3.9a7 7 0 00-2-1.2L14.2 3h-4l-.4 2.6a7 7 0 00-2 1.2l-2.3-.9-2 3.4 2 1.5A7 7 0 005 12c0 .4 0 .8.1 1.2l-2 1.5 2 3.4 2.3-.9a7 7 0 002 1.2l.4 2.6h4l.4-2.6a7 7 0 002-1.2l2.3.9 2-3.4-2-1.5c.1-.4.1-.8.1-1.2',
 building:'M4 21V3h10v18M14 9h6v12M8 7h2M8 11h2M8 15h2M17 13h.01M17 17h.01M2 21h20',box:'M21 8l-9-5-9 5v8l9 5 9-5zM3 8l9 5 9-5M12 13v8',check:'M5 12l5 5L20 7',shield:'M12 3l8 3v6c0 5-3.5 8-8 9-4.5-1-8-4-8-9V6z',
 search:'M21 21l-4.3-4.3M11 18a7 7 0 100-14 7 7 0 000 14',ticket:'M3 8a2 2 0 002-2h14a2 2 0 002 2v2a2 2 0 000 4v2a2 2 0 00-2 2H5a2 2 0 00-2-2v-2a2 2 0 000-4z',
 coin:'M12 21a9 9 0 100-18 9 9 0 000 18M12 7v10M9.5 9.5c0-1 1.2-1.5 2.5-1.5s2.5.5 2.5 1.5-1.2 1.5-2.5 1.5-2.5.5-2.5 1.5 1.2 1.5 2.5 1.5 2.5-.5 2.5-1.5',
 task:'M9 11l3 3 8-8M20 12v7a2 2 0 01-2 2H6a2 2 0 01-2-2V7a2 2 0 012-2h9',lock:'M6 11V8a6 6 0 1112 0v3M5 11h14v10H5z',alert:'M12 9v4M12 17h.01M10.3 3.9L2 18a2 2 0 001.7 3h16.6A2 2 0 0022 18L13.7 3.9a2 2 0 00-3.4 0'};
const ico=n=>`<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="${P[n]||P.home}"/></svg>`;
const vnd=n=>new Intl.NumberFormat('vi-VN').format(n||0)+' ₫';
const dshort=t=>t?new Date(t*1000).toLocaleDateString(undefined,{day:'2-digit',month:'short',year:'numeric'}):'–';
const empty=(m)=>`<div class="empty">${esc(m)}</div>`;
const batt=p=>p==null?'<span class="mut">–</span>':`<span class="batt ${p<20?'low':''}"><i style="right:${100-Math.max(5,p)}%"></i></span>${p}%`;
const chips=(opts,cur,fn)=>`<div class="chips">${opts.map(([k,l,n])=>`<button class="${k===cur?'on':''}" onclick="${fn}('${k}')">${esc(l)}${n!=null?`<span class="n">${n}</span>`:''}</button>`).join('')}</div>`;
const route=()=>{const h=(location.hash||'').replace(/^#\/?/,'').split('/');return {page:h[0]||'',id:h[1]||'',sub:h[2]||''}};
function nav(h){location.hash='#/'+h}
// A small form dialog: ask({title, fields:[{id,label,type,value,options,placeholder,rows,hint}], submit, onSubmit(values)->promise, note})
function ask({title,fields=[],submit='Save',onSubmit,note,danger}){
  const f=fields.map(x=>{const v=x.value??'';const w='style="width:100%"';
    const input=x.type==='select'?`<select id="f_${x.id}" ${w}>${x.options.map(o=>{const [k,l]=Array.isArray(o)?o:[o,o];return `<option value="${esc(k)}" ${String(k)===String(v)?'selected':''}>${esc(l)}</option>`}).join('')}</select>`
     :x.type==='textarea'?`<textarea id="f_${x.id}" rows="${x.rows||3}" ${w} placeholder="${esc(x.placeholder||'')}">${esc(v)}</textarea>`
     :x.type==='checkbox'?`<label style="display:flex;gap:8px;align-items:center;color:var(--ink)"><input type="checkbox" id="f_${x.id}" ${v?'checked':''}> ${esc(x.label)}</label>`
     :`<input id="f_${x.id}" type="${x.type||'text'}" value="${esc(v)}" placeholder="${esc(x.placeholder||'')}" ${w}>`;
    return (x.type==='checkbox'?'':`<label>${esc(x.label)}</label>`)+input+(x.hint?`<div class="mut" style="font-size:12px">${esc(x.hint)}</div>`:'')}).join('');
  const m=modal(`<h2>${esc(title)}</h2>${note?`<p class="mut" style="margin-top:0">${note}</p>`:''}${f}<div class="err" id="ask_err"></div><div class="row"><button class="${danger?'d':'p'}" id="ask_go">${esc(submit)}</button><button id="ask_x">Cancel</button></div>`);
  m.querySelector('#ask_x').onclick=()=>m.remove();
  m.querySelector('#ask_go').onclick=async()=>{const vals={};for(const x of fields){const el=m.querySelector('#f_'+x.id);vals[x.id]=x.type==='checkbox'?el.checked:el.value}
    try{await onSubmit(vals);m.remove()}catch(e){m.querySelector('#ask_err').textContent=e.message}};
  const first=m.querySelector('input,textarea,select');if(first)first.focus();return m}
function shown(title,html){const m=modal(`<h2>${esc(title)}</h2>${html}<div class="row"><button class="p" onclick="this.closest('.modal').remove()">Done</button></div>`);return m}
const thread=(msgs,mine)=>`<div class="thread">${msgs.map(m=>`<div class="msg ${m.author_type===mine?'me':''} ${m.internal?'internal':''}"><small>${esc(m.author)}${m.internal?' · internal note':''} · ${when(m.created)}</small>${esc(m.body)}</div>`).join('')}</div>`;
function stackedBars(days,keys,colors){const W=640,H=170,pad=22,max=Math.max(1,...days.map(d=>keys.reduce((s,k)=>s+d[k],0)));const bw=(W-pad)/days.length;
  const bars=days.map((d,i)=>{let y=H-pad;const x=pad+i*bw;return keys.map((k,j)=>{const h=(H-pad-8)*d[k]/max;y-=h;return h>0?`<rect x="${x+bw*.15}" y="${y}" width="${bw*.7}" height="${h}" rx="2" fill="${colors[j]}"><title>${d.date}: ${d[k]} ${k}</title></rect>`:''}).join('')+(i%Math.ceil(days.length/7)===0?`<text x="${x+bw/2}" y="${H-6}" text-anchor="middle">${d.date.slice(5)}</text>`:'')}).join('');
  return `<svg class="chart" viewBox="0 0 ${W} ${H}"><text x="0" y="12">${max}</text><line x1="${pad}" x2="${W}" y1="${H-pad}" y2="${H-pad}" stroke="currentColor" opacity=".15"/>${bars}</svg>`}
function hourBars(h){const max=Math.max(1,...h);return `<svg class="chart" viewBox="0 0 480 90">${h.map((v,i)=>`<rect x="${i*20+2}" y="${70-60*v/max}" width="16" height="${Math.max(1,60*v/max)}" rx="2" fill="var(--acc)" opacity="${v?1:.2}"><title>${i}:00 · ${v}</title></rect>${i%3===0?`<text x="${i*20+10}" y="85" text-anchor="middle">${i}</text>`:''}`).join('')}</svg>`}
