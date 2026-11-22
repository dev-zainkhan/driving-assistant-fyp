"use client";
// "/settings/alerts" : slide 35
import { DetectionAlertsPage } from "../../../src/screens/DetectionAlertsPage";
import { useDA, useGo } from "../../../src/DAProvider";

export default function Page() {
  const { da } = useDA();
  const go = useGo();
  return <DetectionAlertsPage da={da} go={go} />;
}
