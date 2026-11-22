"use client";
// "/settings/vision" : slides 36-43
import { VisionTypePage } from "../../../src/screens/VisionTypePage";
import { useDA, useGo } from "../../../src/DAProvider";

export default function Page() {
  const { da } = useDA();
  const go = useGo();
  return <VisionTypePage da={da} go={go} />;
}
