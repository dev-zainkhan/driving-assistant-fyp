"use client";
// "/settings/incidents" : slide 46
import { IncidentsPage } from "../../../src/screens/IncidentsPage";
import { useDA, useGo } from "../../../src/DAProvider";

export default function Page() {
  const { da } = useDA();
  const go = useGo();
  return <IncidentsPage da={da} go={go} />;
}
