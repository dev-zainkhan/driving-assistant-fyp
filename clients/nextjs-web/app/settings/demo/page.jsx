"use client";
// "/settings/demo" : every screen of the app map, with sample data where detection comes later
import { DEMOS } from "../../../src/demo";
import { DemoPage } from "../../../src/screens/DemoPage";
import { useDA, useGo } from "../../../src/DAProvider";

export default function Page() {
  const { da, setDemo } = useDA();
  const go = useGo();
  return (
    <DemoPage
      da={da}
      go={go}
      onDemo={(key) => {
        setDemo(DEMOS[key]);
        go("live");
      }}
    />
  );
}
