/** FR-V4: tapping shows only two buttons, Windscreen (AR mirror) and Settings. */
export function TapMenu({ visible, mirrored, onWindscreen, onSettings }) {
  return (
    <div className={`tap-menu ${visible ? "show" : ""}`} onClick={(e) => e.stopPropagation()}>
      <button
        className={`round ${mirrored ? "active" : ""}`}
        onClick={onWindscreen}
        aria-label="Windscreen mirror"
        title="Windscreen (AR mirror)"
      >
        <svg viewBox="0 0 24 24" width="26" height="26" aria-hidden="true">
          <path
            d="M3 8c3-2 15-2 18 0l-2 9H5L3 8z"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinejoin="round"
          />
          <path d="M9 12h6M12 9v6" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
        </svg>
      </button>
      <button className="round" onClick={onSettings} aria-label="Settings" title="Settings">
        <svg viewBox="0 0 24 24" width="26" height="26" aria-hidden="true">
          <circle cx="12" cy="12" r="3.2" fill="none" stroke="currentColor" strokeWidth="2" />
          <path
            d="M12 2.5v3M12 18.5v3M2.5 12h3M18.5 12h3M5.3 5.3l2.1 2.1M16.6 16.6l2.1 2.1M5.3 18.7l2.1-2.1M16.6 7.4l2.1-2.1"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
          />
        </svg>
      </button>
    </div>
  );
}
