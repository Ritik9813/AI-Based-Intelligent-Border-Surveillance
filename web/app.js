const $=(s,r=document)=>r.querySelector(s),$$=(s,r=document)=>[...r.querySelectorAll(s)];
const LV=['Low','Medium','High','Critical'],LC=['#19c37d','#f4b400','#ff7a1a','#e5383b'];
const TYPES=['Unauthorized Crossing','Group Movement','Vehicle Intrusion','Drone Detection','Loitering','Fence Breach','Abandoned Object'];
const TC=['#ef4444','#f97316','#eab308','#a855f7','#3b82f6','#ec4899','#22c55e'];
const ICON={'Unauthorized Crossing':'🚶','Group Movement':'👥','Vehicle Intrusion':'🚗','Drone Detection':'🛸','Loitering':'⏱','Fence Breach':'⚠️','Abandoned Object':'🎒','Raw Sensor Alarm':'📡'};
const CAMP={'CAM-01':[.16,.22],'CAM-02':[.30,.44],'CAM-03':[.58,.20],'CAM-04':[.80,.56],'CAM-05':[.93,.80]};
const BORDER=[[0,.3],[.12,.3],[.22,.34],[.30,.46],[.42,.40],[.52,.33],[.62,.24],[.72,.28],[.80,.40],[.86,.54],[.90,.66],[.95,.82],[1,.9]];
const RIVER=[[.60,0],[.70,.12],[.78,.28],[.86,.45],[.92,.62],[.97,.80],[1,.95]];
const DEMO=['Person crossing','Group','Loitering','Vehicle','Drone','Abandoned object','Fence cut','Animal (decoy)','Wind (decoy)','Patrol (decoy)'];
const esc=s=>String(s).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
let S=null,page='dashboard',zoom=1,modalId=null,me=null,lastMax=0,sound=localStorage.getItem('bw_sound')!=='0',chat=[{b:1,t:'I am your AI Security Agent. I can help you with:\n• Analyze detected events\n• Explain risk levels\n• Summarize suspicious activities\n• Generate reports\n• Answer security-related questions'}];
async function req(u,o){const r=await fetch(u,o);if(r.status==401){showLogin();throw new Error('login')}return r.json()}
const post=(u,o)=>req(u,{method:'POST',body:JSON.stringify(o)});const cmd=o=>post('/api/cmd',o);
function toast(m,ok){const t=$('#toast');t.textContent=m;t.style.background=ok?'#0f6b45':'#e5383b';t.style.display='block';clearTimeout(t._h);t._h=setTimeout(()=>t.style.display='none',3500)}
function beep(){if(!sound)return;try{const c=new (window.AudioContext||window.webkitAudioContext)(),o=c.createOscillator(),g=c.createGain();o.type='square';o.frequency.value=880;g.gain.value=.06;o.connect(g);g.connect(c.destination);o.start();[0,.18,.36].forEach((d,i)=>o.frequency.setValueAtTime(i%2?660:880,c.currentTime+d));o.stop(c.currentTime+.55)}catch(e){}}

/* ---------- login ---------- */
function showLogin(){$('#out').classList.add('on')}
$('#lf').onsubmit=async e=>{e.preventDefault();$('#lerr').textContent='';const r=await fetch('/api/login',{method:'POST',body:JSON.stringify({username:$('#lu').value,password:$('#lp').value})}).then(r=>r.json());
 if(!r.ok){$('#lerr').textContent=r.msg;return}$('#lp').value='';$('#out').classList.remove('on');boot()};
$('#logout').onclick=async()=>{await fetch('/api/logout',{method:'POST'});S=null;showLogin()};
async function boot(){const m=await fetch('/api/me').then(r=>r.json());if(!m.ok){showLogin();$('#lhint').textContent='First run: admin / admin';return}me=m;$('#out').classList.remove('on');applyRole();poll()}
function applyRole(){document.body.classList.toggle('viewer',me.role=='viewer');document.body.classList.toggle('admin',me.role=='admin');$('#uname').textContent=me.user;$('#urole').textContent=me.role[0].toUpperCase()+me.role.slice(1)}

