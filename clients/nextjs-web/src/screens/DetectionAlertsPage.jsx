import { Icon, OBJECT_ICONS } from "../components/Icon";
import { Check } from "./SettingsPage";
import { PageHeader } from "./common";

/** Next value for the minus / plus buttons, kept inside the object's min..max. */
export function stepDistance(a, dir) {
  return Math.min(a.max_m, Math.max(a.min_m, Math.round(a.alert_at_m) + dir));
}

/** Slide 35: for each object, detect it, announce it, at what distance, and whether to show text. */
export function DetectionAlertsPage({ da, go }) {
  const { settings, updateSettings, resetAlerts } = da;
  if (!settings) return null;
  const set = (name, change) => updateSettings({ alerts: { [name]: change } });
  const allRecommended = Object.values(settings.alerts).every((a) => a.alert_at_m === a.recommended_m);

  return (
    <div className="lp">
      <PageHeader
        title="Detection & alerts"
        onBack={() => go("settings")}
        right={
          <button className="lp-btn" onClick={resetAlerts} disabled={allRecommended}>
            <Icon name="reset" /> Reset to recommended
          </button>
        }
      />
      <div className="lp-card lp-table-card">
        <table className="lp-table">
          <thead>
            <tr>
              <th>Object</th>
              <th>Detect</th>
              <th>Announce</th>
              <th>Alert at</th>
              <th>Show text</th>
            </tr>
          </thead>
          <tbody>
            {Object.entries(settings.alerts).map(([name, a]) => (
              <tr key={name} className={a.detect ? "" : "lp-off"}>
                <td>
                  <span className="lp-obj">
                    <span className="lp-obj-icon">
                      <Icon name={OBJECT_ICONS[name] ?? "eye"} />
                    </span>
                    <b>{a.title}</b>
                    {a.is_safety && <span className="lp-badge">Safety</span>}
                    {a.phase > 1 && (
                      <span className="lp-badge lp-badge-later" title="Detection for this comes in phase 3">
                        Later
                      </span>
                    )}
                  </span>
                </td>
                <td>
                  <Check checked={a.detect} onChange={(v) => set(name, { detect: v })} />
                </td>
                <td>
                  <Check checked={a.announce} onChange={(v) => set(name, { announce: v })} />
                </td>
                <td>
                  <span className="lp-stepper">
                    <button
                      className="lp-round"
                      aria-label={`${a.title} closer`}
                      disabled={a.alert_at_m <= a.min_m}
                      onClick={() => set(name, { alert_at_m: stepDistance(a, -1) })}
                    >
                      <Icon name="minus" />
                    </button>
                    <b className="lp-mono">{Math.round(a.alert_at_m)} m</b>
                    <button
                      className="lp-round"
                      aria-label={`${a.title} further`}
                      disabled={a.alert_at_m >= a.max_m}
                      onClick={() => set(name, { alert_at_m: stepDistance(a, 1) })}
                    >
                      <Icon name="plus" />
                    </button>
                  </span>
                </td>
                <td>
                  <Check checked={a.show_text} onChange={(v) => set(name, { show_text: v })} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="lp-note">
        Changes are saved at once on the laptop and used by every screen connected to it.
      </p>
    </div>
  );
}
