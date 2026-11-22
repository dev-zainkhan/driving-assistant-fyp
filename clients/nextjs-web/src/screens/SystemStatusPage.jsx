import { useCallback, useEffect, useState } from "react";
import { Icon } from "../components/Icon";
import { PageHeader } from "./common";

const CAMERA_TITLE = {
  front: "Front camera",
  back: "Rear camera",
  left: "Left camera",
  right: "Right camera",
};

/** Slide 44: cameras, server and audio at a glance, with a button to check again. */
export function SystemStatusPage({ da, go }) {
  const { client, cameras } = da;
  const [health, setHealth] = useState(null);
  const [serverOk, setServerOk] = useState(null);
  const check = useCallback(() => {
    setServerOk(null);
    client
      .getHealth()
      .then((h) => {
        setHealth(h);
        setServerOk(true);
      })
      .catch(() => setServerOk(false));
  }, [client]);
  useEffect(check, [check]);
  const audioOk = typeof window !== "undefined" && "speechSynthesis" in window;
  const tiles = [
    ...["front", "back", "left", "right"].map((p) => ({
      title: CAMERA_TITLE[p],
      text: cameras[p] === "online" ? "Connected" : "Not connected",
      ok: cameras[p] === "online",
      icon: "camera",
    })),
    {
      title: "Server",
      text:
        serverOk === null
          ? "Checking…"
          : !serverOk
            ? "Not reachable"
            : health?.detector === "ready"
              ? "Model loaded"
              : `Model ${health?.detector}`,
      ok: serverOk === null ? null : serverOk && health?.detector === "ready",
      icon: "server",
    },
    {
      title: "Audio",
      text: audioOk ? "Speaker ready" : "No speech on this device",
      ok: audioOk,
      icon: "speaker",
    },
  ];

  return (
    <div className="lp">
      <PageHeader
        title="System status"
        onBack={() => go("settings")}
        right={
          <button className="lp-iconbtn" onClick={check} aria-label="Check again">
            <Icon name="refresh" />
          </button>
        }
      />
      <div className="lp-grid3">
        {tiles.map((t) => (
          <div key={t.title} className="lp-card lp-tile">
            <span className="lp-obj-icon">
              <Icon name={t.icon} />
            </span>
            <span>
              <b>{t.title}</b>
              <small>{t.text}</small>
            </span>
            <span className={`lp-dot ${t.ok ? "ok" : t.ok === null ? "wait" : "bad"}`}>
              {t.ok ? <Icon name="check" size={18} /> : t.ok === null ? "…" : "!"}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