/* ---------- camera tiles ---------- */
function tileHTML(c){const has=['live','paused','ended','starting'].includes(c.status),b={live:['LIVE',''],paused:['PAUSED','p'],ended:['ENDED','i'],starting:['STARTING','p'],idle:['NO FEED','i'],error:['ERROR','e']}[c.status]||['NO FEED','i'];
return `<div class="tile"><div class="th"><b>${c.id}</b><span class="sec">${c.sector}</span><span class="badge ${b[1]}">${b[0]}</span><span class="ts"></span></div>
<div class="tv" data-cam="${c.id}">${has?`<img alt="${c.id} video feed with detections" data-cam="${c.id}">`:`<div class="ph"><div>No video feed</div><div><button class="btn pri needop" data-pick="${c.id}">Upload video</button></div><small>or drag a video file here</small></div>`}
${has?`<div class="ctl"><button class="needop" data-pause="${c.id}" title="${c.status=='paused'?'Resume':'Pause'}">${c.status=='paused'?'▶':'❚❚'}</button><a href="/api/snapshot/${c.id}" title="Snapshot" style="padding:3px 8px;text-decoration:none;color:inherit">📷</a><button data-full="${c.id}" title="Fullscreen">⛶</button></div>`:''}
<div class="prog"><i></i></div><input type="file" accept="video/*,.mkv,.avi,.mov" hidden></div></div>`}
function frameLoop(img){if(!img.isConnected)return;const c=S&&S.cams.find(x=>x.id==img.dataset.cam);
 if(img.offsetParent===null||(img.dataset.done&&c&&c.status!='live'))return setTimeout(()=>frameLoop(img),500);
 img.onload=()=>{img.dataset.done=1;setTimeout(()=>frameLoop(img),70)};img.onerror=()=>setTimeout(()=>frameLoop(img),600);img.src='/api/frame/'+img.dataset.cam+'?'+Date.now()}
function syncTiles(){$$('.tilehost').forEach(h=>{const c=S.cams.find(x=>x.id==h.dataset.cam);if(!c)return;const sig=c.status+'|'+c.name;
 if(h.dataset.sig!=sig){h.dataset.sig=sig;h.innerHTML=tileHTML(c);const img=$('img',h);if(img)frameLoop(img)}
 const ts=$('.ts',h);if(ts&&c.status=='live')ts.textContent=S.now})}
document.addEventListener('click',e=>{const t=e.target.closest('button,[data-p],.eye');if(!t)return;
 if(t.dataset.pick)$('input',t.closest('.tv')).click();
 if(t.dataset.pause){const c=S.cams.find(x=>x.id==t.dataset.pause);cmd({cmd:'cam_pause',cam:c.id,paused:c.status!='paused'}).then(poll)}
 if(t.dataset.full){const tv=t.closest('.tv');(tv.requestFullscreen||tv.webkitRequestFullscreen).call(tv)}
 if(t.dataset.p)go(t.dataset.p);
 if(t.classList.contains('eye'))openModal(+t.dataset.e);
 if(t.dataset.act)act(+t.dataset.id,t.dataset.act);
 if(t.dataset.z)zoom=t.dataset.z=='0'?1:Math.max(1,Math.min(3,zoom+(+t.dataset.z)*.4));
 if(t.dataset.inj)cmd({cmd:'inject',cls:+t.dataset.inj});
 if(t.dataset.ask)ask(t.dataset.ask);
 if(t.dataset.src)cmd({cmd:'cam_source',cam:t.dataset.src,src:$('#src-'+t.dataset.src).value}).then(poll);
 if(t.dataset.srcClear)cmd({cmd:'cam_source',cam:t.dataset.srcClear,src:''}).then(poll);
 if(t.dataset.zones)openZones(t.dataset.zones);
 if(t.dataset.close)closeModal()});
$('#modal').addEventListener('click',e=>{if(e.target.id=='modal')closeModal()});document.addEventListener('keydown',e=>{if(e.key=='Escape')closeModal()});
document.addEventListener('change',e=>{const fi=e.target;if(fi.matches&&fi.matches('.tv input[type=file]')&&fi.files[0]){const tv=fi.closest('.tv');upload(tv.dataset.cam,fi.files[0],tv);fi.value=''}});
document.addEventListener('dragover',e=>{const tv=e.target.closest('.tv');if(tv){e.preventDefault();tv.classList.add('drag')}});
document.addEventListener('dragleave',e=>{const tv=e.target.closest('.tv');if(tv)tv.classList.remove('drag')});
document.addEventListener('drop',e=>{const tv=e.target.closest('.tv');if(tv){e.preventDefault();tv.classList.remove('drag');if(e.dataTransfer.files[0]&&me.role!='viewer')upload(tv.dataset.cam,e.dataTransfer.files[0],tv)}});
function upload(cam,file,host){const x=new XMLHttpRequest(),bar=$('.prog i',host);x.open('POST',`/api/upload?cam=${cam}&name=${encodeURIComponent(file.name)}`);
 x.upload.onprogress=e=>{if(e.lengthComputable)bar.style.width=(100*e.loaded/e.total)+'%'};
 x.onload=()=>{bar.style.width='0';let r={};try{r=JSON.parse(x.responseText)}catch(_){}toast(r.ok?`${file.name} loaded on ${cam}. Analysis started.`:(r.msg||'Upload failed.'),r.ok);poll()};x.onerror=()=>toast('Upload failed.');x.send(file)}

