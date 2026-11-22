"use client";
// Keeps ONE connection to the server for the whole app. It lives in app/layout.jsx, so moving
// between pages (/, /setup/..., /settings/...) does not disconnect.
import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useDrivingAssistant } from "./hooks/useDrivingAssistant";
import { SETUP_DONE_KEY } from "./screens/VisionTypePage";

const DAContext = createContext({
  server: null,
  setServer: () => {},
  da: null,
  demo: null,
  setDemo: () => {},
});
const STORAGE_KEY = "da.server";

/**
 * Each screen of the app map (slide 4) has its own URL. go(page, param) in the screens
 * (the same screens as the React app) is turned into one of these.
 */
export const ROUTES = {
  live: () => "/",
  "setup-vision": () => "/setup/vision",
  check: () => `/setup/check?t=${Date.now()}`, // new t = run the check again
  "camera-missing": (missing) => `/setup/camera-not-found?missing=${(missing ?? []).join(",")}`,
  settings: () => "/settings",
  alerts: () => "/settings/alerts",
  vision: () => "/settings/vision",
  status: () => "/settings/status",
  lane: () => "/settings/lane",
  advanced: () => "/settings/advanced",
  demo: () => "/settings/demo",
  incidents: () => "/settings/incidents",
  playback: (id) => `/settings/incidents/${id}`,
  "not-driving": () => "/settings/incidents/park",
};

/** Server address to show on the Start screen: ?server=..., then the last one used, then this computer. */
export function defaultServer() {
  const fromUrl = new URLSearchParams(window.location.search).get("server");
  if (fromUrl) return fromUrl;
  try {
    const saved = localStorage.getItem(STORAGE_KEY);
    if (saved) return saved;
  } catch {
    /* storage blocked */
  }
  return `${window.location.hostname || "localhost"}:8000`;
}

export function rememberServer(server) {
  try {
    localStorage.setItem(STORAGE_KEY, server);
  } catch {
    /* ignore */
  }
}

/** First start: ask the vision type (slides 6-13). Later starts go straight to the System check. */
export function firstPageAfterStart() {
  try {
    return localStorage.getItem(SETUP_DONE_KEY) === "1" ? "check" : "setup-vision";
  } catch {
    return "setup-vision";
  }
}

function Connected({ server, setServer, demo, setDemo, children }) {
  const da = useDrivingAssistant(server);
  return <DAContext.Provider value={{ server, setServer, da, demo, setDemo }}>{children}</DAContext.Provider>;
}

export function DAProvider({ children }) {
  // Next.js first renders pages on the server, where there is no window or WebSocket.
  // So the app only starts once it runs in the browser.
  const [inBrowser, setInBrowser] = useState(false);
  const [server, setServer] = useState(null);
  const [demo, setDemo] = useState(null); // Settings > Demo screens: what to show on the live view
  useEffect(() => setInBrowser(true), []);

  if (!inBrowser) return null;
  if (!server) {
    return (
      <DAContext.Provider value={{ server: null, setServer, da: null, demo, setDemo }}>
        {children}
      </DAContext.Provider>
    );
  }
  return (
    <Connected server={server} setServer={setServer} demo={demo} setDemo={setDemo}>
      {children}
    </Connected>
  );
}

/** { server, setServer, da, demo, setDemo }: da is null until the driver pressed Start. */
export function useDA() {
  return useContext(DAContext);
}

/** go("settings") opens /settings, go("playback", 7) opens /settings/incidents/7, go("start") disconnects. */
export function useGo() {
  const router = useRouter();
  const { setServer } = useDA();
  return useCallback(
    (page, param) => {
      if (page === "start") {
        setServer(null);
        router.push("/");
        return;
      }
      const route = ROUTES[page];
      router.push(route ? route(param) : "/");
    },
    [router, setServer],
  );
}
