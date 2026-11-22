import { useEffect, useRef, useState } from "react";
import { Icon } from "../components/Icon";
import { isDriving } from "../logic";
import { CAUSE_TEXT, formatWhen } from "./IncidentsPage";
import { PageHeader } from "./common";

const CAMERAS = [
  ["front", "Front"],
  ["left", "Left"],
  ["right", "Right"],
  ["back", "Back"],
];

export function clock(seconds) {
  const s = Math.max(0, Math.floor(seconds));
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
}

/** Slide 48: videos only open when the car is parked. */
export function NotWhileDriving({ go }) {
  return (
    <div className="lp">
      <PageHeader title="Saved incidents" onBack={() => go("incidents")} />
      <div className="lp-card park-card">
        <span className="lp-obj-icon park-icon">
          <Icon name="parking" size={34} />
        </span>
        <div>
          <h2>Park to watch videos</h2>
          <p className="lp-changes-p">
            Saved videos open only when the car is stopped, so your eyes stay on the road.
          </p>
          <p className="park-dot">Backup keeps running while you drive</p>
          <button className="lp-primary" onClick={() => go("live")}>
            Back to live view <Icon name="arrowRight" />
          </button>
          <p className="lp-note">
            Demo: the app counts the car as driving while cameras are streaming. Stop them to watch.
          </p>
        </div>
      </div>
    </div>
  );
}

/** Slide 47: all four cameras play together, with the warnings given before the incident. */
export function PlaybackPage({ da, go, id }) {
  const { client, stats } = da;
  const [inc, setInc] = useState(null);
  const [error, setError] = useState(null);
  const [time, setTime] = useState(0);
  const [playing, setPlaying] = useState(false);
  const videos = useRef({});
  const driving = isDriving(stats);

  useEffect(() => {
    client
      .getIncident(id)
      .then(setInc)
      .catch((e) => setError(e.message));
  }, [client, id]);

  const all = () => Object.values(videos.current).filter(Boolean);
  const seek = (t) => {
    all().forEach((v) => (v.currentTime = t));
    setTime(t);
  };
  const toggle = () => {
    if (playing) all().forEach((v) => v.pause());
    else all().forEach((v) => v.play().catch(() => {}));
    setPlaying(!playing);
  };
  const share = async () => {
    const url = client.incidentVideoUrl(id, "front");
    try {
      if (navigator.share) await navigator.share({ title: "Driving Assistant incident", url });
      else await navigator.clipboard.writeText(url);
    } catch {
      /* cancelled */
    }
  };
  const remove = async () => {
    if (!window.confirm("Delete this incident and its videos? This cannot be undone.")) return;
    await client.deleteIncident(id).catch(() => {});
    go("incidents");
  };

  if (driving) return <NotWhileDriving go={go} />;
  if (error) {
    return (
      <div className="lp">
        <PageHeader title="Incident" onBack={() => go("incidents")} />
        <p className="lp-error">{error}</p>
      </div>
    );
  }
  if (!inc) return <div className="lp" />;

  const length = inc.length_s;
  const cams = CAMERAS.filter(([c]) => inc.videos[c]);

  return (
    <div className="lp">
      <PageHeader
        title={CAUSE_TEXT[inc.cause]}
        onBack={() => go("incidents")}
        right={
          <span className="lp-btnrow" style={{ marginTop: 0 }}>
            <button className="lp-btn" onClick={share}>
              <Icon name="share" /> Share
            </button>
            <button className="lp-iconbtn lp-iconbtn-danger" onClick={remove} aria-label="Delete incident">
              <Icon name="trash" />
            </button>
          </span>
        }
      />
      <p className="lp-note play-sub">
        {formatWhen(inc.happened_at)} · {cams.length} cameras
      </p>
      <div className="play-split">
        <div>
          <div className="play-grid">
            {CAMERAS.map(([c, label]) => (
              <div key={c} className="play-cell">
                {inc.videos[c] ? (
                  <video
                    ref={(el) => (videos.current[c] = el)}
                    src={client.incidentVideoUrl(id, c)}
                    muted
                    playsInline
                    preload="auto"
                    onTimeUpdate={
                      c === cams[0]?.[0] ? (e) => setTime(e.currentTarget.currentTime) : undefined
                    }
                    onEnded={() => setPlaying(false)}
                  />
                ) : (
                  <div className="play-missing">No video</div>
                )}
                <span className="play-label">{label}</span>
              </div>
            ))}
          </div>
          <div className="lp-card play-bar">
            <button className="play-btn" onClick={toggle} aria-label={playing ? "Pause" : "Play"}>
              <Icon name={playing ? "pause" : "play"} />
            </button>
            <div className="play-track">
              <input
                type="range"
                min={0}
                max={length}
                step={0.1}
                value={time}
                onChange={(e) => seek(Number(e.target.value))}
              />
              <span className="play-mark" title="Incident" />
            </div>
            <span className="lp-mono play-time">
              {clock(time)} / {clock(length)}
            </span>
          </div>
        </div>
        <div className="lp-card lp-changes">
          <h2>
            <Icon name="warning" /> Warnings before it
          </h2>
          <ul className="play-warnings">
            {inc.warnings.map((w, i) => (
              <li key={i}>
                <button className="lp-mono play-at" onClick={() => seek(w.time_in_video_s)}>
                  {clock(w.time_in_video_s)}
                </button>
                <span>
                  <b className={w.colour === "orange" ? "play-orange" : ""}>{w.message}</b>
                  <small>
                    {w.camera[0].toUpperCase() + w.camera.slice(1)}
                    {w.distance_m != null ? ` · ${w.distance_m} m` : ""}
                    {w.was_spoken ? " · spoken" : ""}
                  </small>
                </span>
              </li>
            ))}
            <li>
              <span className="lp-mono play-at">{clock(length)}</span>
              <span>
                <b className="play-orange">{CAUSE_TEXT[inc.cause]}</b>
                <small>Incident saved</small>
              </span>
            </li>
          </ul>
        </div>
      </div>
    </div>
  );
}