/* ---------- events ---------- */
const open_=e=>e.status_key=='new'||e.status_key=='ack';
function table(list,full){if(!list.length)return '<div style="color:var(--mu);padding:12px">No events yet. Upload a video to a camera, or turn on demo data in Settings.</div>';
 return '<table><tr><th>ID<th>Time<th>Camera<th>Event Type<th>Detected Objects<th>Risk Level<th>Confidence<th>Location<th>Status<th>Action</tr>'+list.map(e=>`<tr><td>#${e.id}<td>${e.time}<td>${e.cam}<td>${ICON[e.type]||'●'} ${e.type}<td>${esc(e.objects)}<td><span class="pill L${e.level}">${LV[e.level]}</span><td>${e.conf.toFixed(2)}<td>${e.sector}<td><span class="st ${e.status_key}">${e.status}${e.esc?' ⚠ escalated':''}</span><td><button class="eye" data-e="${e.id}" aria-label="View event ${e.id}">👁</button>${full&&open_(e)?`<span class="needop"> ${e.status_key=='new'?`<button class="btn sm" data-act="ack" data-id="${e.id}">Acknowledge</button> `:''}<button class="btn sm grn" data-act="go" data-id="${e.id}">Dispatch</button> <button class="btn sm red" data-act="no" data-id="${e.id}">Dismiss</button></span>`:''}</tr>`).join('')+'</table>'}
async function act(id,a){try{const r=await cmd({cmd:'act',id,action:a});if(!r.ok)toast(r.msg);poll()}catch(e){}}
let clipTimer=null,clipN=0,clipId=0;
function openModal(id){modalId=id;$('#mbox').dataset.sig='';renderModal();$('#modal').classList.add('on')}
function closeModal(){modalId=null;clearInterval(clipTimer);$('#modal').classList.remove('on')}
function renderModal(){if(modalId==null)return;const e=S.events.find(x=>x.id==modalId);if(!e)return;const sig=[e.id,e.status_key,e.clip].join();if($('#mbox').dataset.sig==sig)return;$('#mbox').dataset.sig=sig;
 $('#mbox').innerHTML=`<div class="rowx"><h3 style="margin:0;flex:1">${ICON[e.type]||''} Event #${e.id}: ${e.type}</h3><button class="btn sm" data-close="1">Close</button></div>
 ${e.snap?`<div class="clip" style="margin-top:10px"><img id="clipimg" src="/api/evidence/${e.id}.jpg" alt="Evidence frame"><div class="rowx">${e.clip?`<button class="btn sm" id="clipbtn">▶ Replay</button><input type="range" id="clipsl" min="0" max="${e.clip-1}" value="0" aria-label="Replay position" style="flex:1"><span id="clipt" style="color:var(--mu)">${e.clip} frames</span>`:'<span style="color:var(--mu)">Replay clip is still being recorded…</span>'}</div></div>`:`<p style="color:var(--mu)">Simulated sensor event, so there is no video frame.</p>`}
 <table><tr><th>Camera<td>${e.cam} ${e.sector}<tr><th>Time<td>${e.time}<tr><th>Detected objects<td>${esc(e.objects)}<tr><th>Risk<td><span class="pill L${e.level}">${LV[e.level]}</span> score ${e.risk}<tr><th>Confidence<td>${e.conf.toFixed(2)}<tr><th>Alert channels<td>${(e.channels||[]).join(', ')}<tr><th>Source<td>${e.src=='video'?'Uploaded video':'Simulated demo sensors'}<tr><th>Status<td><span class="st ${e.status_key}">${e.status}</span>${e.by?' by '+esc(e.by):''}</tr></table>
 ${open_(e)?`<div class="rowx needop" style="margin-top:12px">${e.status_key=='new'?`<button class="btn pri" data-act="ack" data-id="${e.id}">Acknowledge</button>`:''}<button class="btn grn" data-act="go" data-id="${e.id}">Dispatch response</button><button class="btn red" data-act="no" data-id="${e.id}">Dismiss as false alarm</button></div>${e.level>=2?'<p style="color:var(--mu)">Policy: High and Critical alerts must be acknowledged before a response is dispatched.</p>':''}`:''}`;
 if(e.clip){clipId=e.id;clipN=e.clip;const sl=$('#clipsl'),im=$('#clipimg'),bt=$('#clipbtn'),show=i=>{im.src=`/api/clip/${e.id}/${i}.jpg`;sl.value=i;$('#clipt').textContent=`${i+1} / ${e.clip}`};
  sl.oninput=()=>{clearInterval(clipTimer);bt.textContent='▶ Replay';show(+sl.value)};
  bt.onclick=()=>{if(clipTimer&&bt.textContent.includes('Pause')){clearInterval(clipTimer);clipTimer=null;bt.textContent='▶ Replay';return}let i=+sl.value>=e.clip-1?0:+sl.value;bt.textContent='❚❚ Pause';clearInterval(clipTimer);clipTimer=setInterval(()=>{show(i);i++;if(i>=e.clip){clearInterval(clipTimer);clipTimer=null;bt.textContent='▶ Replay'}},166)};}}

