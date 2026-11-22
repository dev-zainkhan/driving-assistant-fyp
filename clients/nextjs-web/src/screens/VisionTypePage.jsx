import { useEffect, useState } from "react";
import { Icon } from "../components/Icon";
import { PageHeader } from "./common";

export const VISION = [
  {
    key: "peripheral_vision",
    title: "Peripheral vision",
    text: "Hard to see things at the sides",
    icon: "eye",
    changes: [
      "Give the side cameras top priority",
      "Warn earlier about things at your sides",
      "Always say left, right or behind",
    ],
  },
  {
    key: "night_blindness",
    title: "Night blindness",
    text: "Hard to see in low light or at night",
    icon: "eyeOff",
    changes: [
      "Turn night vision on when it gets dark",
      "Use thick, labelled boxes with distances",
      "Speak every orange warning",
    ],
  },
  {
    key: "night_vision",
    title: "Night vision",
    text: "Use the night camera view all the time",
    icon: "moon",
    changes: ["Brighten every camera picture", "Use thick, labelled boxes with distances"],
  },
];

export const SETUP_DONE_KEY = "da.setupDone";

/**
 * Slides 36-43 (from Settings): pick any vision types, see what changes, then Save.
 * Slides 6-13 (setup = true): the same choice right after Start, the first time only;
 * Continue goes on to the System check.
 */
export function VisionTypePage({ da, go, setup = false }) {
  const { settings, updateSettings } = da;
  const [chosen, setChosen] = useState(settings?.vision ?? null);
  useEffect(() => {
    if (settings && !chosen) setChosen(settings.vision);
  }, [settings, chosen]);
  if (!chosen) return null;
  const picked = VISION.filter((v) => chosen[v.key]);
  const save = async () => {
    await updateSettings({ vision: chosen });
    if (setup) {
      try {
        localStorage.setItem(SETUP_DONE_KEY, "1");
      } catch {
        /* ignore */
      }
      go("check");
    } else go("settings");
  };

  return (
    <div className="lp">
      {setup ? (
        <header className="lp-header lp-header-setup">
          <h1>Your vision type</h1>
          <p className="lp-note">Pick any that apply, or none. The panel shows what the app will change.</p>
        </header>
      ) : (
        <PageHeader title="Vision type" onBack={() => go("settings")} />
      )}
      <div className="lp-split">
        <div className="lp-stack">
          {VISION.map((v) => (
            <label key={v.key} className={`lp-option ${chosen[v.key] ? "on" : ""}`}>
              <input
                type="checkbox"
                checked={chosen[v.key]}
                onChange={(e) => setChosen({ ...chosen, [v.key]: e.target.checked })}
              />
              <span className="lp-box">{chosen[v.key] && <Icon name="check" size={18} />}</span>
              <span className="lp-obj-icon">
                <Icon name={v.icon} />
              </span>
              <span>
                <b>{v.title}</b>
                <small>{v.text}</small>
              </span>
            </label>
          ))}
        </div>
        <div className="lp-card lp-changes">
          <h3>What changes</h3>
          {picked.length === 0 ? (
            <p className="lp-big">No vision type chosen: the app uses the normal settings.</p>
          ) : (
            picked.map((v) => (
              <div key={v.key}>
                <p className="lp-big">With {v.title.toLowerCase()}, the app will:</p>
                <ul>
                  {v.changes.map((c) => (
                    <li key={c}>
                      <Icon name="check" size={18} /> {c}
                    </li>
                  ))}
                </ul>
              </div>
            ))
          )}
          <div className="lp-spacer" />
          <button className="lp-primary" onClick={save}>
            <Icon name="check" /> {setup ? "Continue" : "Save"}
          </button>
        </div>
      </div>
    </div>
  );
}
