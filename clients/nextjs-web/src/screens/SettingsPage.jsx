import { useEffect, useRef, useState } from "react";
import { BackupMode } from "../components/BackupMode";
import { Icon } from "../components/Icon";
import { PageHeader } from "./common";

/** Slide 34: three cards (Voice and audio, Detection and alerts, System). */
export function SettingsPage({ da, go, onDisconnect }) {
  const { settings, updateSettings, client } = da;
  const [incidents, setIncidents] = useState(null);
  useEffect(() => {
    client
      .listIncidents(1)
      .then((r) => setIncidents(r.count))
      .catch(() => setIncidents(null));
  }, [client]);
  if (!settings)
    return (
      <div className="lp">
        <PageHeader title="Settings" onBack={() => go("live")} />
        <p>Loading…</p>
      </div>
    );
  const alerts = Object.entries(settings.alerts);

  return (
    <div className="lp">
      <PageHeader title="Settings" onBack={() => go("live")} />
      <div className="lp-grid3">
        <section className="lp-card">
          <h2>
            <Icon name="speaker" /> Voice &amp; audio
          </h2>
          <Slider
            label="Voice volume"
            value={settings.volume}
            min={0}
            max={1}
            step={0.05}
            show={(v) => `${Math.round(v * 100)}%`}
            onCommit={(v) => updateSettings({ volume: v })}
          />
          <Slider
            label="Speech speed"
            value={settings.speech_speed}
            min={0.5}
            max={2}
            step={0.1}
            show={(v) => `${v.toFixed(1)}×`}
            onCommit={(v) => updateSettings({ speech_speed: v })}
          />
          <div className="lp-checks">
            <Check label="Beep" checked={settings.beep} onChange={(v) => updateSettings({ beep: v })} />
            <Check
              label="Voice assistance"
              checked={settings.voice}
              onChange={(v) => updateSettings({ voice: v })}
            />
          </div>
        </section>

        <section className="lp-card">
          <h2>
            <Icon name="eye" /> Detection &amp; alerts
          </h2>
          <ul className="lp-list">
            {alerts.map(([k, a]) => (
              <li key={k}>
                <span>{a.title}</span>
                <b className={a.announce ? "lp-mono" : "lp-silent"}>
                  {a.announce ? `${a.alert_at_m} m` : `Silent · ${a.alert_at_m} m`}
                </b>
              </li>
            ))}
          </ul>
          <button className="lp-link" onClick={() => go("alerts")}>
            <Icon name="arrows" />
            <span>
              <b>Edit detection &amp; alerts</b>
              <small>What to detect, announce, and when</small>
            </span>
            <Icon name="chevron" />
          </button>
        </section>

        <section className="lp-card">
          <h2>
            <Icon name="server" /> System
          </h2>
          <button className="lp-row" onClick={() => go("vision")}>
            Vision type <Icon name="chevron" />
          </button>
          <button className="lp-row" onClick={() => go("status")}>
            System status <Icon name="chevron" />
          </button>
          <button className="lp-row" onClick={() => go("lane")}>
            Lane setup <Icon name="chevron" />
          </button>
          <button className="lp-row" onClick={() => go("advanced")}>
            Advanced <Icon name="chevron" />
          </button>
          <button className="lp-row" onClick={() => go("demo")}>
            Demo screens <Icon name="chevron" />
          </button>
          <div className="lp-spacer" />
          <button className="lp-link" onClick={() => go("incidents")}>
            <Icon name="video" />
            <span>
              <b>Saved incidents</b>
              <small>{incidents == null ? "…" : `${incidents} saved`} · 90 s from 4 cameras</small>
            </span>
            <Icon name="chevron" />
          </button>
        </section>
      </div>

      <BackupMode client={client} />

      <button className="lp-danger" onClick={onDisconnect}>
        Stop and change server
      </button>
    </div>
  );
}

/** Slider that shows the value while dragging and saves once the user stops (no flood of requests). */
function Slider(props) {
  const [v, setV] = useState(props.value);
  const timer = useRef();
  useEffect(() => setV(props.value), [props.value]);
  useEffect(() => () => clearTimeout(timer.current), []);
  const change = (n) => {
    setV(n);
    clearTimeout(timer.current);
    timer.current = setTimeout(() => props.onCommit(n), 350);
  };

  return (
    <label className="lp-slider">
      <span className="lp-slider-top">
        <b>{props.label}</b>
        <span className="lp-mono">{props.show(v)}</span>
      </span>
      <input
        type="range"
        min={props.min}
        max={props.max}
        step={props.step}
        value={v}
        onChange={(e) => change(Number(e.target.value))}
      />
    </label>
  );
}

export function Check({ label, checked, onChange, disabled }) {
  return (
    <label className={`lp-check ${disabled ? "disabled" : ""}`}>
      <input
        type="checkbox"
        checked={checked}
        disabled={disabled}
        onChange={(e) => onChange(e.target.checked)}
      />
      <span className="lp-box">{checked && <Icon name="check" size={18} />}</span>
      {label && <span>{label}</span>}
    </label>
  );
}
