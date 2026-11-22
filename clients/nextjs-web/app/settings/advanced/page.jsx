"use client";
// "/settings/advanced" : every fine-tuning number from the database (for the team)
import { AdvancedPage } from "../../../src/screens/AdvancedPage";
import { useDA, useGo } from "../../../src/DAProvider";

export default function Page() {
  const { da } = useDA();
  const go = useGo();
  return <AdvancedPage da={da} go={go} />;
}
