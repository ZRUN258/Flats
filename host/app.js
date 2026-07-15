"use strict";

const $ = (id) => document.getElementById(id);
const state = {
  motion: { port: null, reader: null, writer: null, buffer: "", connected: false },
  sensor: { port: null, reader: null, buffer: "", connected: false },
  position: { az: 0, tilt: 0, radius: 0 }, route: [], records: [], logs: [],
  scanIndex: 0, scanning: false, paused: false, awaitingMeasurement: null, rotation: 25
};

const ui = Object.fromEntries(["systemStatus","motionPortText","sensorPortText","sensorMode","azInput","tiltInput","radiusInput","actualPosition","currentPoint","currentValue","rangeValue","rmsValue","routeTag","progressBar","recordsBody","tableEmpty","terminal","surfaceCanvas","canvasEmpty","scanOrbit","startScanBtn","pauseScanBtn","manualDialog","manualValue"].map(id => [id, $(id)]));

function toast(message, error = false) {
  const el = document.createElement("div"); el.className = `toast${error ? " error" : ""}`; el.textContent = message;
  $("toastStack").append(el); setTimeout(() => el.remove(), 3200);
}
function log(direction, message, error = false) {
  const time = new Date().toLocaleTimeString("zh-CN", { hour12: false });
  state.logs.push({ time, direction, message });
  const line = document.createElement("div"); line.className = error ? "err" : direction === "RX" ? "rx" : "";
  line.textContent = `[${time}] ${direction.padEnd(3)} ${message}`; ui.terminal.append(line); ui.terminal.scrollTop = ui.terminal.scrollHeight;
}
function requireSerial() {
  if (!("serial" in navigator)) { toast("当前浏览器不支持 Web Serial，请使用 Chrome 或 Edge", true); return false; }
  return true;
}
async function connect(kind) {
  if (!requireSerial()) return;
  const dev = state[kind];
  if (dev.connected) { await disconnect(kind); return; }
  try {
    dev.port = await navigator.serial.requestPort();
    await dev.port.open({ baudRate: 115200, bufferSize: 4096 });
    dev.connected = true;
    if (kind === "motion") dev.writer = dev.port.writable.getWriter();
    updateConnectionUI(); readLoop(kind);
    log("SYS", `${kind === "motion" ? "运动控制器" : "传感器"}已连接`); toast("串口连接成功");
    if (kind === "motion") setTimeout(() => sendMotion("POS?"), 300);
  } catch (err) { log("ERR", err.message, true); toast(`连接失败：${err.message}`, true); }
}
async function disconnect(kind) {
  const dev = state[kind];
  try {
    if (dev.reader) { await dev.reader.cancel(); dev.reader.releaseLock(); dev.reader = null; }
    if (dev.writer) { dev.writer.releaseLock(); dev.writer = null; }
    if (dev.port) await dev.port.close();
  } catch (_) {} finally { dev.connected = false; dev.port = null; updateConnectionUI(); }
}
async function readLoop(kind) {
  const dev = state[kind], decoder = new TextDecoder();
  try {
    dev.reader = dev.port.readable.getReader();
    while (dev.connected) {
      const { value, done } = await dev.reader.read(); if (done) break;
      dev.buffer += decoder.decode(value, { stream: true });
      const lines = dev.buffer.split(/\r?\n/); dev.buffer = lines.pop();
      lines.filter(Boolean).forEach(line => kind === "motion" ? handleMotionLine(line.trim()) : handleSensorLine(line.trim()));
    }
  } catch (err) { if (dev.connected) { log("ERR", err.message, true); toast("串口读取中断", true); } }
  finally { if (dev.reader) { try { dev.reader.releaseLock(); } catch (_) {} dev.reader = null; } }
}
async function sendMotion(command) {
  if (!state.motion.connected || !state.motion.writer) { toast("请先连接运动控制器", true); throw new Error("motion disconnected"); }
  await state.motion.writer.write(new TextEncoder().encode(`${command}\n`)); log("TX", command);
}
function handleMotionLine(line) {
  log("RX", line, line.startsWith("ERR"));
  if (/^(POS|DONE|STOPPED),/.test(line)) parsePosition(line);
  if (line.startsWith("DONE,")) onMotionDone();
  if (line.startsWith("DATA,")) acceptMeasurement(Number(line.split(",")[1]));
  if (line.startsWith("ERR,")) toast(line, true);
}
function parsePosition(line) {
  const parts = line.split(","), offset = line.startsWith("POS,") ? 2 : 1;
  const values = parts.slice(offset, offset + 3).map(Number); if (values.some(Number.isNaN)) return;
  [state.position.az, state.position.tilt, state.position.radius] = values;
  ui.actualPosition.textContent = `AZ ${values[0].toFixed(4)}° · TILT ${values[1].toFixed(4)}° · R ${values[2].toFixed(3)} mm`;
}
function handleSensorLine(line) {
  log("S/RX", line); const match = line.match(/[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?/);
  if (match && state.awaitingMeasurement) acceptMeasurement(Number(match[0]));
}
function updateConnectionUI() {
  ui.motionPortText.textContent = state.motion.connected ? "已连接 · 115200 baud" : "未连接";
  ui.sensorPortText.textContent = state.sensor.connected ? "已连接 · 等待数据" : "未连接 · 可选";
  $("motionConnectBtn").textContent = state.motion.connected ? "断开" : "连接";
  $("sensorConnectBtn").textContent = state.sensor.connected ? "断开" : "连接";
  ui.systemStatus.className = `status-pill${state.scanning ? " scanning" : state.motion.connected ? " online" : ""}`;
  ui.systemStatus.querySelector("span").textContent = state.scanning ? "正在扫描" : state.motion.connected ? "设备就绪" : "系统待机";
}

function generateEqualAreaRoute() {
  const rings = Math.max(2, Number($("ringCount").value)), equator = Math.max(4, Number($("equatorCount").value));
  const radius = Number($("scanRadius").value), tiltLimit = modelGeometry().maxTilt, points = [{ az: 0, tilt: 0, radius }];
  for (let ring = 1; ring <= rings; ring++) {
    const tilt = tiltLimit * ring / rings;
    const count = Math.max(1, Math.round(equator * Math.sin(tilt * Math.PI / 180) / Math.max(.01, Math.sin(tiltLimit * Math.PI / 180))));
    const phase = ring % 2 ? 180 / count : 0;
    for (let i = 0; i < count; i++) points.push({ az: -180 + phase + i * 360 / count, tilt, radius });
  }
  state.route = points; state.scanIndex = 0; renderRoute(); toast(`已生成 ${points.length} 个覆盖点`);
}
function renderRoute() { ui.routeTag.textContent = `${state.route.length} 点`; ui.currentPoint.textContent = `${state.scanIndex} / ${state.route.length}`; drawSurface(); }
async function importRoute(file) {
  const rows = (await file.text()).split(/\r?\n/).map(x => x.trim()).filter(Boolean); const route = [];
  for (const row of rows) { const v = row.split(/[,;\t]/).map(Number); if (v.length >= 3 && v.slice(0,3).every(Number.isFinite)) route.push({ az:v[0], tilt:v[1], radius:v[2] }); }
  if (!route.length) return toast("CSV 中没有有效的 AZ,TILT,R 数据", true);
  state.route = route; state.scanIndex = 0; renderRoute(); toast(`已导入 ${route.length} 个检测点`);
}
async function startScan() {
  if (!state.route.length) generateEqualAreaRoute();
  if (!state.motion.connected) return toast("请先连接运动控制器", true);
  state.scanning = true; state.paused = false; state.scanIndex = 0; state.records = []; renderRecords(); updateScanUI(); await moveNext();
}
async function moveNext() {
  if (!state.scanning || state.paused) return;
  if (state.scanIndex >= state.route.length) { finishScan(); return; }
  const p = state.route[state.scanIndex]; ui.azInput.value = p.az.toFixed(4); ui.tiltInput.value = p.tilt.toFixed(4); ui.radiusInput.value = p.radius.toFixed(3);
  try { await sendMotion(`MOVE,${p.az.toFixed(4)},${p.tilt.toFixed(4)},${p.radius.toFixed(3)}`); }
  catch (_) { finishScan(true); }
}
async function onMotionDone() {
  if (!state.scanning || state.paused) return;
  await delay(Math.max(0, Number($("settleTime").value)));
  state.awaitingMeasurement = state.route[state.scanIndex];
  const mode = ui.sensorMode.value;
  if (mode === "onboard") await sendMotion("MEASURE");
  else if (mode === "manual") { ui.manualValue.value = (100 + Math.random() * 5).toFixed(3); ui.manualDialog.showModal(); }
  else if (!state.sensor.connected) { toast("外部传感器未连接", true); state.paused = true; updateScanUI(); }
  else log("SYS", "等待外部传感器数据");
}
function acceptMeasurement(value) {
  if (!Number.isFinite(value) || !state.awaitingMeasurement) return;
  const p = state.awaitingMeasurement; state.awaitingMeasurement = null;
  state.records.push({ index: state.records.length + 1, time: new Date().toISOString(), ...p, value, status: "有效" });
  state.scanIndex++; renderRecords(); updateMetrics(); drawSurface(); updateScanUI(); setTimeout(moveNext, 30);
}
function finishScan(error = false) {
  state.scanning = false; state.paused = false; state.awaitingMeasurement = null; updateScanUI();
  toast(error ? "扫描因连接问题停止" : `扫描完成，共 ${state.records.length} 个有效点`, error);
}
function updateScanUI() {
  const progress = state.route.length ? state.scanIndex / state.route.length * 100 : 0;
  ui.progressBar.style.width = `${progress}%`; ui.currentPoint.textContent = `${state.scanIndex} / ${state.route.length}`;
  ui.startScanBtn.textContent = state.scanning ? "结束扫描" : "开始扫描";
  ui.pauseScanBtn.disabled = !state.scanning; ui.pauseScanBtn.textContent = state.paused ? "继续" : "暂停";
  ui.scanOrbit.classList.toggle("active", state.scanning && !state.paused); updateConnectionUI();
}
function renderRecords() {
  ui.recordsBody.replaceChildren(...state.records.slice().reverse().map(r => {
    const tr = document.createElement("tr");
    [r.index, new Date(r.time).toLocaleTimeString("zh-CN",{hour12:false}), `${r.az.toFixed(4)}°`, `${r.tilt.toFixed(4)}°`, `${r.radius.toFixed(3)} mm`, r.value.toFixed(4), r.status].forEach(v => { const td=document.createElement("td");td.textContent=v;tr.append(td); }); return tr;
  })); ui.tableEmpty.style.display = state.records.length ? "none" : "block";
}
function stats() { const a=state.records.map(r=>r.value); if(!a.length)return null; const min=Math.min(...a),max=Math.max(...a),mean=a.reduce((x,y)=>x+y,0)/a.length;return{min,max,range:max-min,rms:Math.sqrt(a.reduce((s,v)=>s+(v-mean)**2,0)/a.length)}; }
function updateMetrics() { const s=stats(), last=state.records.at(-1); ui.currentValue.textContent=last?last.value.toFixed(4):"—";ui.rangeValue.textContent=s?s.range.toFixed(4):"—";ui.rmsValue.textContent=s?s.rms.toFixed(4):"—"; }

function modelGeometry() {
  const radius = Math.max(.1, Number($("curvatureRadius").value) || 8.6);
  const requestedDiameter = Math.max(.1, Number($("apertureDiameter").value) || 14);
  const diameter = Math.min(requestedDiameter, radius * 2);
  const apertureRadius = diameter / 2;
  const capHeight = radius - Math.sqrt(Math.max(0, radius * radius - apertureRadius * apertureRadius));
  const maxTilt = Math.asin(Math.min(1, apertureRadius / radius)) * 180 / Math.PI;
  return { radius, diameter, apertureRadius, capHeight, maxTilt };
}
function updateModel() {
  const m = modelGeometry();
  $("capHeight").value = m.capHeight.toFixed(2); $("maxTilt").value = m.maxTilt.toFixed(1);
  $("modelBadge").textContent = `球面直径 ${m.diameter.toFixed(1)} mm · R ${m.radius.toFixed(1)} mm`;
  drawSurface();
}
function drawSurface() {
  const canvas=ui.surfaceCanvas, rect=canvas.getBoundingClientRect(), dpr=devicePixelRatio||1; canvas.width=rect.width*dpr;canvas.height=rect.height*dpr;
  const ctx=canvas.getContext("2d");ctx.scale(dpr,dpr);const w=rect.width,h=rect.height,model=modelGeometry();
  const yaw=state.rotation*Math.PI/180,elevation=18*Math.PI/180,thetaMax=model.maxTilt*Math.PI/180;
  ctx.clearRect(0,0,w,h);
  const projectRaw=(theta,phi)=>{const x=Math.sin(theta)*Math.cos(phi),y=Math.sin(theta)*Math.sin(phi),z=Math.cos(theta);const xr=x*Math.cos(yaw)-y*Math.sin(yaw),yr=x*Math.sin(yaw)+y*Math.cos(yaw);return{x:xr,y:-z*Math.cos(elevation)+yr*Math.sin(elevation),depth:yr*Math.cos(elevation)+z*Math.sin(elevation)};};
  const bounds=[];for(let i=0;i<=20;i++){const theta=thetaMax*i/20;for(let j=0;j<72;j++)bounds.push(projectRaw(theta,2*Math.PI*j/72));}
  const minX=Math.min(...bounds.map(p=>p.x)),maxX=Math.max(...bounds.map(p=>p.x)),minY=Math.min(...bounds.map(p=>p.y)),maxY=Math.max(...bounds.map(p=>p.y));
  const padX=Math.max(34,w*.055),padTop=24,padBottom=62,scale=Math.min((w-padX*2)/Math.max(.01,maxX-minX),(h-padTop-padBottom)/Math.max(.01,maxY-minY));
  const offsetX=padX-minX*scale+(w-padX*2-(maxX-minX)*scale)/2,offsetY=padTop-minY*scale+(h-padTop-padBottom-(maxY-minY)*scale)/2;
  const project3=(theta,phi)=>{const p=projectRaw(theta,phi);return{x:offsetX+p.x*scale,y:offsetY+p.y*scale,depth:p.depth};};
  const faces=[],rings=18,sectors=52;
  for(let i=0;i<rings;i++){const t0=thetaMax*i/rings,t1=thetaMax*(i+1)/rings;for(let j=0;j<sectors;j++){const p0=2*Math.PI*j/sectors,p1=2*Math.PI*(j+1)/sectors,pts=[project3(t0,p0),project3(t0,p1),project3(t1,p1),project3(t1,p0)];faces.push({pts,depth:pts.reduce((s,p)=>s+p.depth,0)/4,light:.5+.32*Math.cos((p0+p1)/2-yaw)*Math.sin(t1)});}}
  faces.sort((a,b)=>a.depth-b.depth).forEach(f=>{const light=Math.round(94+f.light*5);ctx.beginPath();ctx.moveTo(f.pts[0].x,f.pts[0].y);f.pts.slice(1).forEach(p=>ctx.lineTo(p.x,p.y));ctx.closePath();ctx.fillStyle=`hsl(210 32% ${light}%)`;ctx.fill();ctx.strokeStyle="rgba(75,105,135,.13)";ctx.lineWidth=.6;ctx.stroke()});
  const rim=[];for(let j=0;j<=sectors;j++)rim.push(project3(thetaMax,2*Math.PI*j/sectors));ctx.beginPath();ctx.moveTo(rim[0].x,rim[0].y);rim.slice(1).forEach(p=>ctx.lineTo(p.x,p.y));ctx.strokeStyle="rgba(66,91,117,.42)";ctx.lineWidth=1.2;ctx.stroke();
  ctx.fillStyle="#6e6e73";ctx.font="11px -apple-system,BlinkMacSystemFont,sans-serif";ctx.textAlign="center";ctx.fillText(`口径 Ø ${model.diameter.toFixed(1)} mm`,w/2,offsetY+maxY*scale+31);
  const s=stats(),project=p=>project3(Math.min(thetaMax,p.tilt*Math.PI/180),p.az*Math.PI/180);
  state.route.map((p,i)=>({...project(p),p,i})).sort((a,b)=>a.depth-b.depth).forEach(q=>{if(q.i<state.records.length)return;ctx.fillStyle="rgba(60,92,124,.28)";ctx.beginPath();ctx.arc(q.x,q.y,2,0,Math.PI*2);ctx.fill()});
  state.records.map(r=>({...project(r),r})).sort((a,b)=>a.depth-b.depth).forEach(q=>{const ratio=s?.range?(q.r.value-s.min)/s.range:.5,hue=215-ratio*180;ctx.shadowColor=`hsla(${hue} 90% 50% / .5)`;ctx.shadowBlur=8;ctx.fillStyle=`hsl(${hue} 82% 52%)`;ctx.beginPath();ctx.arc(q.x,q.y,4.5,0,Math.PI*2);ctx.fill()});ctx.shadowBlur=0;
  ui.canvasEmpty.classList.toggle("hidden",state.route.length>0||state.records.length>0);
}
function exportData() {
  if(!state.records.length)return toast("暂无可导出的检测数据",true);
  const rows=[["index","time","azimuth_deg","tilt_deg","radius_mm","value","status"],...state.records.map(r=>[r.index,r.time,r.az,r.tilt,r.radius,r.value,r.status])];download(`flats_${stamp()}.csv`,"\ufeff"+rows.map(r=>r.join(",")).join("\n"),"text/csv");
}
function download(name,content,type){const a=document.createElement("a");a.href=URL.createObjectURL(new Blob([content],{type}));a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(a.href),1000)}
function stamp(){return new Date().toISOString().replace(/[:.]/g,"-")}
const delay=ms=>new Promise(resolve=>setTimeout(resolve,ms));

