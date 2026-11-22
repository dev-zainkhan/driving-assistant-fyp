import { useEffect, useRef, useState } from "react";
import { Icon } from "../components/Icon";
import { missingCameras, missingText } from "../logic";

const ITEMS = [
  { key: "front", title: "Front camera", icon: "camera" },
  { key: "back", title: "Rear camera", icon: "camera" },
  { key: "left", title: "Left camera", icon: "camera" },
  { key: "right", title: "Right camera", icon: "camera" },
  { key: "server", title: "Server", icon: "server" },
  { key: "audio", title: "Audio", icon: "speaker" },
];
const STEP_MS = 350;

function speak(text, settings) {
  if (!("speechSynthesis" in window)) return;
  const u = new SpeechSynthesisUtterance(text);
  u.volume = settings?.volume ?? 0.85;
  u.rate = settings?.speech_speed ?? 1;
  window.speechSynthesis.speak(u);
}

/** results: { front: "ok" | "missing" | "checking" | undefined, ... } */
function Tiles({ results, detail = {} }) {
  return (
    <div className="setup-tiles">
      {ITEMS.map((it) => {
        const r = results[it.key];
        const bad = r === "missing";
        return (
          <div key={it.key} className={`lp-card lp-tile ${bad ? "lp-tile-bad" : ""}`}>
            <span className="lp-obj-icon">
              <Icon name={bad && it.icon === "camera" ? "cameraOff" : it.icon} />
            </span>
            <span>
              <b>{it.title}</b>
              {detail[it.key] && <small className={bad ? "lp-bad-text" : ""}>{detail[it.key]}</small>}
            </span>
            <span className={`lp-dot ${r === "ok" ? "ok" : bad ? "bad" : "wait"}`}>
              {r === "ok" ? <Icon name="check" size={18} /> : bad ? "!" : "…"}
            </span>
          </div>
        );
      })}
    </div>
  );
}

/** Slide 14: checks the four cameras, the server and the speaker before driving. */
export function SystemCheckPage({ da, go }) {
  const { client, cameras } = da;
  const [results, setResults] = useState({});
  const [done, setDone] = useState(false);
  const camerasRef = useRef(cameras);
  camerasRef.current = cameras;
  const goRef = useRef(go); // go may be a new function each render; the check must run once
  goRef.current = go;

  useEffect(() => {
    let stop = false;
    (async () => {
      const wait = () => new Promise((r) => setTimeout(r, STEP_MS));
      // give phones that are reconnecting a moment
      await wait();
      for (const it of ITEMS) {
        if (stop) return;
        setResults((r) => ({ ...r, [it.key]: "checking" }));
        await wait();
        let ok;
        if (it.key === "server")
          ok = await client
            .getHealth()
            .then((h) => h.detector === "ready")
            .catch(() => false);
        else if (it.key === "audio") ok = typeof window !== "undefined" && "speechSynthesis" in window;
        else ok = camerasRef.current[it.key] === "online";
        setResults((r) => ({ ...r, [it.key]: ok ? "ok" : "missing" }));
      }
      if (stop) return;
      setDone(true);
      const missing = missingCameras(camerasRef.current);
      if (missing.length) goRef.current("camera-missing", missing);
    })();
    return () => {
      stop = true;
    };
  }, [client]);

  const count = Object.values(results).filter((r) => r === "ok" || r === "missing").length;
  const allOk = done && ITEMS.every((it) => results[it.key] === "ok");
  const serverBad = results.server === "missing";

  return (
    <div className="lp setup">
      <div className="setup-left">
        <div className="setup-top">
          <button className="lp-iconbtn" onClick={() => go("start")} aria-label="Back">
            <Icon name="back" />
          </button>
          <span className="setup-label">Setup</span>
        </div>
        <h1>System check</h1>
        <p className="setup-text">Checking the four cameras, the server and the speaker.</p>
        <div className="setup-progress">
          <span style={{ width: `${(count / ITEMS.length) * 100}%` }} />
        </div>
        <div className="setup-count">
          <span>{done ? "Complete" : "Checking…"}</span>
          <b className="lp-mono">
            {count} / {ITEMS.length}
          </b>
        </div>
        <div className="lp-spacer" />
        {allOk && (
          <p className="setup-ready">
            <Icon name="check" /> All systems ready
          </p>
        )}
        {serverBad && <p className="lp-bad-text">The server is not ready. Is it running on the laptop?</p>}
        <button
          className="lp-primary"
          disabled={!done}
          onClick={() => (serverBad ? go("check") : go("live"))}
        >
          {serverBad ? "Try again" : "Continue"} <Icon name="arrowRight" />
        </button>
      </div>
      <Tiles results={results} />
    </div>
  );
}

/** Slide 15: a camera is missing. Said out loud too, with Try again. */
export function CameraNotFoundPage({ da, go, missing }) {
  const { cameras, settings } = da;
  const [help, setHelp] = useState(false);
  const stillMissing = (missing ?? missingCameras(cameras)).filter((p) => cameras[p] !== "online");
  const title = missingText(stillMissing.length ? stillMissing : (missing ?? []));

  useEffect(() => {
    speak(`${title}. Please check the connection, then try again.`, settings);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const results = {};
  const detail = {};
  for (const p of ["front", "back", "left", "right"]) {
    results[p] = cameras[p] === "online" ? "ok" : "missing";
    detail[p] = cameras[p] === "online" ? "Connected" : "Not found";
  }
  results.server = "ok";
  detail.server = "Model loaded · Wi-Fi";
  results.audio = "ok";
  detail.audio = "Speaker ready";

  return (
    <div className="lp setup">
      <div className="setup-left">
        <span className="setup-label">Setup</span>
        <span className="setup-warn">
          <Icon name="warning" size={40} />
        </span>
        <h1>{stillMissing.length ? title : "All cameras found"}</h1>
        <p className="setup-text">
          {stillMissing.length ? "Please check the connection, then try again." : "You can continue now."}
        </p>
        <p className="setup-spoken">
          <Icon name="speaker" size={20} /> This message is also spoken
        </p>
        {help && (
          <div className="setup-help">
            On the phone: same Wi-Fi as the laptop, open <code>http://&lt;laptop-ip&gt;:8000/camera</code>,
            choose the position and a video, press Play. Or use Backup mode in Settings.
          </div>
        )}
        <div className="lp-spacer" />
        <div className="setup-buttons">
          <button className="lp-primary" onClick={() => go("check")}>
            <Icon name="refresh" /> Try again
          </button>
          <button className="lp-outline" onClick={() => setHelp((h) => !h)}>
            Help
          </button>
        </div>
        <button className="setup-skip" onClick={() => go("live")}>
          Continue without it
        </button>
      </div>
      <Tiles results={results} detail={detail} />
    </div>
  );
}
