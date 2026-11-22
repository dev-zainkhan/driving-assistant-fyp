import { useState } from "react";
import { Icon } from "../components/Icon";
import { DEMOS } from "../demo";
import { PageHeader } from "./common";

function Row({ title, note, onClick }) {
  return (
    <button className="lp-row demo-row" onClick={onClick}>
      <span>
        {title}
        {note && <small>{note}</small>}
      </span>
      <Icon name="chevron" />
    </button>
  );
}

/**
 * Settings > Demo screens: opens every screen of the App map (slide 4), so the full flow can be
 * shown to the supervisor even where detection is not built yet (phase 3 and 4).
 */
export function DemoPage({ da, go, onDemo }) {
  const [msg, setMsg] = useState(null);
  const sampleIncident = async (cause) => {
    go("live"); // the live view shows the "Incident saved" notice (slide 45)
    try {
      await da.client.createSampleIncident(cause);
    } catch (e) {
      setMsg(e.message);
    }
  };

  return (
    <div className="lp">
      <PageHeader title="Demo screens" onBack={() => go("settings")} />
      <p className="lp-note demo-intro">
        Every screen of the app map. Screens marked <b>demo</b> show sample data for a few seconds, because
        their detection comes in a later phase.
      </p>
      <div className="lp-grid3">
        <section className="lp-card">
          <h2>
            <Icon name="sparkle" /> Setup
          </h2>
          <Row title="Vision type (first start)" note="Slides 6-13" onClick={() => go("setup-vision")} />
          <Row title="System check" note="Slide 14" onClick={() => go("check")} />
          <Row
            title="Camera not found"
            note="Slide 15 · left camera"
            onClick={() => go("camera-missing", ["left"])}
          />
        </section>

        <section className="lp-card">
          <h2>
            <Icon name="warning" /> Alerts and road info
          </h2>
          {Object.entries(DEMOS).map(([key, d]) => (
            <Row key={key} title={d.title} note={`Slide ${d.slide} · demo`} onClick={() => onDemo(key)} />
          ))}
        </section>

        <section className="lp-card">
          <h2>
            <Icon name="video" /> Incidents
          </h2>
          <Row
            title="Incident saved: sudden brake"
            note="Slide 45 · demo videos"
            onClick={() => sampleIncident("sudden_brake")}
          />
          <Row
            title="Incident saved: by driver"
            note="Slide 45 · demo videos"
            onClick={() => sampleIncident("saved_by_driver")}
          />
          <Row title="Saved incidents" note="Slides 46-47" onClick={() => go("incidents")} />
          <Row title="Park to watch videos" note="Slide 48" onClick={() => go("not-driving")} />
          <p className="lp-note">AR mirror (slide 18): tap the live view, then the windscreen button.</p>
        </section>
      </div>
      {msg && <p className="lp-error">{msg}</p>}
    </div>
  );
}