$("motionConnectBtn").onclick=()=>connect("motion"); $("sensorConnectBtn").onclick=()=>connect("sensor");
$("positionQueryBtn").onclick=()=>sendMotion("POS?").catch(()=>{});
$("moveBtn").onclick=()=>sendMotion(`MOVE,${ui.azInput.value},${ui.tiltInput.value},${ui.radiusInput.value}`).catch(()=>{});
$("stopBtn").onclick=()=>sendMotion("STOP").catch(()=>{});
document.querySelectorAll("[data-jog]").forEach(btn=>btn.onclick=()=>{const [axis,dir]=btn.dataset.jog.split(",");sendMotion(`JOG,${axis},${Number(dir)*Number($("jogStep").value)}`).catch(()=>{})});
$("generateRouteBtn").onclick=generateEqualAreaRoute; $("routeFile").onchange=e=>e.target.files[0]&&importRoute(e.target.files[0]);
ui.startScanBtn.onclick=()=>state.scanning?finishScan():startScan(); ui.pauseScanBtn.onclick=()=>{state.paused=!state.paused;updateScanUI();if(!state.paused)moveNext()};
$("exportBtn").onclick=exportData; $("reportBtn").onclick=()=>state.records.length?window.print():toast("完成检测后才能生成报告",true);
$("manualConfirm").onclick=()=>{const v=Number(ui.manualValue.value);setTimeout(()=>Number.isFinite(v)?acceptMeasurement(v):toast("请输入有效数值",true),0)};
$("rotationSlider").oninput=e=>{state.rotation=Number(e.target.value);$("rotationValue").textContent=`${state.rotation}°`;drawSurface()};
["curvatureRadius","apertureDiameter"].forEach(id=>$(id).addEventListener("input",updateModel));
document.querySelectorAll("[data-tab]").forEach(b=>b.onclick=()=>{document.querySelectorAll("[data-tab]").forEach(x=>x.classList.toggle("active",x===b));document.querySelectorAll(".tab-body").forEach(x=>x.classList.remove("active"));$(`${b.dataset.tab}Tab`).classList.add("active")});
window.addEventListener("resize",drawSurface); navigator.serial?.addEventListener("disconnect",()=>{updateConnectionUI();toast("串口设备已断开",true)});
renderRecords();updateScanUI();updateModel();
