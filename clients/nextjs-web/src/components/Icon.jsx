// Small outline icons for the settings screens (drawn like the slides, no icon package needed).
const PATHS = {
  back: "M19 12H5M11 18l-6-6 6-6",
  chevron: "M9 6l6 6-6 6",
  speaker: "M4 9v6h4l5 4V5L8 9H4zM16.5 8.5a5 5 0 0 1 0 7M19 6a8.5 8.5 0 0 1 0 12",
  eye: "M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12zM12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6z",
  eyeOff:
    "M3 3l18 18M10.6 10.6a2 2 0 0 0 2.8 2.8M9.9 5.2A10 10 0 0 1 12 5c6.5 0 10 7 10 7a17 17 0 0 1-3.2 4.1M6.6 6.6C3.9 8.3 2 12 2 12s3.5 7 10 7a9.6 9.6 0 0 0 5.4-1.6",
  moon: "M12 3a7 7 0 1 0 9 9 9 9 0 1 1-9-9zM17 4h4M19 2v4",
  server: "M4 4h16v6H4zM4 14h16v6H4zM8 7h.01M8 17h.01",
  car: "M5 17h14M5 17a2 2 0 1 0 4 0M15 17a2 2 0 1 0 4 0M3 17v-5l2-5h14l2 5v5M3 12h18",
  person: "M12 4a1.5 1.5 0 1 0 0 .01M9 20l3-6 3 6M7 11l5-2 5 2M12 9v5",
  light:
    "M9 3h6a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H9a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2zM12 7h.01M12 12h.01M12 17h.01",
  sign: "M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18zM8 12h8M12 9h.01M12 15h.01",
  bump: "M3 18h18M6 18a6 6 0 0 1 12 0",
  pothole: "M3 12c0-2 4-4 9-4s9 2 9 4-4 4-9 4-9-2-9-4zM8 12l2-1 2 2 2-2 2 1",
  board: "M4 4h16v8H4zM12 12v8M8 20h8",
  camera: "M4 8h3l2-3h6l2 3h3v11H4zM12 16a3 3 0 1 0 0-6 3 3 0 0 0 0 6z",
  video: "M3 6h12v12H3zM15 10l6-3v10l-6-3",
  refresh: "M20 11A8 8 0 1 0 18 17M20 5v6h-6",
  reset: "M4 11a8 8 0 1 1 2 6M4 5v6h6",
  arrows: "M4 12h16M8 8l-4 4 4 4M16 8l4 4-4 4",
  check: "M5 12l5 5L20 7",
  minus: "M5 12h14",
  plus: "M12 5v14M5 12h14",
  trash: "M4 7h16M10 11v6M14 11v6M5 7l1 13h12l1-13M9 7V4h6v3",
  warning: "M12 3 2 21h20L12 3zM12 10v5M12 18h.01",
  cameraOff: "M3 3l18 18M7 8H4v11h15M10 5h5l2 3h3v9M9.5 11.5a3 3 0 0 0 4 4",
  parking: "M5 3h14v18H5zM9 17V7h4a3 3 0 0 1 0 6H9",
  arrowRight: "M5 12h14M13 6l6 6-6 6",
  play: "M7 4v16l13-8z",
  pause: "M7 4h4v16H7zM13 4h4v16h-4z",
  share: "M12 3v12M8 7l4-4 4 4M5 13v7h14v-7",
  help: "M9.5 9a2.5 2.5 0 1 1 3.5 2.3c-.7.3-1 .9-1 1.7M12 17h.01M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18z",
  topview: "M9 4h6a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2H9a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2zM9 8h6M9 16h6",
  vibrate: "M9 6h6v12H9zM5 9v6M19 9v6M2 11v2M22 11v2",
  sparkle: "M12 3v4M12 17v4M3 12h4M17 12h4M6 6l2.5 2.5M15.5 15.5 18 18M6 18l2.5-2.5M15.5 8.5 18 6",
};

export function Icon({ name, size = 22, className }) {
  return (
    <svg
      className={className}
      viewBox="0 0 24 24"
      width={size}
      height={size}
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d={PATHS[name]} />
    </svg>
  );
}

export const OBJECT_ICONS = {
  vehicles: "car",
  people: "person",
  traffic_lights: "light",
  traffic_signs: "sign",
  speed_breakers: "bump",
  potholes: "pothole",
  sign_boards: "board",
};
