import { useEffect, useState } from "react";
import { Icon } from "../components/Icon";
import { PageHeader } from "./common";

export const CAUSE_TEXT = {
  sudden_brake: "Sudden brake",
  hard_jolt: "Hard jolt",
  saved_by_driver: "Saved by driver",
};

function clockText(seconds) {
  return `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, "0")}`;
}

export function formatWhen(iso) {
  const d = new Date(iso);
  const date = d.toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" });
  const time = d.toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit" });
  return `${date} · ${time}`;
}

/** Slide 46: every saved incident with its front picture, date, time and cause. No limit. Tap to watch (slide 47). */
export function IncidentsPage({ da, go }) {
  const [items, setItems] = useState(null);
  const [error, setError] = useState(null);
  const load = () =>
    da.client
      .listIncidents()
      .then((r) => setItems(r.incidents))
      .catch((e) => setError(e.message));
  useEffect(() => {
    void load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [da.client]);

  return (
    <div className="lp">
      <PageHeader title="Saved incidents" onBack={() => go("settings")} />
      <div className="lp-split">
        <div className="lp-stack">
          {items === null && !error && <p>Loading…</p>}
          {error && <p className="lp-error">{error}</p>}
          {items?.length === 0 && (
            <div className="lp-card lp-empty">
              <Icon name="video" size={32} />
              <b>No saved incidents yet</b>
              <small>
                After a sudden brake or jolt, or when the driver saves, the last 90 seconds from all four
                cameras appear here.
              </small>
            </div>
          )}
          {items?.map((i) => (
            <button key={i.id} className="lp-card lp-incident" onClick={() => go("playback", i.id)}>
              <span className="inc-thumb">
                {i.front_picture ? (
                  <img src={da.client.incidentPictureUrl(i.id)} alt="" />
                ) : (
                  <Icon name="video" />
                )}
                <span className="inc-length">{clockText(i.length_s)}</span>
              </span>
              <span>
                <b>
                  <span className={`lp-cause ${i.cause === "saved_by_driver" ? "blue" : "orange"}`} />{" "}
                  {CAUSE_TEXT[i.cause]}
                </b>
                <small>{formatWhen(i.happened_at)}</small>
                <small>
                  {Object.keys(i.videos).length} cameras · {i.length_s} s before
                </small>
              </span>
              <Icon name="chevron" />
            </button>
          ))}
        </div>
        <div className="lp-card lp-changes">
          <h2>
            <Icon name="video" /> Incident backup
          </h2>
          <p>
            The last 90 seconds from all four cameras is always kept. When an incident happens, it is saved
            here.
          </p>
          <p>There is no limit. Incidents stay saved until you delete them.</p>
          <div className="lp-spacer" />
          <div className="lp-total">
            <b>Saved</b>
            <span className="lp-mono">{items?.length ?? 0} incidents</span>
          </div>
        </div>
      </div>
    </div>
  );
}
