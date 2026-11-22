"use client";
// "/" : Start screen (slide 5), then the live view with the four cameras (slides 16-30).
import { LiveView } from "../src/components/LiveView";
import { StartScreen } from "../src/components/StartScreen";
import { defaultServer, firstPageAfterStart, rememberServer, useDA, useGo } from "../src/DAProvider";

export default function HomePage() {
  const { server, setServer, da, demo, setDemo } = useDA();
  const go = useGo();

  if (!server || !da) {
    return (
      <StartScreen
        initialServer={defaultServer()}
        onStart={(s) => {
          rememberServer(s);
          setServer(s);
          go(firstPageAfterStart()); // first time: vision type, later: system check
        }}
      />
    );
  }
  return (
    <LiveView
      da={da}
      onSettings={() => go("settings")}
      demo={demo}
      onDemoEnd={() => setDemo(null)}
      onOpenIncident={(id) => go("playback", id)}
    />
  );
}
