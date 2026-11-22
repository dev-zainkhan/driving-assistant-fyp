// WebSocket + REST client for the Driving Assistant server, with auto reconnect.
// Framework-free: React, Next.js and plain JS can all use it.
import { parseServerMessage, parseViewerFrame } from "./protocol";
import { POSITIONS } from "./types";

export function normaliseBaseUrl(base) {
  let b = base.trim().replace(/\/+$/, "");
  if (!/^https?:\/\//i.test(b)) b = "http://" + b;
  return b;
}

export function wsUrl(base, path) {
  return normaliseBaseUrl(base).replace(/^http/i, "ws") + path;
}

const EMPTY_WARNING = { level: "none", codes: [], text: "", since: 0 };

export class DrivingAssistantClient {
  baseUrl;
  opts;
  ws = null;
  listeners = {};
  attempt = 0;
  timer = null;
  stopped = true;
  connection = "idle";
  cameras = { front: "offline", left: "offline", right: "offline", back: "offline" };
  warnings = { front: EMPTY_WARNING, left: EMPTY_WARNING, right: EMPTY_WARNING, back: EMPTY_WARNING };
  settings = null;
  stats = null;

  constructor(options) {
    this.opts = { video: "auto", backoffMs: [1000, 2000, 4000, 5000], ...options };
    this.baseUrl = normaliseBaseUrl(options.baseUrl);
  }

  // ---------------- events ----------------
  on(event, fn) {
    let set = this.listeners[event];
    if (!set) {
      set = new Set();
      this.listeners[event] = set;
    }
    set.add(fn);
    return () => set.delete(fn);
  }

  emit(event, value) {
    const set = this.listeners[event];
    set?.forEach((fn) => {
      try {
        fn(value);
      } catch (e) {
        console.error(`[da-client] ${event} listener failed`, e);
      }
    });
  }

  setConnection(s) {
    if (this.connection === s) return;
    this.connection = s;
    this.emit("connection", s);
  }

  // ---------------- WebSocket ----------------
  connect() {
    this.stopped = false;
    this.open();
  }

  close() {
    this.stopped = true;
    if (this.timer) clearTimeout(this.timer);
    this.timer = null;
    const ws = this.ws;
    this.ws = null;
    if (ws) {
      ws.onclose = null;
      ws.close();
    }
    this.setConnection("closed");
  }

  setVideoMode(video) {
    this.opts.video = video;
    this.send({ type: "subscribe", video });
  }

  send(msg) {
    if (this.ws && this.ws.readyState === 1) this.ws.send(JSON.stringify(msg));
  }

  open() {
    const WS = this.opts.WebSocketImpl ?? WebSocket;
    this.setConnection(this.attempt === 0 ? "connecting" : "reconnecting");
    const ws = new WS(wsUrl(this.baseUrl, "/ws/viewer"));
    ws.binaryType = "arraybuffer";
    this.ws = ws;
    ws.onopen = () => {
      this.attempt = 0;
      this.setConnection("open");
      this.send({ type: "subscribe", video: this.opts.video });
    };
    ws.onmessage = (ev) => this.handle(ev.data);
    ws.onerror = () => {
      /* onclose follows */
    };
    ws.onclose = () => {
      if (this.ws !== ws) return;
      this.ws = null;
      for (const p of POSITIONS) this.cameras[p] = "offline";
      if (this.stopped) return this.setConnection("closed");
      this.setConnection("reconnecting");
      const delays = this.opts.backoffMs;
      const wait = delays[Math.min(this.attempt, delays.length - 1)];
      this.attempt++;
      this.timer = setTimeout(() => this.open(), wait);
    };
  }

  /** Exposed for tests: feed one raw WebSocket message. */
  handle(data) {
    if (typeof data !== "string") {
      if (data instanceof ArrayBuffer || data instanceof Uint8Array) {
        try {
          this.emit("frame", parseViewerFrame(data));
        } catch (e) {
          console.warn("[da-client] bad frame", e);
        }
      }
      return;
    }
    const m = parseServerMessage(data);
    if (!m) return;
    switch (m.type) {
      case "welcome":
        this.settings = m.settings;
        for (const c of m.cameras) this.cameras[c.position] = c.status;
        this.emit("welcome", m);
        break;
      case "overlay":
        this.emit("overlay", m);
        break;
      case "warning_state":
        this.warnings = { ...this.warnings, ...m.cameras };
        this.emit("warning_state", m);
        break;
      case "camera_status":
        this.cameras = { ...this.cameras, [m.position]: m.status };
        this.emit("camera_status", m);
        break;
      case "stats":
        this.stats = m;
        this.emit("stats", m);
        break;
      case "incident":
        this.emit("incident", m);
        break;
      case "settings":
        this.settings = m.settings;
        this.emit("settings", m);
        break;
    }
    this.emit("message", m);
  }

  // ---------------- REST ----------------
  async request(method, path, body) {
    const f = this.opts.fetchImpl ?? fetch;
    const r = await f(this.baseUrl + path, {
      method,
      headers: body === undefined ? undefined : { "Content-Type": "application/json" },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
    const json = await r.json().catch(() => null);
    if (!r.ok) {
      const msg = json?.error?.message ?? `${method} ${path} failed (${r.status})`;
      throw new Error(msg);
    }
    return json;
  }

  getHealth() {
    return this.request("GET", "/api/health");
  }

  getMeta() {
    return this.request("GET", "/api/meta");
  }

  getStatus() {
    return this.request("GET", "/api/status");
  }

  getSettings() {
    return this.request("GET", "/api/settings");
  }

  /** Change some settings; the server saves them and tells every app. */
  async patchSettings(patch) {
    const s = await this.request("PATCH", "/api/settings", patch);
    this.settings = s;
    return s;
  }

  /** "Reset to recommended" on the Detection and alerts screen. */
  async resetAlerts() {
    const s = await this.request("POST", "/api/settings/alerts/reset");
    this.settings = s;
    return s;
  }

  /** Put every fine-tuning number back to its default. */
  async resetAdvanced() {
    const s = await this.request("POST", "/api/settings/advanced/reset");
    this.settings = s;
    return s;
  }

  getAdvancedSettings() {
    return this.request("GET", "/api/settings/advanced");
  }

  listIncidents(limit = 100) {
    return this.request("GET", `/api/incidents?limit=${limit}`);
  }

  getIncident(id) {
    return this.request("GET", `/api/incidents/${id}`);
  }

  async deleteIncident(id) {
    await this.request("DELETE", `/api/incidents/${id}`);
  }

  /** URL of one camera's incident video, for a <video> element. */
  incidentVideoUrl(id, camera) {
    return `${this.baseUrl}/api/incidents/${id}/video/${camera}`;
  }

  /** URL of the incident's front picture (slide 46 list). */
  incidentPictureUrl(id) {
    return `${this.baseUrl}/api/incidents/${id}/picture`;
  }

  /** Save the last 90 s of every camera as an incident (driver held the screen). */
  saveIncident(cause = "saved_by_driver") {
    return this.request("POST", "/api/incidents", { cause });
  }

  /** DEMO ONLY: save a sample incident from the test videos (until the real recorder exists). */
  createSampleIncident(cause = "sudden_brake") {
    return this.request("POST", "/api/incidents/sample", { cause });
  }

  getDatabaseSummary() {
    return this.request("GET", "/api/database");
  }

  listVideos() {
    return this.request("GET", "/api/sources/videos");
  }

  getFileSources() {
    return this.request("GET", "/api/sources/files");
  }

  startFileSources(files) {
    return this.request("POST", "/api/sources/files", files);
  }

  stopFileSources() {
    return this.request("DELETE", "/api/sources/files");
  }
}