/* ---------- zone editor ---------- */
let Z=null;
function openZones(cam){const c=S.cams.find(x=>x.id==cam);if(!c||!['live','paused','ended'].includes(c.status)){toast('Load a video on this camera first.');return}
 const im=new Image();im.onload=()=>{Z={cam,im,zones:JSON.parse(JSON.stringify(c.zones||[])),cur:[]};
  $('#mbox').dataset.sig='zones';modalId=null;$('#mbox').innerHTML=`<div class="rowx"><h3 style="margin:0;flex:1">Restricted zones: ${cam}</h3><button class="btn sm" data-close="1">Close</button></div>
  <p style="color:var(--mu);margin:6px 0">Click on the picture to add corners of a restricted area. Press <b>Finish shape</b> when done. Detections inside a zone raise crossing and intrusion events. With no zones, everything below the fence line slider is restricted.</p>
  <canvas id="zc" class="zc"></canvas><div class="rowx" style="margin-top:8px"><button class="btn sm" id="z-fin">Finish shape</button><button class="btn sm" id="z-undo">Undo point</button><button class="btn sm red" id="z-clear">Delete all zones</button><span style="flex:1"></span><button class="btn pri" id="z-save">Save zones</button></div><div id="z-list" style="margin-top:8px;color:var(--mu)"></div>`;
  $('#modal').classList.add('on');const cv=$('#zc');cv.width=im.naturalWidth;cv.height=im.naturalHeight;zdraw();
  cv.onclick=e=>{const r=cv.getBoundingClientRect();Z.cur.push([(e.clientX-r.left)/r.width,(e.clientY-r.top)/r.height]);zdraw()};
  $('#z-fin').onclick=()=>{if(Z.cur.length>=3){Z.zones.push({name:'Zone '+(Z.zones.length+1),pts:Z.cur});Z.cur=[];zdraw()}else toast('A zone needs at least 3 corners.')};
  $('#z-undo').onclick=()=>{Z.cur.pop();zdraw()};$('#z-clear').onclick=()=>{Z.zones=[];Z.cur=[];zdraw()};
  $('#z-save').onclick=async()=>{if(Z.cur.length>=3)$('#z-fin').click();const r=await cmd({cmd:'set_zones',cam:Z.cam,zones:Z.zones});toast(r.ok?'Zones saved.':r.msg,r.ok);if(r.ok){closeModal();poll()}}};
 im.src=`/api/frame/${cam}?`+Date.now()}
function zdraw(){const cv=$('#zc'),c=cv.getContext('2d'),w=cv.width,h=cv.height;c.drawImage(Z.im,0,0,w,h);
 const poly=(p,col,fill)=>{c.beginPath();p.forEach((q,i)=>i?c.lineTo(q[0]*w,q[1]*h):c.moveTo(q[0]*w,q[1]*h));if(fill){c.closePath();c.fillStyle=fill;c.fill()}c.lineWidth=3;c.strokeStyle=col;c.stroke();p.forEach(q=>{c.fillStyle=col;c.fillRect(q[0]*w-4,q[1]*h-4,8,8)})};
 Z.zones.forEach((z,i)=>{poly(z.pts,'#ffbe00','rgba(229,56,59,.25)');c.fillStyle='#ffbe00';c.font='bold 18px sans-serif';c.fillText(z.name,z.pts[0][0]*w+8,z.pts[0][1]*h-8)});if(Z.cur.length)poly(Z.cur,'#22b8f0');
 $('#z-list').innerHTML=Z.zones.length?Z.zones.map((z,i)=>`${esc(z.name)} (${z.pts.length} corners)`).join(' · '):'No custom zones. The default fence-line zone is used.'}

/* ---------- charts ---------- */
function fit(cv,h){if(!cv.clientWidth)return null;const d=devicePixelRatio||1,w=cv.clientWidth;cv.width=w*d;cv.height=h*d;cv.style.height=h+'px';const c=cv.getContext('2d');c.setTransform(d,0,0,d,0,0);return[c,w,h]}
function donut(){const f=fit($('#donut'),150);if(!f)return;const[c]=f,ty=S.types,vals=TYPES.map(t=>ty[t]||0),oth=Object.entries(ty).filter(([k])=>!TYPES.includes(k)).reduce((a,b)=>a+b[1],0),tot=vals.reduce((a,b)=>a+b,0)+oth;
 let a=-Math.PI/2;vals.concat([oth]).forEach((v,i)=>{if(!v)return;const s=v/tot*Math.PI*2;c.beginPath();c.arc(75,75,60,a,a+s);c.lineWidth=22;c.strokeStyle=TC[i]||'#64748b';c.stroke();a+=s});
 if(!tot){c.beginPath();c.arc(75,75,60,0,7);c.lineWidth=22;c.strokeStyle='#183456';c.stroke()}
 c.fillStyle='#e6eef8';c.textAlign='center';c.font='600 24px Segoe UI,Arial';c.fillText(tot,75,76);c.font='11px Segoe UI,Arial';c.fillStyle='#8ba2bd';c.fillText('Total Events',75,92);
 $('#dleg').innerHTML=TYPES.map((t,i)=>`<div><span><i style="background:${TC[i]}"></i>${t}</span><b>${vals[i]}</b></div>`).join('')+(oth?`<div><span><i style="background:#64748b"></i>Others</span><b>${oth}</b></div>`:'')}
