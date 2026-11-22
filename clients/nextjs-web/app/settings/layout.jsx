"use client";
// Shared by every /settings/... page: needs a connection, and shows a small red message
// when a setting could not be saved.
import { RequireConnection } from "../../src/RequireConnection";

export default function SettingsLayout({ children }) {
  return <RequireConnection showErrors>{children}</RequireConnection>;
}
