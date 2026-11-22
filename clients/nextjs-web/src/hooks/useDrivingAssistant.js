import { useCallback, useEffect, useMemo, useState } from "react";
import { DrivingAssistantClient } from "@da/client";

/** Deep-merge a patch into settings for an instant (optimistic) screen update. */
export function mergeSettings(base, patch) {
  if (!patch || typeof patch !== "object" || Array.isArray(patch)) return patch;
  const out = { ...base };
  for (const [k, v] of Object.entries(patch)) {
    const cur = out[k];
    out[k] =
      v && typeof v === "object" && !Array.isArray(v) && cur && typeof cur === "object"
        ? mergeSettings(cur, v)
        : v;
  }
  return out;
}

/** Wraps @da/client. Frames and overlays are NOT React state (30 fps); slots subscribe directly. */
export function useDrivingAssistant(baseUrl) {
  const client = useMemo(() => new DrivingAssistantClient({ baseUrl, video: "auto" }), [baseUrl]);
  const [connection, setConnection] = useState(client.connection);
  const [cameras, setCameras] = useState(client.cameras);
  const [warnings, setWarnings] = useState(client.warnings);
  const [settings, setSettings] = useState(client.settings);
  const [stats, setStats] = useState(null);
  const [error, setError] = useState(null);
  useEffect(() => {
    const offs = [
      client.on("connection", (s) => {
        setConnection(s);
        setCameras({ ...client.cameras });
      }),
      client.on("welcome", () => {
        setCameras({ ...client.cameras });
        setSettings(client.settings);
      }),
      client.on("settings", (m) => setSettings(m.settings)),
      client.on("camera_status", () => setCameras({ ...client.cameras })),
      client.on("warning_state", () => setWarnings({ ...client.warnings })),
      client.on("stats", (m) => setStats(m)),
    ];
    client.connect();
    return () => {
      offs.forEach((off) => off());
      client.close();
    };
  }, [client]);
  const updateSettings = useCallback(
    async (patch) => {
      setSettings((cur) => (cur ? mergeSettings(cur, patch) : cur));
      try {
        setSettings(await client.patchSettings(patch));
        setError(null);
      } catch (e) {
        setError(e.message);
        client
          .getSettings()
          .then(setSettings)
          .catch(() => {}); // undo the instant change
      }
    },
    [client],
  );
  const resetAlerts = useCallback(async () => {
    try {
      setSettings(await client.resetAlerts());
    } catch (e) {
      setError(e.message);
    }
  }, [client]);
  return {
    client,
    connection,
    cameras,
    warnings,
    settings,
    stats,
    updateSettings,
    resetAlerts,
    error,
    clearError: () => setError(null),
  };
}
