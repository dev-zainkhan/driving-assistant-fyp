import { useState } from "react";
import { DrivingAssistantClient } from "@da/client";
import { unlockSpeech } from "../hooks/useVoice";

/** Slide 5: one big "Start Driving Assistant" button, plus the server address. */
export function StartScreen({ initialServer, onStart }) {
  const [server, setServer] = useState(initialServer);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const start = async () => {
    setBusy(true);
    setError(null);
    unlockSpeech(); // must happen inside the click so the browser allows voice later
    try {
      const h = await new DrivingAssistantClient({ baseUrl: server }).getHealth();
      if (h.status !== "ok") throw new Error("server not ready");
      onStart(server);
    } catch {
      setError(`Cannot reach the server at ${server}. Is it running, and on the same Wi-Fi?`);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="start">
      <div className="start-card">
        <div className="logo" aria-hidden="true">
          <svg viewBox="0 0 64 64" width="72" height="72">
            <path
              d="M12 40l6-16c1-3 3-4 6-4h16c3 0 5 1 6 4l6 16v10h-6v-4H18v4h-6V40z"
              fill="none"
              stroke="currentColor"
              strokeWidth="3"
              strokeLinejoin="round"
            />
            <circle cx="21" cy="40" r="3" fill="currentColor" />
            <circle cx="43" cy="40" r="3" fill="currentColor" />
          </svg>
        </div>
        <h1>Driving Assistant</h1>
        <button className="start-btn" onClick={start} disabled={busy}>
          {busy ? "Connecting…" : "Start Driving Assistant"}
        </button>
        <label className="server-field">
          Server address
          <input
            value={server}
            onChange={(e) => setServer(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && start()}
            spellCheck={false}
          />
        </label>
        {error && <p className="error">{error}</p>}
      </div>
    </div>
  );
}