function bars(id,h){const f=fit($(id),h);if(!f)return;const[c,w]=f,v=S.kpi.levels,mx=Math.max(5,...v),top=Math.ceil(mx/5)*5,x0=34,bw=(w-x0-10)/4;c.font='11px Segoe UI,Arial';
 for(let i=0;i<=4;i++){const y=h-24-(h-44)*i/4;c.strokeStyle='#183456';c.beginPath();c.moveTo(x0,y);c.lineTo(w,y);c.stroke();c.fillStyle='#8ba2bd';c.textAlign='right';c.fillText(Math.round(top*i/4),x0-6,y+4)}
 [0,1,2,3].forEach(i=>{const hh=(h-44)*v[i]/top,x=x0+bw*i+bw*.2;c.fillStyle=LC[i];c.fillRect(x,h-24-hh,bw*.6,hh);c.fillStyle='#e6eef8';c.textAlign='center';c.fillText(v[i],x+bw*.3,h-28-hh);c.fillStyle='#8ba2bd';c.fillText(LV[i],x+bw*.3,h-8)})}
function tbars(){const f=fit($('#tbars'),240);if(!f)return;const[c,w]=f,all=Object.entries(S.types).sort((a,b)=>b[1]-a[1]),mx=Math.max(1,...all.map(a=>a[1]));c.font='12px Segoe UI,Arial';
 all.slice(0,8).forEach(([k,n],i)=>{const y=12+i*28;c.fillStyle='#cfdced';c.textAlign='left';c.fillText(k,0,y+12);c.fillStyle=TC[TYPES.indexOf(k)]||'#64748b';c.fillRect(150,y,(w-190)*n/mx,16);c.fillStyle='#e6eef8';c.fillText(n,156+(w-190)*n/mx,y+13)});if(!all.length){c.fillStyle='#8ba2bd';c.fillText('No events yet',0,20)}}
function tline(){const f=fit($('#tl'),200);if(!f)return;const[c,w,h]=f,d=S.timeline,mx=Math.max(3,...d);c.strokeStyle='#183456';for(let i=0;i<=3;i++){const y=10+(h-34)*i/3;c.beginPath();c.moveTo(30,y);c.lineTo(w,y);c.stroke();c.fillStyle='#8ba2bd';c.font='11px Segoe UI';c.fillText(Math.round(mx*(3-i)/3),6,y+4)}
 c.beginPath();d.forEach((v,i)=>{const x=34+i*(w-44)/(d.length-1),y=10+(h-34)*(1-v/mx);i?c.lineTo(x,y):c.moveTo(x,y)});c.strokeStyle='#22b8f0';c.lineWidth=2;c.stroke();c.lineWidth=1;c.fillStyle='#8ba2bd';c.fillText('30 min ago',34,h-6);c.fillText('now',w-26,h-6)}

/* ---------- map ---------- */
let ter={};function rnd(s){return()=>{s|=0;s=s+0x6D2B79F5|0;let t=Math.imul(s^s>>>15,1|s);t=t+Math.imul(t^t>>>7,61|t)^t;return((t^t>>>14)>>>0)/4294967296}}
function terrain(w,h){const k=w+'x'+h;if(ter[k])return ter[k];const o=document.createElement('canvas');o.width=w;o.height=h;const c=o.getContext('2d'),sw=48,sh=Math.round(48*h/w),r=rnd(7),g=[],g2=[];
 for(let i=0;i<(sw+2)*(sh+2);i++){g.push(r());g2.push(r())}const sm=document.createElement('canvas');sm.width=sw;sm.height=sh;const sc=sm.getContext('2d'),im=sc.createImageData(sw,sh);
 for(let y=0;y<sh;y++)for(let x=0;x<sw;x++){const n=(g[y*(sw+2)+x]*.5+g[(y+1)*(sw+2)+x+1]*.5)*.7+g2[(y+1)*(sw+2)+x]*.3,p=(y*sw+x)*4;im.data[p]=Math.round(110+n*95);im.data[p+1]=Math.round(52+n*60);im.data[p+2]=Math.round(44+n*40);im.data[p+3]=255}
 sc.putImageData(im,0,0);c.imageSmoothingEnabled=true;c.drawImage(sm,0,0,w,h);
 const path=P=>{c.beginPath();P.forEach((p,i)=>i?c.lineTo(p[0]*w,p[1]*h):c.moveTo(p[0]*w,p[1]*h))};c.lineJoin='round';c.lineCap='round';
 path(RIVER);c.lineWidth=w*.075;c.strokeStyle='#5d7f8f';c.stroke();path(RIVER);c.lineWidth=w*.06;c.strokeStyle='#1d5a8a';c.stroke();path(RIVER);c.lineWidth=w*.025;c.strokeStyle='#3a86bd';c.stroke();return ter[k]=o}
