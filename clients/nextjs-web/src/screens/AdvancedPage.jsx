import { useEffect, useRef, useState } from "react";
import { POSITIONS } from "@da/client";
import { Icon } from "../components/Icon";
import { Check } from "./SettingsPage";
import { PageHeader } from "./common";

const CAMERA_TITLE = { front: "Front", left: "Left", right: "Right", back: "Back" };

/** Group the rows from GET /api/settings/advanced, keeping the server's order. */
export function groupRows(rows) {
  const groups = [];
  for (const r of rows) {
    let g = groups.find((x) => x.name === r.group);
    if (!g) groups.push((g = { name: r.group, rows: [] }));
    g.rows.push(r);
  }
  return groups;
}

/** Keep a typed number inside the allowed range and on the step grid. */
export function clampToStep(value, { min, max, step }) {
  const v = Math.min(max, Math.max(min, value));
  const snapped = Math.round((v - min) / step) * step + min;
  return Math.round(snapped * 1000) / 1000;
}

function NumberRow({ row, onSave }) {
  const [text, setText] = useState(String(row.value));
  useEffect(() => setText(String(row.value)), [row.value]);
  const commit = () => {
    const n = Number(text);
    if (Number.isNaN(n)) return setText(String(row.value));
    const v = clampToStep(n, row);
    setText(String(v));
    if (v !== row.value) onSave(row.name, v);
  };
  const changed = row.value !== row.default;
  return (
    <div className="adv-row">
      <span>
        <b>
          {row.title}{" "}
          {changed && (
            <span className="adv-changed" title={`Default: ${row.default}`}>
              changed
            </span>
          )}
        </b>
        <small>{row.description}</small>
      </span>
      <span className="adv-input">
        <input
          type="number"
          min={row.min}
          max={row.max}
          step={row.step}
          value={text}
          onChange={(e) => setText(e.target.value)}
          onBlur={commit}
          onKeyDown={(e) => e.key === "Enter" && e.currentTarget.blur()}
        />
        <span className="adv-unit">{row.unit === "yes/no" ? "" : row.unit}</span>
      </span>
    </div>
  );
}

/**
 * Settings > Advanced (for the team): every fine-tuning number from the database, grouped,
 * with its range and a plain description, so tuning on real road videos needs no code change.
 */
export function AdvancedPage({ da, go }) {
  const { client, settings, updateSettings } = da;
  const [rows, setRows] = useState(null);
  const [msg, setMsg] = useState(null);
  const msgTimer = useRef();

  const load = () =>
    client
      .getAdvancedSettings()
      .then(setRows)
      .catch((e) => setMsg(e.message));
  useEffect(() => {
    void load();
    return () => clearTimeout(msgTimer.current);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [client]);

  const flash = (text) => {
    setMsg(text);
    clearTimeout(msgTimer.current);
    msgTimer.current = setTimeout(() => setMsg(null), 2500);
  };
  const save = async (name, value) => {
    await updateSettings({ [name]: value });
    await load();
    flash("Saved");
  };
  const resetAll = async () => {
    if (!window.confirm("Put every number on this page back to its default?")) return;
    await client.resetAdvanced();
    await load();
    flash("All numbers are back to their defaults");
  };

  if (!rows || !settings) return <div className="lp" />;
  const changedCount = rows.filter((r) => r.value !== r.default).length;

  return (
    <div className="lp">
      <PageHeader
        title="Advanced"
        onBack={() => go("settings")}
        right={
          <button className="lp-btn" onClick={resetAll} disabled={changedCount === 0}>
            <Icon name="reset" /> Reset all ({changedCount} changed)
          </button>
        }
      />
      <p className="lp-note adv-intro">
        For the team: fine-tuning numbers for testing with real road videos. Changes are saved on the laptop
        and used at once.
      </p>

      <section className="lp-card adv-card">
        <h2>
          <Icon name="camera" /> Cameras
        </h2>
        {POSITIONS.map((p) => (
          <div className="adv-row" key={p}>
            <span>
              <b>{CAMERA_TITLE[p]} camera</b>
              <small>Detections per second, and whether this camera is checked at all</small>
            </span>
            <span className="adv-input">
              <input
                type="number"
                min={0}
                max={30}
                step={1}
                defaultValue={settings.det_fps[p]}
                key={settings.det_fps[p]}
                onBlur={(e) => {
                  const v = clampToStep(Number(e.target.value) || 0, { min: 0, max: 30, step: 1 });
                  if (v !== settings.det_fps[p]) save("det_fps", { ...settings.det_fps, [p]: v });
                }}
                onKeyDown={(e) => e.key === "Enter" && e.currentTarget.blur()}
              />
              <span className="adv-unit">fps</span>
              <Check
                checked={settings.camera_on[p]}
                onChange={(on) => save("camera_on", { ...settings.camera_on, [p]: on })}
              />
            </span>
          </div>
        ))}
      </section>

      {groupRows(rows).map((g) => (
        <section className="lp-card adv-card" key={g.name}>
          <h2>{g.name}</h2>
          {g.rows.map((r) =>
            r.unit === "yes/no" ? (
              <div className="adv-row" key={r.name}>
                <span>
                  <b>{r.title}</b>
                  <small>{r.description}</small>
                </span>
                <Check checked={!!r.value} onChange={(v) => save(r.name, v)} />
              </div>
            ) : (
              <NumberRow key={r.name} row={r} onSave={save} />
            ),
          )}
        </section>
      ))}
      {msg && <div className="adv-flash">{msg}</div>}
    </div>
  );
}
