"use client";
import { RequireConnection } from "../../src/RequireConnection";

export default function SetupLayout({ children }) {
  return <RequireConnection>{children}</RequireConnection>;
}
