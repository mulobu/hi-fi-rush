/* overlays/tech-talks-tuesday/fusion.js -- the fusion design, on either canvas
   Shared by overlay.html (1920 x 1080) and vertical.html (1080 x 1920): the
   scene copy, the surface with its windows cut out, the 3D grid transition
   and the flower loop. Only the flowers use the ASCII renderer. Core owns the
   source contract; each page owns its layout.

   Before this file the page defines CANVAS_W and CANVAS_H. After it, and
   before core/panel-page.js, it defines PANELS (with hole() and panel()
   below), GARDENS and GRID_TARGET. Nothing runs until the page's boot script
   calls startFusion(). */
const COLS = CANVAS_W / CELL_W, ROWS = CANVAS_H / CELL_H;
const GROUND = colour(THEME.ground), SOUND = false;
/* A theme with `css` recolours the page itself (palette.css variables). */
for(const [k,v] of Object.entries(THEME.css||{}))document.documentElement.style.setProperty('--'+k,v);

/* One panel per scene, each exactly the canvas inside its 15 px border, side
   by side. The panels paint nothing; the surface does. hole() takes a window
   in canvas px. */
const PANEL_SPACING = CANVAS_W + 80, PAGE_W = 6 * PANEL_SPACING, PAGE_H = CANVAS_H + 30;
const FULL = [0,0,CANVAS_W,CANVAS_H];
const hole = (src, a) => ({src,x:a[0]/(CANVAS_W/100),y:a[1]/(CANVAS_H/100),w:a[2]/(CANVAS_W/100),h:a[3]/(CANVAS_H/100),bare:true,label:src,c:'#43263d'});
const panel = (id,key,holes) => ({id,key,cls:'p-'+key,x:(id-1)*PANEL_SPACING,y:0,w:CANVAS_W+30,h:CANVAS_H+30,rot:0,fit:'fill',holes});
const SCENE_MAP = {START:1,CHAT:2,GAME:3,CAM:4,BRB:5,END:6};
function scaleFor(){return 1;}
function artFor(){return '';}
function transformFor(t){return `translate(${-(Number(t)-1)*PANEL_SPACING-15}px,-15px)`;}

/* GARDENS[key] is {garden, region}: a makeGarden() list in canvas px, and
   the cells [c0, r0, c1, r1] it is converted in. A scene with none draws no
   flowers. */
function drawFlowers(grid,now,key){
  wipe(grid,CLEAR);
  const g=GARDENS[key];
  if(!g)return;
  clearSource(flowerSource,[0,0,COLS,ROWS]);
  flowerSource.ctx.save();
  g.garden.draw(flowerSource.ctx,now/1000);
  flowerSource.ctx.restore();
  readSource(flowerSource,g.region);
  convert(flowerSource,grid,g.region,{bg:CLEAR,fillDim:1});
}

const COPY = {
  start:{n:'01',label:'THE CONVERSATION STARTS HERE',title:'Starting<br><span>soon.</span>',desc:'A little curiosity. A fresh perspective.<br>Let’s see what grows.',status:'GET COMFORTABLE',time:true},
  brb:{n:'02',label:'A MOMENT TO RECHARGE',title:'Back in<br><span>a bit.</span>',desc:'Stepping away. Keeping the ideas warm.<br>We’ll pick up right here.',status:'TAKING A SHORT BREAK'},
  end:{n:'03',label:'UNTIL THE NEXT CONVERSATION',title:'Stay<br><span>curious.</span>',desc:'Same time. Next Tuesday.',status:'THANK YOU FOR BEING HERE'},
  game:{n:'04',label:'IN THE FLOW'},cam:{n:'05',label:'A CLOSER LOOK'},chat:{n:'06',label:'ROOM FOR YOUR IDEAS'}
};
let current = null, fusionKey = '', standalone = false;
function setDesign(key){
  fusionKey=key;
  const c=COPY[key];
  document.body.dataset.scene=key;
  document.getElementById('chapter').textContent=c.n+' / '+c.label;
  document.getElementById('hero-title').innerHTML=c.title||'';
  document.getElementById('hero-desc').innerHTML=c.desc||'';
  document.getElementById('status-text').textContent=c.status||'';
  document.getElementById('scene-name').textContent=key==='game'?'IN THE FLOW':key==='cam'?'THE DEEP EFFECT':key==='chat'?'THE CONVERSATION': 'TECH TALKS TUESDAY';
  /* The surface is the canvas with this scene's windows cut out. A window
     inside another (GAME's cam, inside the game) is not cut again: evenodd
     would fill it back in. */
  const px=(v,s)=>Math.round(v*s)/100;
  const cuts=PANELS.find(p=>p.key===key).holes.map(h=>[px(h.x,CANVAS_W),px(h.y,CANVAS_H),px(h.w,CANVAS_W),px(h.h,CANVAS_H)]);
  const inside=(a,b)=>a!==b&&a[0]>=b[0]&&a[1]>=b[1]&&a[0]+a[2]<=b[0]+b[2]&&a[1]+a[3]<=b[1]+b[3];
  let path=`M0 0H${CANVAS_W}V${CANVAS_H}H0Z`;
  for(const [x,y,w,h] of cuts.filter(a=>!cuts.some(b=>inside(a,b))))path+=`M${x} ${y}h${w}v${h}h${-w}Z`;
  document.getElementById('surface-path').setAttribute('d',path);
}
function settleView(t){
  t=String(t);const p=PANELS.find(p=>String(p.id)===t);if(!p||current===t)return;
  current=t;setDesign(p.key);
  pageEl.style.transform=transformFor(t);
  applyPunch(Number(t));
  Object.entries(panelEls).forEach(([id,el])=>el.classList.toggle('is-live',id===t));
  if(!standalone)startTracking(160);
}

