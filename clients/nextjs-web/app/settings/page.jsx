"use client";
// "/settings" : slide 34
import { SettingsPage } from "../../src/screens/SettingsPage";
import { useDA, useGo } from "../../src/DAProvider";

export default function Page() {
  const { da } = useDA();
  const go = useGo();
  return <SettingsPage da={da} go={go} onDisconnect={() => go("start")} />;
}
