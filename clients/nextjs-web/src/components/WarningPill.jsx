export function WarningPill({ level, text, compact }) {
  // Side strips are narrow: show only the object name ("Car"), like the slides.
  const shown = compact ? text.replace(/ on (left|right)$/, "") : text;

  return (
    <div className={`pill pill-${level}`} role="alert">
      <svg viewBox="0 0 24 24" width="1em" height="1em" aria-hidden="true">
        <path d="M12 3 2 21h20L12 3z" fill="currentColor" />
        <path d="M12 10v5M12 17.5v.5" stroke="var(--pill-bg)" strokeWidth="2.2" strokeLinecap="round" />
      </svg>
      <span>{shown}</span>
    </div>
  );
}
