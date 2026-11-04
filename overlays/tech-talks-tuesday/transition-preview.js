/* WebGL2 counterpart of grid-bend.shader. No external library or OBS calls. */
const canvas=document.getElementById('view'), gl=canvas.getContext('webgl2',{alpha:false,preserveDrawingBuffer:true});
const slider=document.getElementById('progress'),statusEl=document.getElementById('status');
let runStart=null, video=null, uploadedUrl=null, phase=0, frames=0, loopTimer=null, reversed=false, frameQueued=false;
const loopControl=document.getElementById('loop');
function fail(error){statusEl.textContent=error.message;document.body.dataset.testStatus='failed';console.error(error);}
(async()=>{try{
if(!gl)throw Error('WebGL2 is unavailable in this browser');
const vert=`#version 300 es
in vec2 position;out vec2 screenUV;
void main(){screenUV=vec2(position.x*.5+.5,.5-position.y*.5);gl_Position=vec4(position,0.,1.);}`;
const shaderResponse=await fetch('grid-preview.frag?v='+Date.now());
if(!shaderResponse.ok)throw Error('Could not load the grid shader');
const frag=await shaderResponse.text();
function compile(type,source){const s=gl.createShader(type);gl.shaderSource(s,source);gl.compileShader(s);if(!gl.getShaderParameter(s,gl.COMPILE_STATUS))throw Error(gl.getShaderInfoLog(s));return s;}
const program=gl.createProgram();gl.attachShader(program,compile(gl.VERTEX_SHADER,vert));gl.attachShader(program,compile(gl.FRAGMENT_SHADER,frag));gl.linkProgram(program);if(!gl.getProgramParameter(program,gl.LINK_STATUS))throw Error(gl.getProgramInfoLog(program));gl.useProgram(program);
const buffer=gl.createBuffer();gl.bindBuffer(gl.ARRAY_BUFFER,buffer);gl.bufferData(gl.ARRAY_BUFFER,new Float32Array([-1,-1,1,-1,-1,1,-1,1,1,-1,1,1]),gl.STATIC_DRAW);
const attr=gl.getAttribLocation(program,'position');gl.enableVertexAttribArray(attr);gl.vertexAttribPointer(attr,2,gl.FLOAT,false,0,0);
const phaseLoc=gl.getUniformLocation(program,'progress'),textures=[];
gl.pixelStorei(gl.UNPACK_FLIP_Y_WEBGL,false);
for(let i=0;i<2;i++){const tex=gl.createTexture();textures.push(tex);gl.activeTexture(gl.TEXTURE0+i);gl.bindTexture(gl.TEXTURE_2D,tex);gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_MIN_FILTER,gl.LINEAR);gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_MAG_FILTER,gl.LINEAR);gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_WRAP_S,gl.CLAMP_TO_EDGE);gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_WRAP_T,gl.CLAMP_TO_EDGE);gl.uniform1i(gl.getUniformLocation(program,i?'sceneB':'sceneA'),i);}
function upload(i,source){gl.activeTexture(gl.TEXTURE0+i);gl.bindTexture(gl.TEXTURE_2D,textures[i]);gl.texImage2D(gl.TEXTURE_2D,0,gl.RGBA,gl.RGBA,gl.UNSIGNED_BYTE,source);}
function render(){if(video&&video.readyState>=2){upload(0,video);upload(1,video);}gl.uniform1f(phaseLoc,phase);gl.drawArrays(gl.TRIANGLES,0,6);slider.value=phase;document.getElementById('position').textContent=Math.round(phase*100)+'%';document.body.dataset.progress=phase.toFixed(3);document.body.dataset.renderedFrames=String(++frames);}
const image=(src)=>new Promise((resolve,reject)=>{const i=new Image();i.onload=()=>resolve(i);i.onerror=()=>reject(Error('Could not load '+src));i.src=src;});
Promise.all([image('assets/review-start.jpg'),image('assets/review-game.jpg')]).then(images=>{images.forEach((im,i)=>upload(i,im));render();document.getElementById('play').disabled=false;document.getElementById('inspect').disabled=false;statusEl.textContent='WebGL shader compiled · ready';statusEl.className='success';document.body.dataset.testStatus='ready';loopTimer=setTimeout(play,600);}).catch(fail);
function queueFrame(){if(!frameQueued){frameQueued=true;requestAnimationFrame(tick);}}
function pause(){clearTimeout(loopTimer);runStart=null;}
function play(){clearTimeout(loopTimer);gl.uniform1i(gl.getUniformLocation(program,'sceneA'),reversed?1:0);gl.uniform1i(gl.getUniformLocation(program,'sceneB'),reversed?0:1);phase=0;runStart=performance.now();statusEl.textContent='Playing · 1.8 seconds';document.body.dataset.testStatus='playing';queueFrame();}
function tick(now){frameQueued=false;if(runStart===null&&!video)return;if(runStart!==null){phase=Math.min(1,(now-runStart)/1800);if(phase===1){runStart=null;statusEl.textContent='Transition complete';document.body.dataset.testStatus='complete';if(loopControl.checked)loopTimer=setTimeout(()=>{reversed=!reversed;play();},1000);}}render();if(runStart!==null||video)queueFrame();}
document.getElementById('play').onclick=play;
document.getElementById('inspect').onclick=()=>{pause();phase=.30;render();statusEl.textContent='Paused at 30% · tilted mesh';};
document.getElementById('reset').onclick=()=>{pause();phase=0;render();statusEl.textContent='Reset · outgoing image';};
slider.oninput=()=>{pause();phase=Number(slider.value);render();};
loopControl.onchange=()=>{clearTimeout(loopTimer);if(loopControl.checked&&runStart===null)play();};
document.getElementById('video-file').onchange=async(e)=>{const file=e.target.files[0];if(!file)return;pause();if(video)video.pause();if(uploadedUrl)URL.revokeObjectURL(uploadedUrl);uploadedUrl=URL.createObjectURL(file);video=document.createElement('video');video.muted=true;video.loop=true;video.playsInline=true;video.src=uploadedUrl;await video.play();phase=0;statusEl.textContent='Using local video · nothing uploaded';queueFrame();};
}catch(error){fail(error);}})();
