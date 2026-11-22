"use client";
// "/settings/incidents/7" : slide 47, watch an incident (or slide 48 while driving)
import { useParams } from "next/navigation";
import { PlaybackPage } from "../../../../src/screens/PlaybackPage";
import { useDA, useGo } from "../../../../src/DAProvider";

export default function Page() {
  const { da } = useDA();
  const go = useGo();
  const { id } = useParams();
  return <PlaybackPage da={da} go={go} id={Number(id)} />;
}
