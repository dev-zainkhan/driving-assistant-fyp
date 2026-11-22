"use client";
// "/settings/lane" : Lane setup, draw our lane and the road end on the real picture
import { LaneSetupPage } from "../../../src/screens/LaneSetupPage";
import { useDA, useGo } from "../../../src/DAProvider";

export default function Page() {
  const { da } = useDA();
  const go = useGo();
  return <LaneSetupPage da={da} go={go} />;
}