function marks(cv,list){const f=fit(cv,Math.round(cv.clientWidth*(cv===$('#map1')?.33:.5)));if(!f)return;const[c,w,h]=f,T=terrain(Math.round(w),Math.round(h));cv._m=[];
 c.save();c.translate(w/2,h/2);c.scale(zoom,zoom);c.translate(-w/2,-h/2);c.drawImage(T,0,0,w,h);
 c.beginPath();BORDER.forEach((p,i)=>i?c.lineTo(p[0]*w,p[1]*h):c.moveTo(p[0]*w,p[1]*h));c.lineWidth=7;c.strokeStyle='rgba(229,56,59,.35)';c.stroke();c.lineWidth=2.5;c.strokeStyle='#ff4d50';c.stroke();
 for(const[id,p]of Object.entries(CAMP)){const x=p[0]*w,y=p[1]*h,cm=S.cams.find(q=>q.id==id),on=cm&&['live','paused','ended'].includes(cm.status);c.fillStyle=on?'#0d6b45':'#3a4658';c.strokeStyle=on?'#19c37d':'#7a8aa3';c.lineWidth=2;c.beginPath();c.roundRect(x-13,y-13,26,26,5);c.fill();c.stroke();c.font='13px Segoe UI';c.textAlign='center';c.fillStyle='#fff';c.fillText('📹',x,y+5);
  c.font='600 12px Segoe UI';const tw=c.measureText(id).width;c.fillStyle='rgba(8,18,34,.9)';c.fillRect(x+16,y-9,tw+10,18);c.fillStyle='#fff';c.textAlign='left';c.fillText(id,x+21,y+4)}
 list.slice(0,30).forEach(e=>{const a=CAMP[e.cam]||[.5,.5],j=n=>(((e.id*n)%97)/97-.5),x=(a[0]+j(37)*.09)*w,y=(a[1]+j(53)*.12)*h,r=11;c.fillStyle=LC[e.level];c.beginPath();c.arc(x,y,r,0,7);c.fill();c.strokeStyle='#fff';c.lineWidth=1.5;c.stroke();c.font='12px Segoe UI';c.textAlign='center';c.fillStyle='#fff';c.fillText(ICON[e.type]||'●',x,y+4.5);cv._m.push([x,y,r+3,e.id])});
 c.restore()}
function mapClick(cv,ev){const r=cv.getBoundingClientRect(),w=r.width,h=r.height,x=(ev.clientX-r.left-w/2)/zoom+w/2,y=(ev.clientY-r.top-h/2)/zoom+h/2;const m=(cv._m||[]).find(m=>Math.hypot(m[0]-x,m[1]-y)<m[2]);if(m)openModal(m[3])}

/* ---------- chat ---------- */
function chatHTML(sug){return `<div class="msgs" role="log" aria-live="polite"></div>${sug?`<div class="rowx">${['Show high risk events','Summarize suspicious activity','Explain risk levels','Generate report'].map(q=>`<button class="btn sm" data-ask="${q}">${q}</button>`).join('')}</div>`:''}<form><input type="text" placeholder="Ask something about the detected events..." aria-label="Ask the AI Security Agent"><button class="btn pri" type="submit">Send</button></form>`}
function paintChat(){$$('.msgs').forEach(m=>{m.innerHTML=chat.map(x=>`<div class="${x.b?'b':'u'}">${x.b?'':'You: '}${esc(x.t)}</div>`).join('');m.scrollTop=m.scrollHeight})}
async function ask(q){if(!q.trim())return;chat.push({t:q});paintChat();try{const r=await post('/api/ask',{q});chat.push({b:1,t:r.answer});paintChat()}catch(e){}}
['chat1','chat2'].forEach((id,i)=>{const h=$('#'+id);h.innerHTML=chatHTML(i==1);$('form',h).onsubmit=e=>{e.preventDefault();const inp=$('input',h);ask(inp.value);inp.value=''}});paintChat();

