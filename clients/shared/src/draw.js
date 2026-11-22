export const LEVEL_COLORS = {
  none: "#ffffff", // far, just tracked
  caution: "#facc15", // a little near
  danger: "#fb923c", // near, warn now
  info: "#3b82f6", // signs
};

export const LEVEL_WIDTH = { none: 2, caution: 3, danger: 4, info: 3 };

/**
 * Source rectangle to draw so the image covers the destination (object-fit: cover).
 * focusY (0..1): which height of the picture to keep in the middle when the top and bottom
 * must be cut off, e.g. the road in a wide, short slot. Default 0.5 = the centre.
 */
export function coverCrop(srcW, srcH, dstW, dstH, focusY = 0.5) {
  const srcRatio = srcW / srcH;
  const dstRatio = dstW / dstH;
  if (srcRatio > dstRatio) {
    const sw = srcH * dstRatio;
    return { sx: (srcW - sw) / 2, sy: 0, sw, sh: srcH };
  }
  const sh = srcW / dstRatio;
  const sy = Math.min(srcH - sh, Math.max(0, focusY * srcH - sh / 2));
  return { sx: 0, sy, sw: srcW, sh };
}

/**
 * Height to keep in view for a camera: the middle of the road area, between the horizon of
 * its lane (Lane setup) and the bottom of the picture. 0.5 when there is no lane.
 */
export function roadFocus(lanePolygon) {
  if (!lanePolygon || lanePolygon.length !== 4) return 0.5;
  const horizon = lanePolygon[3][1];
  return (horizon + 1) / 2;
}

/** Map a normalised box to destination pixels through a cover crop. */
export function mapBox(box, crop, srcW, srcH, dstW, dstH) {
  const kx = dstW / crop.sw;
  const ky = dstH / crop.sh;
  return [
    (box[0] * srcW - crop.sx) * kx,
    (box[1] * srcH - crop.sy) * ky,
    (box[2] * srcW - crop.sx) * kx,
    (box[3] * srcH - crop.sy) * ky,
  ];
}

export function drawImageCover(ctx, img, dstW, dstH, focusY = 0.5) {
  const crop = coverCrop(img.width, img.height, dstW, dstH, focusY);
  ctx.drawImage(img, crop.sx, crop.sy, crop.sw, crop.sh, 0, 0, dstW, dstH);
  return crop;
}

/** Draw a zone polygon (e.g. the lane trapezoid) through a cover crop, for tuning. */
export function drawZone(
  ctx,
  polygon,
  crop,
  srcW,
  srcH,
  dstW,
  dstH,
  color = "rgba(59,130,246,0.9)",
  scale = 1,
) {
  if (polygon.length < 3) return;
  const kx = dstW / crop.sw;
  const ky = dstH / crop.sh;
  ctx.save();
  ctx.beginPath();
  polygon.forEach(([x, y], i) => {
    const px = (x * srcW - crop.sx) * kx;
    const py = (y * srcH - crop.sy) * ky;
    if (i === 0) ctx.moveTo(px, py);
    else ctx.lineTo(px, py);
  });
  ctx.closePath();
  ctx.fillStyle = color.replace(/[\d.]+\)$/, "0.12)");
  ctx.fill();
  ctx.setLineDash([8 * scale, 6 * scale]);
  ctx.lineWidth = 2 * scale;
  ctx.strokeStyle = color;
  ctx.stroke();
  ctx.restore();
}

export function labelFor(o) {
  const name = o.cls.charAt(0).toUpperCase() + o.cls.slice(1);
  return o.distance_m == null ? name : `${name} ${Math.round(o.distance_m)} m`;
}

/** Which group of the Detection & alerts screen an object belongs to. */
export function groupOf(cls) {
  return cls === "person"
    ? "people"
    : ["car", "bus", "truck", "motorcycle", "bicycle"].includes(cls)
      ? "vehicles"
      : cls;
}

/**
 * Draw the boxes of one overlay.
 * opts.labels: "all" | "warnings" (default) | "none" | a function (object) => true/false
 * opts.thick: night vision style (slide 30): thicker boxes
 */
export function drawObjects(ctx, objects, crop, srcW, srcH, dstW, dstH, opts = {}) {
  const scale = (opts.scale ?? 1) * (opts.thick ? 1.6 : 1);
  const labels = opts.labels ?? "warnings";
  // draw white first, danger last (on top)
  const order = { none: 0, info: 1, caution: 2, danger: 3 };
  const sorted = [...objects].sort((a, b) => order[a.level] - order[b.level]);
  for (const o of sorted) {
    const [x1, y1, x2, y2] = mapBox(o.box, crop, srcW, srcH, dstW, dstH);
    if (x2 < 0 || y2 < 0 || x1 > dstW || y1 > dstH) continue;
    const color = LEVEL_COLORS[o.level];
    ctx.save();
    ctx.strokeStyle = color;
    ctx.lineWidth = LEVEL_WIDTH[o.level] * scale;
    if (o.level === "danger") {
      ctx.shadowColor = color;
      ctx.shadowBlur = 12 * scale;
    }
    const r = 6 * scale;
    ctx.beginPath();
    if ("roundRect" in ctx) ctx.roundRect(x1, y1, x2 - x1, y2 - y1, r);
    else ctx.rect(x1, y1, x2 - x1, y2 - y1);
    ctx.stroke();
    ctx.restore();
    const isWarning = o.level === "danger" || o.level === "caution";
    const show =
      typeof labels === "function" ? labels(o) : labels === "all" || (labels === "warnings" && isWarning);
    if (show) {
      const text = labelFor(o);
      ctx.save();
      ctx.font = `600 ${13 * scale}px system-ui, sans-serif`;
      const w = ctx.measureText(text).width + 10 * scale;
      const h = 18 * scale;
      const ty = Math.max(0, y1 - h - 2 * scale);
      ctx.fillStyle = color;
      ctx.fillRect(x1, ty, w, h);
      ctx.fillStyle = o.level === "none" ? "#111" : "#1a1206";
      ctx.fillText(text, x1 + 5 * scale, ty + 13 * scale);
      ctx.restore();
    }
  }
}
