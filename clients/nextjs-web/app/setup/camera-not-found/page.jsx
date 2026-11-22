"use client";
// "/setup/camera-not-found?missing=left,back" : slide 15
import { Suspense } from "react";
import { useSearchParams } from "next/navigation";
import { CameraNotFoundPage } from "../../../src/screens/SetupPages";
import { useDA, useGo } from "../../../src/DAProvider";

function NotFound() {
  const { da } = useDA();
  const go = useGo();
  const missing = (useSearchParams().get("missing") ?? "").split(",").filter(Boolean);
  return <CameraNotFoundPage da={da} go={go} missing={missing} />;
}

export default function Page() {
  return (
    <Suspense>
      <NotFound />
    </Suspense>
  );
}
