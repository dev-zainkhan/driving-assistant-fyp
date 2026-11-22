import { Icon } from "../components/Icon";

export function PageHeader({ title, onBack, right }) {
  return (
    <header className="lp-header">
      <button className="lp-iconbtn" onClick={onBack} aria-label="Back">
        <Icon name="back" />
      </button>
      <h1>{title}</h1>
      <div className="lp-header-right">{right}</div>
    </header>
  );
}
