// Camera node: plays a gallery video and streams JPEG frames over WebSocket (protocol v1).
(() => {
  "use strict";
  const $ = (id) => document.getElementById(id);
  const video = $("video"), canvas = $("canvas"), ctx = canvas.getContext("2d");
  const playBtn = $("play"), conn = $("conn"), msg = $("msg");

  const state = {
    position: null, file: null, streaming: false, ws: null, replaced: false,
    seq: 0, sent: 0, dropped: 0, lastSent: 0, encoding: false, backoff: 1000,
    fps: 30, quality: 0.7, rtt: null, wakeLock: null, timers: [], retryTimer: null,
  };
  const MAX_BUFFERED = 512 * 1024; // skip frames if the network falls behind

  $("server").value = localStorage.getItem("da.server") || location.host;
  $("quality").value = localStorage.getItem("da.quality") || 0.7;
  $("fps").value = localStorage.getItem("da.fps") || 30;
  for (const id of ["server", "quality", "fps"]) {
    $(id).addEventListener("change", () => { try { localStorage.setItem("da." + id, $(id).value); } catch {} });
  }

  function setConn(text, cls) { conn.textContent = text; conn.className = "pill " + cls; }
  function apiBase() { return location.protocol + "//" + $("server").value.trim(); }
  function wsBase() { return (location.protocol === "https:" ? "wss://" : "ws://") + $("server").value.trim(); }
  function updatePlay() {
    playBtn.disabled = !(state.position && state.file) && !state.streaming;
    playBtn.textContent = state.streaming ? "Stop" : "Play";
    playBtn.classList.toggle("stop", state.streaming);
  }

  // ---- position buttons + taken positions ----
  document.querySelectorAll(".pos").forEach((b) => b.addEventListener("click", () => {
    if (state.streaming) return;
    state.position = b.dataset.pos;
    document.querySelectorAll(".pos").forEach((x) => x.classList.toggle("selected", x === b));
    $("sPos").textContent = state.position;
    updatePlay();
  }));
  async function refreshTaken() {
    if (state.streaming) return;
    try {
      const r = await fetch(apiBase() + "/api/status");
      const s = await r.json();
      document.querySelectorAll(".pos").forEach((b) => {
        const cam = s.cameras[b.dataset.pos];
        const taken = cam && cam.status === "online";
        b.classList.toggle("taken", taken);
        b.querySelector("small").textContent = taken ? "in use (will replace)" : "free";
      });
      if (conn.textContent === "server?") setConn("idle", "off");
    } catch { setConn("server?", "bad"); }
  }
  refreshTaken();
  setInterval(refreshTaken, 3000);

  // ---- video file ----
  $("file").addEventListener("change", (e) => {
    const f = e.target.files[0];
    if (!f) return;
    state.file = f;
    $("fileName").textContent = f.name;
    if (video.src) URL.revokeObjectURL(video.src);
    video.src = URL.createObjectURL(f);
    video.load();
    updatePlay();
  });

  // ---- WebSocket ----
  function connect() {
    if (!state.streaming || document.hidden) return; // hidden: we reconnect when the page is visible again
    if (state.ws && state.ws.readyState <= 1) return; // already connecting or open
    clearTimeout(state.retryTimer);
    setConn(state.ws ? "reconnecting" : "connecting", "wait");
    const ws = new WebSocket(wsBase() + "/ws/camera/" + state.position);
    ws.binaryType = "arraybuffer";
    state.ws = ws;
    ws.onopen = () => {
      ws.send(JSON.stringify({ type: "hello", position: state.position, client: "camera-web/1.0",
        width: canvas.width, height: canvas.height, fps: state.fps, video_name: state.file ? state.file.name : "" }));
    };
    ws.onmessage = (ev) => {
      if (typeof ev.data !== "string") return;
      const m = JSON.parse(ev.data);
      if (m.type === "ack") { setConn("live", "live"); state.backoff = 1000; msg.textContent = "Server accepted " + m.position + " (session " + m.session_id + ")"; }
      else if (m.type === "config") {
        // phone settings win if the user changed them; otherwise use the server's
        if (!localStorage.getItem("da.fps")) state.fps = m.fps;
        if (!localStorage.getItem("da.quality")) state.quality = m.jpeg_quality;
      }
      else if (m.type === "pong") { state.rtt = performance.now() - m.t; $("sRtt").textContent = Math.round(state.rtt) + " ms"; }
      else if (m.type === "replaced") { state.replaced = true; msg.textContent = "Another phone took this position."; stop(); setConn("replaced", "bad"); }
      else if (m.type === "error") { msg.textContent = "Server error: " + m.message; }
    };
    ws.onclose = () => {
      if (state.ws !== ws) return; // an old socket
      if (!state.streaming || state.replaced) return;
      if (document.hidden) {
        setConn("paused", "wait");
        return;
      }
      setConn("reconnecting", "wait");
      const wait = state.backoff;
      state.backoff = Math.min(state.backoff * 2, 5000);
      state.retryTimer = setTimeout(connect, wait);
    };
  }

  // ---- frames ----
  function drawContain() {
    const vw = video.videoWidth, vh = video.videoHeight;
    if (!vw || !vh) return false;
    const cw = canvas.width, ch = canvas.height;
    const s = Math.min(cw / vw, ch / vh);
    const w = vw * s, h = vh * s;
    ctx.fillStyle = "#000";
    ctx.fillRect(0, 0, cw, ch);
    ctx.drawImage(video, (cw - w) / 2, (ch - h) / 2, w, h);
    return true;
  }

  function sendFrame() {
    const ws = state.ws;
    if (!state.streaming || document.hidden || !ws || ws.readyState !== 1) return;
    const now = performance.now();
    if (now - state.lastSent < 1000 / state.fps - 3) return;
    if (state.encoding || ws.bufferedAmount > MAX_BUFFERED) { state.dropped++; return; }
    if (!drawContain()) return;
    state.lastSent = now;
    state.encoding = true;
    const captureTs = performance.timeOrigin + performance.now();
    canvas.toBlob(async (blob) => {
      state.encoding = false;
      if (!blob || ws.readyState !== 1) return;
      const jpeg = new Uint8Array(await blob.arrayBuffer());
      const buf = new ArrayBuffer(16 + jpeg.length);
      const dv = new DataView(buf);
      dv.setUint8(0, 1); dv.setUint8(1, 1);
      dv.setUint32(2, state.seq >>> 0, true);
      dv.setFloat64(6, captureTs, true);
      dv.setUint16(14, 0, true);
      new Uint8Array(buf, 16).set(jpeg);
      ws.send(buf);
      state.seq = (state.seq + 1) >>> 0;
      state.sent++;
    }, "image/jpeg", state.quality);
  }

  function frameLoop() {
    if (!state.streaming) return;
    sendFrame();
    if ("requestVideoFrameCallback" in video) video.requestVideoFrameCallback(frameLoop);
  }

  // ---- start / stop ----
  async function start() {
    state.fps = Number($("fps").value) || 30;
    state.quality = Number($("quality").value) || 0.7;
    state.streaming = true; state.replaced = false; state.ws = null;
    state.seq = 0; state.sent = 0; state.dropped = 0; state.backoff = 1000;
    document.querySelectorAll(".pos").forEach((b) => (b.disabled = true));
    $("file").disabled = true;
    updatePlay();
    try { await video.play(); } catch (e) { msg.textContent = "Cannot play video: " + e.message; stop(); return; }
    connect();
    if ("requestVideoFrameCallback" in video) video.requestVideoFrameCallback(frameLoop);
    else state.timers.push(setInterval(sendFrame, 33));
    let lastCount = 0, lastT = performance.now();
    state.timers.push(setInterval(() => {
      const now = performance.now();
      const fps = ((state.sent - lastCount) * 1000) / (now - lastT);
      lastCount = state.sent; lastT = now;
      $("sFps").textContent = fps.toFixed(1);
      $("sDrop").textContent = state.dropped;
      const ws = state.ws;
      if (ws && ws.readyState === 1) {
        ws.send(JSON.stringify({ type: "stats", sent_fps: Number(fps.toFixed(1)), dropped: state.dropped }));
        ws.send(JSON.stringify({ type: "ping", t: performance.now() }));
      }
    }, 2000));
    try { state.wakeLock = await navigator.wakeLock?.request("screen"); } catch {}
  }

  function stop() {
    state.streaming = false;
    clearTimeout(state.retryTimer);
    state.timers.forEach(clearInterval); state.timers = [];
    if (state.ws) { const ws = state.ws; state.ws = null; try { ws.close(); } catch {} }
    video.pause();
    try { state.wakeLock?.release(); } catch {}
    state.wakeLock = null;
    document.querySelectorAll(".pos").forEach((b) => (b.disabled = false));
    $("file").disabled = false;
    if (!state.replaced) setConn("idle", "off");
    updatePlay();
    refreshTaken();
  }

  playBtn.addEventListener("click", () => (state.streaming ? stop() : start()));
  // Screen off or another app/tab: the browser pauses the video and slows timers. So we
  // disconnect cleanly (the dashboard shows this camera as offline instead of a frozen picture)
  // and, when the page is visible again, play the video and reconnect at once.
  document.addEventListener("visibilitychange", async () => {
    if (!state.streaming) return;
    if (document.hidden) {
      msg.textContent = "Paused: keep this page open and the screen on.";
      const ws = state.ws;
      if (ws) { try { ws.close(); } catch {} }
      setConn("paused", "wait");
      return;
    }
    msg.textContent = "Back: reconnecting…";
    try { await video.play(); } catch {}
    if ("requestVideoFrameCallback" in video) video.requestVideoFrameCallback(frameLoop);
    state.backoff = 1000;
    connect();
    if (!state.wakeLock) {
      try { state.wakeLock = await navigator.wakeLock?.request("screen"); } catch {}
    }
  });
  // Wake lock is released by the browser when the page is hidden; forget it so we ask again.
  navigator.wakeLock && document.addEventListener("visibilitychange", () => {
    if (document.hidden) state.wakeLock = null;
  });
})();
