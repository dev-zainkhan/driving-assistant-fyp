"use client";
// "/settings/incidents/park" : slide 48, videos only open when the car is parked
import { NotWhileDriving } from "../../../../src/screens/PlaybackPage";
import { useGo } from "../../../../src/DAProvider";

export default function Page() {
  const go = useGo();
  return <NotWhileDriving go={go} />;
}
