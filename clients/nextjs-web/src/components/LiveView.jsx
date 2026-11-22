import { useEffect, useMemo, useRef, useState } from "react";
import { POSITIONS, roadFocus } from "@da/client";
import { DEMO_SECONDS, demoObjects } from "../demo";
import { useVoice } from "../hooks/useVoice";
import { CameraSlot } from "./CameraSlot";
import { IncidentNotice, SignBanner } from "./SignBanner";
import { TapMenu } from "./TapMenu";

const MENU_HIDE_MS = 3000;
const NOTICE_MS = 6000;
const LONG_PRESS_MS = 1000; // hold the screen this long = save an incident (slide 46 "Saved by driver")

function say(text, settings) {
  if (!("speechSynthesis" in window) || settings?.voice === false) return;
  const u = new SpeechSynthesisUtterance(text);
  u.volume = settings?.volume ?? 0.85;
  u.rate = settings?.speech_speed ?? 1;
  window.speechSynthesis.speak(u);
}

/**
 * Constant layout (DESIGN.md 4.1): left strip | front (top) + back (bottom) | right strip.
 * Slots never move or resize; only their content switches between black and video.
 *
 * demo: one entry of demo.js to show for a few seconds (Settings > Demo screens), or null.
 */
export function LiveView({ da, onSettings, demo, onDemoEnd, onOpenIncident }) {
  const { client, cameras, warnings, settings, connection, stats } = da;
  const [menu, setMenu] = useState(false);
  const [mirrored, setMirrored] = useState(false);
  const [showStats, setShowStats] = useState(false);
  const [notice, setNotice] = useState(null);
  const [toast, setToast] = useState(null);
  const timer = useRef();
  const press = useRef({ timer: null, fired: false });

  // Saved by driver: long-press anywhere, or the S key. The tap menu still has only 2 buttons.
  const saveIncident = async () => {
    setToast("Saving the last 90 seconds…");
    try {
      await client.saveIncident("saved_by_driver");
    } catch (e) {
      setToast(e.message.includes("moment ago") ? "Already saved a moment ago" : `Not saved: ${e.message}`);
    }
    setTimeout(() => setToast(null), 2500);
  };
  const pressStart = () => {
    press.current.fired = false;
    clearTimeout(press.current.timer);
    press.current.timer = setTimeout(() => {
      press.current.fired = true;
      if (navigator.vibrate) navigator.vibrate(60);
      void saveIncident();
    }, LONG_PRESS_MS);
  };
  const pressEnd = () => clearTimeout(press.current.timer);
  useVoice(warnings, settings);

  useEffect(() => {
    if (settings) setMirrored(settings.ar_mirror);
  }, [settings]);

  useEffect(() => {
    const onKey = (e) => {
      if (e.key === "d" || e.key === "D") setShowStats((s) => !s);
      if ((e.key === "s" || e.key === "S") && !e.repeat) void saveIncident();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  // Slide 45: "Incident saved" notice, also spoken.
  useEffect(() => {
    let hide;
    const off = client.on("incident", (m) => {
      setNotice(m);
      say("Incident saved", client.settings);
      clearTimeout(hide);
      hide = setTimeout(() => setNotice(null), NOTICE_MS);
    });
    return () => {
      off();
      clearTimeout(hide);
    };
  }, [client]);

  // Demo screens: show for a few seconds, say it once, then go back to normal.
  useEffect(() => {
    if (!demo) return;
    say(demo.say, settings);
    const t = setTimeout(() => onDemoEnd?.(), DEMO_SECONDS * 1000);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [demo]);

  const tap = () => {
    if (press.current.fired) {
      press.current.fired = false; // that was a long-press (incident), not a tap
      return;
    }
    setMenu(true);
    clearTimeout(timer.current);
    timer.current = setTimeout(() => setMenu(false), MENU_HIDE_MS);
  };
  useEffect(() => () => clearTimeout(timer.current), []);

  // Vision type (slides 36-43): night vision always on, night blindness = on when it is dark.
  const night = settings?.vision?.night_vision ? "on" : settings?.vision?.night_blindness ? "auto" : "off";
  // Wide, short slots (back) keep the road in view instead of the sky (from Lane setup).
  const focusFor = (p) => roadFocus(settings?.zones?.[`${p}_vehicles`]?.polygon);
  const demoView = useMemo(() => (demo ? { ...demo, objectsList: demoObjects(demo) } : null), [demo]);

  return (
    <div
      className="live-root"
      onClick={tap}
      onPointerDown={pressStart}
      onPointerUp={pressEnd}
      onPointerLeave={pressEnd}
      onPointerCancel={pressEnd}
      onContextMenu={(e) => e.preventDefault()}
    >
      <div className={`live-grid ${mirrored ? "mirrored" : ""}`}>
        {POSITIONS.map((p) => (
          <CameraSlot
            key={p}
            client={client}
            position={p}
            status={cameras[p]}
            warning={warnings[p]}
            view={{ night, focusY: focusFor(p), demo: p === "front" ? demoView : null }}
            zones={
              showStats && settings
                ? [settings.zones?.[`${p}_vehicles`], settings.zones?.[`${p}_people`]].filter(Boolean)
                : undefined
            }
          >
            {p === "front" && demo?.banner && <SignBanner {...demo.banner} />}
          </CameraSlot>
        ))}
        <TapMenu
          visible={menu}
          mirrored={mirrored}
          onWindscreen={() => {
            setMirrored((m) => !m);
            tap();
          }}
          onSettings={onSettings}
        />
      </div>
      {notice && (
        <IncidentNotice
          cause={notice.cause}
          onOpen={onOpenIncident ? () => onOpenIncident(notice.id) : null}
        />
      )}
      {demo && (
        <div className="demo-tag">
          Demo: {demo.title} (slide {demo.slide})
        </div>
      )}
      {connection !== "open" && (
        <div className="conn-banner">
          {connection === "connecting" ? "Connecting to server…" : "Server connection lost, reconnecting…"}
        </div>
      )}
      {showStats && stats && (
        <div className="stats-box" onClick={(e) => e.stopPropagation()}>
          {POSITIONS.map((p) => {
            const c = stats.cameras[p];
            return (
              <div key={p}>
                <b>{p}</b> {c.status} · in {c.in_fps} · det {c.det_fps} · {c.latency_ms ?? "-"} ms
              </div>
            );
          })}
          <div>gpu {stats.gpu}</div>
        </div>
      )}
    </div>
  );
}
