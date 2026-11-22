"use client";
// "/setup/check" : slide 14. ?t=... changes on every Try again, which restarts the check.
import { Suspense } from "react";
import { useSearchParams } from "next/navigation";
import { SystemCheckPage } from "../../../src/screens/SetupPages";
import { useDA, useGo } from "../../../src/DAProvider";

function Check() {
  const { da } = useDA();
  const go = useGo();
  const t = useSearchParams().get("t") ?? "0";
  return <SystemCheckPage key={t} da={da} go={go} />;
}

export default function Page() {
  return (
    <Suspense>
      <Check />
    </Suspense>
  );
}
