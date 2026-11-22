// DEMO SCREENS: the alert screens of slides 24-30 need detection that comes in phase 3/4
// (potholes, traffic lights, signs, night). Until then, Settings > Demo screens shows each
// one on the live view for a few seconds, so the whole app flow can be presented.
// Boxes use the same 0..1 coordinates as real detections.

export const DEMO_SECONDS = 8;

export const DEMOS = {
  pothole: {
    title: "Pothole ahead",
    slide: 24,
    say: "Pothole ahead, 8 metres",
    pill: { level: "danger", text: "Pothole ahead, 8 m" },
    objects: [
      { cls: "pothole", box: [0.42, 0.78, 0.6, 0.9], level: "danger", distance_m: 8 },
      { cls: "pothole", box: [0.55, 0.6, 0.63, 0.66], level: "caution", distance_m: 16 },
      { cls: "pothole", box: [0.47, 0.5, 0.51, 0.53], level: "none", distance_m: 30 },
    ],
  },
  crossing: {
    title: "Person crossing ahead",
    slide: 25,
    say: "Person crossing ahead, 5 metres",
    pill: { level: "danger", text: "Person crossing, 5 m" },
    objects: [
      { cls: "person", box: [0.46, 0.4, 0.53, 0.8], level: "danger", distance_m: 5 },
      { cls: "car", box: [0.12, 0.5, 0.3, 0.72], level: "none", distance_m: 14 },
      { cls: "car", box: [0.68, 0.52, 0.8, 0.64], level: "none", distance_m: 22 },
    ],
  },
  red_light: {
    title: "Red light ahead",
    slide: 26,
    say: "Red light. Stop, wait for green",
    banner: { kind: "red", title: "Red light · Stop", text: "Traffic light · wait for green" },
    objects: [{ cls: "traffic light", box: [0.62, 0.12, 0.66, 0.3], level: "danger", distance_m: 15 }],
  },
  road_sign: {
    title: "Road sign read aloud",
    slide: 27,
    say: "Model Town ahead",
    banner: { kind: "blue", title: "Model Town ahead", text: "Sign board · 40 m" },
    objects: [{ cls: "sign board", box: [0.66, 0.2, 0.86, 0.36], level: "info", distance_m: 40 }],
  },
  speed: {
    title: "Speed limit and speed breaker",
    slide: 28,
    say: "Speed limit 40. Speed breaker in 14 metres",
    banner: { kind: "blue", title: "Speed limit 40 km/h", text: "Speed breaker 14 m ahead" },
    objects: [
      { cls: "speed limit 40", box: [0.74, 0.22, 0.82, 0.36], level: "info", distance_m: 25 },
      { cls: "speed breaker", box: [0.3, 0.66, 0.7, 0.72], level: "caution", distance_m: 14 },
    ],
  },
  night: {
    title: "Night vision",
    slide: 30,
    say: "Night vision on",
    night: true,
    objects: [],
  },
};

/** Turn a demo into overlay-like objects that drawObjects() understands. */
export function demoObjects(demo) {
  return (demo?.objects ?? []).map((o, i) => ({
    track_id: 9000 + i,
    conf: 1,
    predicted: false,
    zone: "center",
    ...o,
  }));
}
