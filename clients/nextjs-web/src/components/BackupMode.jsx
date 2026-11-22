import { useEffect, useState } from "react";
import { POSITIONS } from "@da/client";

/** Pick a video for each position by name: "front.mp4", "road_left.mov", ... */
export function autoPick(videos) {
  const out = {};
  for (const p of POSITIONS) {
    const hit = videos.find((v) => v.name.toLowerCase().includes(p));
    if (hit) out[p] = hit.path;
  }
  return out;
}

/** Backup mode (FR-S9): the server plays video files from videos/ as the four cameras. */
export function BackupMode({ client }) {
  const [videos, setVideos] = useState([]);
  const [folder, setFolder] = useState("videos");
  const [pick, setPick] = useState({});
  const [running, setRunning] = useState({});
  const [msg, setMsg] = useState(null);
  const refresh = async () => {
    try {
      const [v, r] = await Promise.all([client.listVideos(), client.getFileSources()]);
      setVideos(v.videos);
      setFolder(v.folder);
      setRunning(r.running);
      setPick((cur) => (Object.keys(cur).length ? cur : autoPick(v.videos)));
    } catch (e) {
      setMsg(e.message);
    }
  };
  useEffect(() => {
    void refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [client]);
  const start = async () => {
    const files = Object.fromEntries(Object.entries(pick).filter(([, v]) => v));
    if (!Object.keys(files).length) return setMsg("Choose at least one video.");
    try {
      const r = await client.startFileSources(files);
      setMsg(`Started: ${r.started.join(", ")}`);
    } catch (e) {
      setMsg(e.message);
    }
    void refresh();
  };
  const stop = async () => {
    await client.stopFileSources().catch(() => {});
    setMsg("Backup mode stopped.");
    void refresh();
  };
  const isRunning = Object.keys(running).length > 0;

  return (
    <section className="lp-card lp-wide">
      <h2>Backup mode (no phones)</h2>
      <p className="lp-note">
        The laptop plays videos from the <code>{folder}</code> folder as the four cameras. Use it if the Wi-Fi
        or phones fail. A phone that connects later takes its position back.
      </p>
      {videos.length === 0 ? (
        <p className="lp-note">
          No videos found. Put .mp4 files in the {folder} folder (for example front.mp4, left.mp4, right.mp4,
          back.mp4).
        </p>
      ) : (
        POSITIONS.map((p) => (
          <div className="lp-formrow" key={p}>
            <span className="lp-cap">{p}</span>
            <select value={pick[p] ?? ""} onChange={(e) => setPick({ ...pick, [p]: e.target.value })}>
              <option value="">(none)</option>
              {videos.map((v) => (
                <option key={v.path} value={v.path}>
                  {v.path.replace(/^videos\//, "")}
                </option>
              ))}
            </select>
            <b className={running[p] ? "lp-okay" : "lp-silent"}>{running[p] ? "playing" : "off"}</b>
          </div>
        ))
      )}
      <div className="lp-btnrow">
        <button className="lp-primary lp-small" onClick={start} disabled={!videos.length}>
          {isRunning ? "Restart backup mode" : "Start backup mode"}
        </button>
        <button className="lp-btn" onClick={stop} disabled={!isRunning}>
          Stop
        </button>
      </div>
      {msg && <p className="lp-note">{msg}</p>}
    </section>
  );
}
