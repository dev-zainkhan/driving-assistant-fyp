import { useEffect, useRef, useState } from "react";
import { drawImageCover, drawObjects, drawZone } from "@da/client";
import { BADGE, slotShowsVideo } from "../logic";
import { WarningPill } from "./WarningPill";

const NIGHT_FILTER = "brightness(1.8) contrast(1.15) saturate(0.85)"; // slide 30: brightened image
const DARK_LEVEL = 70; // average brightness 0..255 below which the picture counts as "night"

/** Average brightness of a picture (0..255), measured on a tiny copy so it costs almost nothing. */
function brightness(bitmap, probe) {
  const pctx = probe.getContext("2d", { willReadFrequently: true });
  pctx.drawImage(bitmap, 0, 0, probe.width, probe.height);
  const d = pctx.getImageData(0, 0, probe.width, probe.height).data;
  let sum = 0;
  for (let i = 0; i < d.length; i += 4) sum += 0.299 * d[i] + 0.587 * d[i + 1] + 0.114 * d[i + 2];
  return sum / (d.length / 4);
}

/**
 * One fixed slot. Draws the newest JPEG with object-fit: cover maths, then the boxes from
 * the newest overlay. Side/back slots stay fully black unless their camera warns.
 *
 * view (optional):
 *   night:   "on" | "off" | "auto"  (auto = on when the picture is dark, for night blindness)
 *   focusY:  height of the picture kept in view when the slot cuts off top and bottom
 *            (the road, from Lane setup), see roadFocus() in @da/client
 *   demo:    { pill, objects } from demo.js, drawn on top (front slot only)
 * children: banners shown at the top left, under the warning pill.
 */
export function CameraSlot({ client, position, status, warning, zones, view, children }) {
  const canvasRef = useRef(null);
  const demo = view?.demo;
  const [isDark, setIsDark] = useState(false);
  const night = view?.night === "on" || (view?.night === "auto" && isDark) || !!demo?.night;
  const showVideo = (status === "online" && slotShowsVideo(position, warning)) || !!demo;
  const state = useRef({});
  state.current = { showVideo, zones, night, focusY: view?.focusY ?? 0.5, demoObjects: demo?.objectsList };
  const redraw = useRef(() => {});
  useEffect(() => {
    redraw.current();
  }, [showVideo, zones, night, view?.focusY, demo]);

  useEffect(() => {
    const canvas = canvasRef.current;
    const ctx = canvas.getContext("2d");
    const probe = document.createElement("canvas");
    probe.width = 16;
    probe.height = 9;
    let bitmap = null;
    let overlay = null;
    let decodingSeq = -1;
    let dirty = true;
    let raf = 0;
    let lastProbe = 0;

    const resize = () => {
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      const w = Math.max(1, Math.round(canvas.clientWidth * dpr));
      const h = Math.max(1, Math.round(canvas.clientHeight * dpr));
      if (canvas.width !== w || canvas.height !== h) {
        canvas.width = w;
        canvas.height = h;
        dirty = true;
      }
    };
    const ro = new ResizeObserver(resize);
    ro.observe(canvas);
    resize();

    const draw = () => {
      raf = requestAnimationFrame(draw);
      if (!dirty) return;
      dirty = false;
      const s = state.current;
      const W = canvas.width,
        H = canvas.height;
      ctx.fillStyle = "#000";
      ctx.fillRect(0, 0, W, H);
      if (!s.showVideo) return;
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      const srcW = bitmap?.width ?? 640;
      const srcH = bitmap?.height ?? 360;
      let crop = { sx: 0, sy: 0, sw: srcW, sh: srcH };
      if (bitmap) {
        ctx.filter = s.night ? NIGHT_FILTER : "none";
        crop = drawImageCover(ctx, bitmap, W, H, s.focusY);
        ctx.filter = "none";
      } else {
        crop = { sx: 0, sy: 0, sw: srcW, sh: srcH }; // demo without a camera: boxes on black
      }
      for (const z of s.zones ?? []) {
        if (z.polygon) drawZone(ctx, z.polygon, crop, srcW, srcH, W, H, undefined, dpr);
      }
      // Boxes only, no text on them: the warning pill already says what and how far.
      const opts = { scale: dpr, thick: s.night, labels: "none" };
      if (overlay && bitmap) drawObjects(ctx, overlay.objects, crop, srcW, srcH, W, H, opts);
      if (s.demoObjects?.length) drawObjects(ctx, s.demoObjects, crop, srcW, srcH, W, H, opts);
    };
    raf = requestAnimationFrame(draw);
    redraw.current = () => {
      dirty = true;
    };

    const offFrame = client.on("frame", (f) => {
      if (f.camera !== position) return;
      if (decodingSeq !== -1) return; // one decode at a time; the newest frame wins next round
      decodingSeq = f.seq;
      const blob = new Blob([f.jpeg], { type: "image/jpeg" });
      createImageBitmap(blob)
        .then((bmp) => {
          bitmap?.close();
          bitmap = bmp;
          dirty = true;
          const now = performance.now();
          if (now - lastProbe > 1000) {
            lastProbe = now;
            setIsDark(brightness(bmp, probe) < DARK_LEVEL);
          }
        })
        .catch(() => {})
        .finally(() => {
          decodingSeq = -1;
        });
    });
    const offOverlay = client.on("overlay", (o) => {
      if (o.camera !== position) return;
      overlay = o;
      dirty = true;
    });
    const offStatus = client.on("camera_status", (m) => {
      if (m.position !== position || m.status !== "offline") return;
      bitmap?.close();
      bitmap = null;
      overlay = null;
      dirty = true;
    });
    const offWarn = client.on("warning_state", () => (dirty = true));
    return () => {
      cancelAnimationFrame(raf);
      ro.disconnect();
      offFrame();
      offOverlay();
      offStatus();
      offWarn();
      bitmap?.close();
    };
  }, [client, position]);

  const live = status === "online";
  const pill =
    demo?.pill ??
    (live && showVideo && (warning.level === "danger" || warning.level === "caution") ? warning : null);

  return (
    <div
      className={`slot slot-${position} ${showVideo ? "on" : "off"} lvl-${demo?.pill?.level ?? warning.level} ${night ? "night" : ""}`}
    >
      <canvas ref={canvasRef} />
      <div className="badge" aria-label={`${position} camera`}>
        {BADGE[position]}
        {position === "front" && live && <span className="badge-dot" />}
      </div>
      {!live && !demo && <div className="offline-tag">offline</div>}
      {night && <div className="night-tag">Night vision</div>}
      <div className="slot-top">
        {pill && (
          <WarningPill
            level={pill.level}
            text={pill.text}
            compact={position === "left" || position === "right"}
          />
        )}
        {children}
      </div>
    </div>
  );
}