/* ---------- pages ---------- */
function go(p){page=p;$$('.page').forEach(x=>x.classList.toggle('on',x.id=='p-'+p));$$('nav button[data-p]').forEach(b=>b.classList.toggle('on',b.dataset.p==p));if(S)render(true)}
['1','2','3','4','5'].forEach(n=>{const h=$('#d-c'+n);h.className='tilehost';h.dataset.cam='CAM-0'+n});
$('#camgrid').innerHTML=['1','2','3','4','5'].map(n=>{const id='CAM-0'+n;return `<div class="pn"><div class="tilehost" data-cam="${id}"></div><div class="needop"><div class="rowx" style="margin-top:8px"><input id="src-${id}" placeholder="Webcam index (0) or RTSP/HTTP URL" class="in" style="flex:1;min-width:150px" aria-label="${id} source"><button class="btn sm" data-src="${id}">Set source</button><button class="btn sm red" data-src-clear="${id}">Clear</button></div>
<div class="rowx" style="margin-top:6px"><button class="btn sm pri" data-zones="${id}">Draw restricted zones</button><label class="tg" style="font-size:12px">Default fence line <input type="range" min="15" max="85" value="45" data-fy="${id}"> <span id="fy-${id}">45%</span></label></div></div><div class="stat" id="stat-${id}" style="color:var(--mu);font-size:12px;margin-top:6px"></div></div>`}).join('');
document.addEventListener('input',e=>{const t=e.target;if(t.dataset.fy){$('#fy-'+t.dataset.fy).textContent=t.value+'%';clearTimeout(t._h);t._h=setTimeout(()=>{const c=S.cams.find(x=>x.id==t.dataset.fy);cmd({cmd:'set_zones',cam:t.dataset.fy,zones:c.zones||[],fence_y:t.value/100})},200)}});
$('#inj').innerHTML=DEMO.map((n,i)=>`<button class="btn sm ${i<7?'red':'grn'}" data-inj="${i}">${n}</button>`).join('');
$('#mleg').innerHTML=[['🚶','Person'],['🚗','Vehicle'],['🛸','Drone'],['⚠️','Suspicious Activity / Fence'],['📹','Camera']].map(a=>`<div>${a[0]} ${a[1]}</div>`).join('');
const fl=()=>({lv:$('#f-lv').value,st:$('#f-st').value,q:$('#f-q').value.toLowerCase()});['#f-lv','#f-st'].forEach(s=>$(s).onchange=()=>render(true));$('#f-q').oninput=()=>render(true);
const setSel=(id,v)=>{const el=$(id);if(document.activeElement!==el)el.checked=v};
const tog=(id,k)=>$(id).onchange=e=>cmd({cmd:'set',[k]:e.target.checked});tog('#s-demo','demo');tog('#s-loop','loop');tog('#s-ag','agents_on');tog('#s-night','night');tog('#s-bad','bad');tog('#s-trails','trails');tog('#s-heat','heat');tog('#s-enh','enhance');
$('#s-snd').onchange=e=>{sound=e.target.checked;localStorage.setItem('bw_sound',sound?'1':'0');if(sound)beep()};
$('#s-tau').oninput=e=>cmd({cmd:'set',tau:e.target.value/100});$('#clr').onclick=()=>{if(confirm('Delete all events?'))cmd({cmd:'clear_events'}).then(poll)};$('#rst').onclick=()=>cmd({cmd:'reset'}).then(poll);
$('#s-whs').onclick=async()=>{const r=await cmd({cmd:'set',webhook_url:$('#s-wh').value,webhook_min:+$('#s-whm').value});toast(r.ok?'Webhook saved.':r.msg,r.ok)};
$('#s-wht').onclick=async()=>{const r=await cmd({cmd:'test_webhook'});toast(r.ok?'Test sent. See the audit log.':r.msg,r.ok)};
$('#pw-s').onclick=async()=>{const r=await post('/api/password',{old:$('#pw-o').value,new:$('#pw-n').value});toast(r.ok?'Password changed.':r.msg,r.ok);if(r.ok){$('#pw-o').value=$('#pw-n').value='';me.must_change=false}};
$('#nu-a').onclick=async()=>{const r=await post('/api/users',{op:'add',username:$('#nu-u').value,password:$('#nu-p').value,role:$('#nu-r').value});toast(r.ok?'User added.':r.msg,r.ok);if(r.ok){$('#nu-u').value=$('#nu-p').value='';loadUsers()}};
async function loadUsers(){if(me.role!='admin')return;const u=await req('/api/users');$('#ulist').innerHTML='<table><tr><th>User<th>Role<th></tr>'+u.map(x=>`<tr><td>${esc(x.username)}<td>${x.role}<td>${x.username==me.user?'':`<button class="btn sm red" data-deluser="${esc(x.username)}">Delete</button>`}</tr>`).join('')+'</table>'}
document.addEventListener('click',async e=>{const t=e.target.closest('[data-deluser]');if(t&&confirm('Delete user '+t.dataset.deluser+'?')){const r=await post('/api/users',{op:'delete',username:t.dataset.deluser});toast(r.ok?'User deleted.':r.msg,r.ok);loadUsers()}});
[$('#map1'),$('#map2')].forEach(cv=>cv.onclick=e=>mapClick(cv,e));
let sigE='',heatT=0;
function render(force){const k=S.kpi,ev=S.events;
 $('#banner').hidden=!S.must_change;$('#banner').textContent='You are using the default password. Change it in Settings > Account.';
 $('#top').innerHTML=`<div class="card2 h"><b>${k.high+k.critical}</b><span>High Risk</span></div><div class="card2 m"><b>${k.medium}</b><span>Medium Risk</span></div><div class="card2 l"><b>${k.low}</b><span>Low Risk</span></div><div class="card2 c"><b>${k.cams_online}</b><span>Cameras Online</span></div>`;
 const mx=ev.reduce((m,e)=>e.level>=2?Math.max(m,e.id):m,0);if(lastMax&&mx>lastMax)beep();lastMax=Math.max(lastMax,mx);
 syncTiles();const sg=ev.map(e=>e.id+e.status_key+e.level+(e.esc?1:0)).join()+page+(S.video);
 if(page=='dashboard'){if(force||sg!=sigE)$('#evt1').innerHTML=table(ev.slice(0,6),false);donut();bars('#bars',190);marks($('#map1'),ev)}
 if(page=='events'){const f=fl();if(force||sg!=sigE)$('#evt2').innerHTML=table(ev.filter(e=>(!f.lv||LV[e.level]==f.lv)&&(!f.st||e.status==f.st)&&(!f.q||(e.type+e.cam+e.sector+e.objects).toLowerCase().includes(f.q))),true)}
 if(page=='analytics'){$('#kv').innerHTML=[[ev.length,'Total events'],[k.handled,'Responses dispatched'],[k.missed,'Missed (demo sensors)'],[k.filtered,'False alarms filtered'],[k.blocked,'Policy blocks'],[k.avg_response==null?'n/a':k.avg_response+' s','Avg response time']].map(a=>`<div><b>${a[0]}</b><span>${a[1]}</span></div>`).join('');bars('#bars2',240);tbars();tline();
  $('#camtab').innerHTML='<table><tr><th>Camera<th>Status<th>Source<th>FPS<th>Processing<th>Detector<th>Zones<th>Events</tr>'+S.cams.map(c=>`<tr><td>${c.id} ${c.sector}<td>${c.status}<td>${esc(c.name||'-')}<td>${c.fps||'-'}<td>${c.proc_ms?c.proc_ms+' ms/frame':'-'}<td>${c.backend||'-'}<td>${(c.zones||[]).length||'default'}<td>${c.events}</tr>`).join('')+'</table>';
  if(!$('#heats').children.length)$('#heats').innerHTML=S.cams.map(c=>`<div class="heat"><b>${c.id} ${c.sector}</b><img data-heat="${c.id}" alt="Heatmap ${c.id}" onerror="this.style.opacity=.25"></div>`).join('');
  if(Date.now()-heatT>4000){heatT=Date.now();$$('img[data-heat]').forEach(i=>{i.style.opacity=1;i.src='/api/heat/'+i.dataset.heat+'.jpg?'+Date.now()})}}
 if(page=='map')marks($('#map2'),ev);
 if(page=='agent'){$('#ags').innerHTML=Object.entries(S.agents).map(([n,v])=>`<span class="chip"><i></i>${n[0].toUpperCase()+n.slice(1)} ${v}</span>`).join('')+'<span class="chip"><i></i>Orchestrator</span>';$('#log').innerHTML=S.log.map(l=>`<p>${esc(l)}</p>`).join('')}
 if(page=='reports')$('#rkv').innerHTML=[[ev.length,'Events'],[k.critical+k.high,'High and Critical'],[k.medium,'Medium'],[k.low,'Low'],[k.handled,'Dispatched']].map(a=>`<div><b>${a[0]}</b><span>${a[1]}</span></div>`).join('');
 if(page=='settings'){const c=S.cfg;setSel('#s-demo',c.demo);setSel('#s-loop',c.loop);setSel('#s-ag',S.agents_on);setSel('#s-night',S.night);setSel('#s-bad',S.bad);setSel('#s-trails',c.trails);setSel('#s-heat',c.heat);setSel('#s-enh',c.enhance);setSel('#s-snd',sound);
  if(document.activeElement!==$('#s-tau'))$('#s-tau').value=S.tau*100;$('#s-tv').textContent=S.tau.toFixed(2);if(document.activeElement!==$('#s-wh')){$('#s-wh').value=c.webhook_url;$('#s-whm').value=c.webhook_min}
  const bk=[...new Set(S.cams.map(c=>c.backend).filter(Boolean))];$('#det').innerHTML=`<p>Video analysis: <b>${S.video?'available':'OpenCV missing'}</b></p><p>Backend in use: <b>${bk.join(', ')||'starts when a video is loaded'}</b> (requested: ${esc(S.backend)})</p>${S.notes.map(n=>`<p style="color:var(--am)">${esc(n)}</p>`).join('')}<p style="color:var(--mu)">The bundled YOLOX neural network detects people and vehicles. COCO models have no drone class, so use a drone-trained model for reliable drone detection (see README).</p>`;
  if(!$('#ulist').dataset.l){$('#ulist').dataset.l=1;loadUsers()}}
 if(page=='cameras'){S.cams.forEach(c=>{const i=$(`input[data-fy="${c.id}"]`);if(i&&document.activeElement!==i){i.value=c.fence_y*100;$('#fy-'+c.id).textContent=Math.round(c.fence_y*100)+'%'}const s=$('#stat-'+c.id);if(s)s.textContent=`${c.status}${c.fps?' · '+c.fps+' fps':''}${c.proc_ms?' · '+c.proc_ms+' ms/frame':''} · zones: ${(c.zones||[]).length||'default'} · events: ${c.events}`})}
 sigE=sg;renderModal()}
async function poll(){if(!me)return;try{S=await req('/api/state');render(false)}catch(e){if(e.message!='login')$('#clk').textContent='Connection lost'}}
setInterval(poll,800);boot();
setInterval(()=>{if(S)$('#clk').textContent=new Date().toLocaleString('sv-SE').replace('T',' ')},1000);
