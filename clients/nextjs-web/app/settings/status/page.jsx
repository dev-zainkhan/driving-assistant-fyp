"use client";
// "/settings/status" : slide 44
import { SystemStatusPage } from "../../../src/screens/SystemStatusPage";
import { useDA, useGo } from "../../../src/DAProvider";

export default function Page() {
  const { da } = useDA();
  const go = useGo();
  return <SystemStatusPage da={da} go={go} />;
}
