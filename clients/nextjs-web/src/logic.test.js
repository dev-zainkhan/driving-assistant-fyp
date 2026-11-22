import { describe, expect, it } from "vitest";
import { newVoiceState, nextAnnouncement, slotShowsVideo, spokenText } from "./logic";

const w = (level, codes = [], text = "") => ({ level, codes, text, since: 0 });

const settings = {
  voice: true,
  voice_gap_s: 4,
  voice_repeat_s: 15,
  alerts: {
    people: { detect: true, announce: true, alert_at_m: 6, show_text: false },
    vehicles: { detect: true, announce: true, alert_at_m: 20, show_text: false },
  },
};

describe("slot visibility (constant layout)", () => {
  it("front always shows video", () => {
    expect(slotShowsVideo("front", w("none"))).toBe(true);
  });

  it("side and back are black unless warning", () => {
    expect(slotShowsVideo("left", w("none"))).toBe(false);
    expect(slotShowsVideo("back", undefined)).toBe(false);
    expect(slotShowsVideo("right", w("caution"))).toBe(true);
    expect(slotShowsVideo("back", w("danger"))).toBe(true);
  });
});

describe("voice", () => {
  const car = (pos = "right") => ({ [pos]: w("danger", ["VEHICLE_RIGHT"], "Car on right") });
  it("makes natural sentences", () => {
    expect(spokenText(w("danger", [], "Car on left"))).toBe("Car on the left");
    expect(spokenText(w("danger", [], "Person ahead, 5 m"))).toBe("Person ahead, 5 metres");
  });

  it("speaks a new orange warning once while it stays active", () => {
    const s = newVoiceState();
    expect(nextAnnouncement(s, car(), settings, 0)).toBe("Car on the right");
    expect(nextAnnouncement(s, car(), settings, 20000)).toBeNull();
  });

  it("ignores yellow warnings", () => {
    expect(
      nextAnnouncement(newVoiceState(), { left: w("caution", ["VEHICLE_LEFT"], "Car on left") }, settings, 0),
    ).toBeNull();
  });

  it("does not repeat the same warning within voice_repeat_s (flicker)", () => {
    const s = newVoiceState();
    nextAnnouncement(s, car(), settings, 0);
    nextAnnouncement(s, { right: w("caution", ["VEHICLE_RIGHT"], "Car on right") }, settings, 1000); // drops to yellow
    expect(nextAnnouncement(s, car(), settings, 2000)).toBeNull(); // back to orange: still quiet
    nextAnnouncement(s, { right: w("none") }, settings, 3000);
    expect(nextAnnouncement(s, car(), settings, 16000)).toBe("Car on the right"); // after 15 s: ok
  });

  it("keeps a gap between sentences and does not save skipped ones for later", () => {
    const s = newVoiceState();
    expect(nextAnnouncement(s, car(), settings, 0)).not.toBeNull();
    const person = {
      right: w("danger", ["VEHICLE_RIGHT"], "Car on right"),
      front: w("danger", ["PERSON_AHEAD"], "Person ahead, 4 m"),
    };
    expect(nextAnnouncement(s, person, settings, 1000)).toBeNull(); // within 4 s gap: skipped
    expect(nextAnnouncement(s, person, settings, 6000)).toBeNull(); // not spoken late either
  });

  it("never interrupts: skips while speech is busy", () => {
    const s = newVoiceState();
    expect(nextAnnouncement(s, car(), settings, 0, true)).toBeNull();
    expect(nextAnnouncement(s, car(), settings, 500, false)).toBeNull(); // same warning, already handled
  });

  it("stays quiet when voice is off or announce is off", () => {
    const st = { front: w("danger", ["PERSON_AHEAD"], "Person ahead, 4 m") };
    expect(nextAnnouncement(newVoiceState(), st, { ...settings, voice: false }, 0)).toBeNull();
    const noPeople = {
      ...settings,
      alerts: { ...settings.alerts, people: { ...settings.alerts.people, announce: false } },
    };
    expect(nextAnnouncement(newVoiceState(), st, noPeople, 0)).toBeNull();
  });
});
import { autoPick } from "./components/BackupMode";

describe("backup mode", () => {
  it("picks videos by position name", () => {
    const v = (path) => ({ path, name: path.split("/").pop(), size_mb: 1 });
    expect(autoPick([v("videos/test/front.mp4"), v("videos/road_LEFT.mov"), v("videos/other.mp4")])).toEqual({
      front: "videos/test/front.mp4",
      left: "videos/road_LEFT.mov",
    });
  });
});

import { isDriving, missingCameras, missingText } from "./logic";

describe("setup flow", () => {
  it("lists missing cameras and says it like slide 15", () => {
    const cams = { front: "online", left: "offline", right: "online", back: "offline" };
    expect(missingCameras(cams)).toEqual(["left", "back"]);
    expect(missingText(["left"])).toBe("Left camera not found");
    expect(missingText(["left", "back"])).toBe("Left and back cameras not found");
    expect(missingText(["front", "left", "back"])).toBe("Front, left and back cameras not found");
    expect(missingText([])).toBe("All cameras found");
  });
  it("treats streaming cameras as driving (slide 48)", () => {
    expect(isDriving(null)).toBe(false);
    expect(isDriving({ cameras: { front: { status: "online", in_fps: 30 } } })).toBe(true);
    expect(isDriving({ cameras: { front: { status: "offline", in_fps: 0 } } })).toBe(false);
  });
});

import { laneFromSliders, slidersFromLane } from "./logic";

describe("lane setup", () => {
  it("builds the default lane shape from sliders", () => {
    const lane = laneFromSliders({ horizon: 0.45, width: 0.64, centre: 0.5 });
    expect(lane[0]).toEqual([0.18, 1]);
    expect(lane[1]).toEqual([0.82, 1]);
    expect(lane[2][1]).toBe(0.45);
    expect(lane[3][0]).toBeLessThan(0.5);
  });
  it("makes the people zone wider", () => {
    const cars = laneFromSliders({ horizon: 0.7, width: 0.5, centre: 0.5 });
    const people = laneFromSliders({ horizon: 0.7, width: 0.5, centre: 0.5 }, "people");
    expect(people[1][0] - people[0][0]).toBeGreaterThan(cars[1][0] - cars[0][0]);
  });
  it("reads the sliders back from a saved lane", () => {
    const s = { horizon: 0.73, width: 0.6, centre: 0.48 };
    expect(slidersFromLane(laneFromSliders(s))).toEqual(s);
  });
});
