/** FR-V3: front always shows video; other slots only while their camera warns. */
export function slotShowsVideo(position, warning) {
  if (position === "front") return true;
  return warning?.level === "caution" || warning?.level === "danger";
}

export function groupOfCode(code) {
  if (code.startsWith("PERSON_")) return "people";
  if (code.startsWith("VEHICLE_")) return "vehicles";
  return null;
}

/** Turn "Car on left" into a sentence for speech: "Car on the left". */
export function spokenText(warning) {
  return warning.text.replace(/ on (left|right)$/, " on the $1").replace(/(\d+) m$/, "$1 metres");
}

export function newVoiceState() {
  return { active: {}, lastByCode: {}, lastSpokenAt: -Infinity };
}

/**
 * Decide what to speak for a new warning_state. Calm rules (no chatter):
 * - only orange (danger) warnings are spoken, and only when they newly appear;
 * - the same warning code is not spoken again within `voice_repeat_s`;
 * - at most one sentence every `voice_gap_s`;
 * - never interrupt a sentence: if speech is busy, the new warning is skipped, not queued.
 * Mutates `state`; returns the sentence or null.
 */
export function nextAnnouncement(state, warnings, settings, nowMs, busy = false) {
  const repeatMs = (settings?.voice_repeat_s ?? 15) * 1000;
  const gapMs = (settings?.voice_gap_s ?? 4) * 1000;
  let sentence = null;
  const candidates = [];
  for (const [pos, w] of Object.entries(warnings)) {
    const before = state.active[pos] ?? new Set();
    const now = new Set(w.level === "danger" ? w.codes : []);
    state.active[pos] = now;
    const fresh = [...now].filter((c) => !before.has(c));
    const wanted = fresh.filter((c) => {
      const g = groupOfCode(c);
      const allowed = !g || settings?.alerts?.[g]?.announce !== false;
      return allowed && nowMs - (state.lastByCode[c] ?? -Infinity) >= repeatMs;
    });
    if (!wanted.length) continue;
    candidates.push(...wanted);
    if (sentence === null) sentence = spokenText(w);
  }
  if (!sentence) return null;
  // Every candidate counts as handled, spoken or not, so it does not pop up later.
  for (const c of candidates) state.lastByCode[c] = nowMs;
  if (!(settings?.voice ?? true) || busy || nowMs - state.lastSpokenAt < gapMs) return null;
  state.lastSpokenAt = nowMs;
  return sentence;
}

export const BADGE = { front: "F", left: "L", right: "R", back: "B" };

// ---------------- setup flow (slides 5, 6-13, 14, 15) ----------------

/** Cameras that are not connected, in the order they are announced. */
export function missingCameras(cameras) {
  return ["front", "left", "right", "back"].filter((p) => cameras[p] !== "online");
}

const CAMERA_NAMES = { front: "Front", left: "Left", right: "Right", back: "Back" };

/** "Left camera not found" / "Left and back cameras not found" (slide 15, also spoken). */
export function missingText(missing) {
  const names = missing.map((p) => CAMERA_NAMES[p]);
  if (names.length === 0) return "All cameras found";
  if (names.length === 1) return `${names[0]} camera not found`;
  const lower = names.map((n, i) => (i === 0 ? n : n.toLowerCase()));
  const list = lower.slice(0, -1).join(", ") + " and " + lower[lower.length - 1];
  return `${list} cameras not found`; // "Front, left and back cameras not found"
}

/** Slide 48: videos only open when parked. Cameras streaming = the car is being driven. */
export function isDriving(stats) {
  if (!stats) return false;
  return Object.values(stats.cameras).some((c) => c.status === "online" && c.in_fps > 1);
}

// ---------------- lane setup (Settings > Lane setup) ----------------

/** How much narrower the lane is at the horizon than at the bottom of the picture. */
const TOP_SHARE = 0.16;
/** The people zone is wider than the car lane (people crossing from the side). */
const PEOPLE_WIDEN = 1.45;

/**
 * Lane trapezoid from three easy numbers (all 0..1 of the picture):
 *   horizon: height where the road ends (0 = top, 1 = bottom)
 *   width:   lane width at the bottom of the picture
 *   centre:  middle of the lane at the bottom (0.5 = camera in the middle of the car)
 * kind "people" gives the wider zone used for people.
 * Corners go bottom-left, bottom-right, top-right, top-left, like the server's lane().
 */
export function laneFromSliders({ horizon, width, centre }, kind = "vehicles") {
  const w = kind === "people" ? Math.min(1.2, width * PEOPLE_WIDEN) : width;
  const topW = w * TOP_SHARE;
  const r = (v) => Math.round(v * 1000) / 1000;
  return [
    [r(centre - w / 2), 1],
    [r(centre + w / 2), 1],
    [r(centre + topW / 2), r(horizon)],
    [r(centre - topW / 2), r(horizon)],
  ];
}

/** The three slider values back from a saved lane polygon. */
export function slidersFromLane(polygon) {
  if (!polygon || polygon.length !== 4) return { horizon: 0.45, width: 0.64, centre: 0.5 };
  const [[bl], [br], , [, topY]] = polygon;
  return {
    horizon: topY,
    width: Math.round((br - bl) * 1000) / 1000,
    centre: Math.round(((bl + br) / 2) * 1000) / 1000,
  };
}
