"use client";
// "/setup/vision" : slides 6-13, first start only
import { VisionTypePage } from "../../../src/screens/VisionTypePage";
import { useDA, useGo } from "../../../src/DAProvider";

export default function Page() {
  const { da } = useDA();
  const go = useGo();
  return <VisionTypePage da={da} go={go} setup />;
}