/* The shader runs on the page's host scene, so it turns live video into the
   mesh as well as the overlay. GPU time drives the animation; the socket
   only toggles it at the ends. The layout changes at CUT, while the frame is
   an edge-on line, which leaves tracking about 130 ms before the next scene
   rises out of it. CUT matches tools/build-tuesday-grid.py.

   GRID_TARGET() names the host scene to the filter requests, or is null
   until it is known: the vertical canvas's scene is found by uuid after the
   socket identifies, so attach() waits for it. Until the filter exists
   (tools/obs-setup.py makes it, from overlay.json's "transition", whose
   filter FILTER must match) the page cuts and looks again every 5 s. */
const GridFX=(()=>{
  const FILTER='Botanical Grid', DURATION=1800, CUT=.47;
  let ready=false, running=false, wanted=null, retry=0, warned=false;
  const pause=ms=>new Promise(resolve=>setTimeout(resolve,ms));
  const rpc=(kind,data)=>Promise.race([
    request(kind,{...GRID_TARGET(),filterName:FILTER,...data}),
    new Promise((_,reject)=>setTimeout(()=>reject(Error('Grid request timed out')),1200))
  ]);
  const enable=on=>rpc('SetSourceFilterEnabled',{filterEnabled:on});
  async function attach(){
    ready=false;
    clearTimeout(retry);
    if(!wsReady)return;
    if(!GRID_TARGET()){retry=setTimeout(attach,1500);return;}
    try{
      const f=await rpc('GetSourceFilter',{});
      if(f.filterSettings.last_error)throw Error(f.filterSettings.last_error);
      await enable(false);
      await rpc('SetSourceFilterSettings',{filterSettings:{Progress:-1,Duration:DURATION/1000},overlay:true});
      ready=true;
      if(warned)hud('3D grid found');
      warned=false;
    }catch(e){
      if(!warned)hud('3D grid unavailable: '+e.message,true);
      warned=true;
      retry=setTimeout(attach,5000);
    }
  }
  async function run(){
    if(running)return;
    running=true;
    try{
      while(wanted!==current){
        await enable(false);await pause(50);
        await enable(true);
        await pause(DURATION*CUT);
        settleView(wanted);
        await pause(DURATION*(1.04-CUT));
        await enable(false);
      }
    }catch(e){
      ready=false;hud('3D grid stopped: '+e.message,true);
      try{await enable(false);}catch(_){}
      settleView(wanted);
    }finally{running=false;}
  }
  return {attach,go(t,instant){
    wanted=String(t);
    if(instant||standalone||!ready){settleView(wanted);return;}
    void run();
  },state:()=>({ready,running,wanted})};
})();
function goTo(t,opts={}){
  if(!PANELS.some(p=>String(p.id)===String(t)))return;
  GridFX.go(t,opts.instant||current===null);
}

let flowerSource, fusionScreen, fusionGrid, lastFlowerFrame=-100;
function fusionLoop(now){
  requestAnimationFrame(fusionLoop);
  if(now-lastFlowerFrame<1000/30-2)return;
  lastFlowerFrame=now;
  drawFlowers(fusionGrid,now,fusionKey||'start');fusionScreen.draw(fusionGrid);
  document.getElementById('timer').textContent=document.getElementById('countdown').textContent;
  const date=new Date();
  document.getElementById('clock').textContent=date.toLocaleTimeString('en-GB',{hour:'2-digit',minute:'2-digit',timeZone:'Asia/Kolkata'})+' IST';
}
function startFusion(){
  flowerSource=makeSource(COLS,ROWS);
  fusionScreen=makeScreen(document.getElementById('screen'),COLS,ROWS,{glow:0,scan:0});
  fusionGrid=makeGrid(COLS,ROWS);
  const fontsIn=()=>{fitFont();measureShapes();fusionScreen.reset();};
  document.fonts.addEventListener('loadingdone',fontsIn);
  document.fonts.ready.then(fontsIn);
  requestAnimationFrame(fusionLoop);
}
