import { Icon } from "./Icon";

/** Slides 26-28: banner at the top left of the front view. Red for a red light, blue for signs. */
export function SignBanner({ kind, title, text }) {
  return (
    <div className={`sign-banner sign-${kind}`} role="status">
      <span className="sign-icon">
        <Icon name={kind === "red" ? "light" : "board"} size={26} />
      </span>
      <span>
        <b>{title}</b>
        {text && <small>{text}</small>}
      </span>
    </div>
  );
}

const CAUSE = { sudden_brake: "sudden brake", hard_jolt: "hard jolt", saved_by_driver: "saved by driver" };

/** Slide 45: short notice at the top of the live view after an incident was saved. */
export function IncidentNotice({ cause, onOpen }) {
  return (
    <div className="incident-notice" role="status" onClick={(e) => e.stopPropagation()}>
      <span className="incident-notice-icon">
        <Icon name="video" size={22} />
      </span>
      <span>
        <b>Incident saved{CAUSE[cause] ? ` · ${CAUSE[cause]}` : ""}</b>
        <small>Last 90 s from all 4 cameras · Settings › Saved incidents</small>
      </span>
      {onOpen && (
        <button onClick={onOpen} className="incident-notice-btn">
          View
        </button>
      )}
    </div>
  );
}
