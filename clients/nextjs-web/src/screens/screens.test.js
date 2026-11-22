import { describe, expect, it } from "vitest";
import { mergeSettings } from "../hooks/useDrivingAssistant";
import { stepDistance } from "./DetectionAlertsPage";
import { CAUSE_TEXT } from "./IncidentsPage";
import { VISION } from "./VisionTypePage";

describe("detection & alerts minus / plus", () => {
  const vehicles = { alert_at_m: 20, min_m: 5, max_m: 20 };
  it("stops at the max (slide 35: plus is off at 20 m for vehicles)", () => {
    expect(stepDistance(vehicles, 1)).toBe(20);
    expect(stepDistance(vehicles, -1)).toBe(19);
  });

  it("stops at the min", () => {
    expect(stepDistance({ alert_at_m: 2, min_m: 2, max_m: 15 }, -1)).toBe(2);
  });
});

describe("instant settings update", () => {
  it("deep-merges a nested change and keeps the rest", () => {
    const base = {
      volume: 0.8,
      alerts: { people: { alert_at_m: 6, announce: true }, vehicles: { alert_at_m: 20, announce: true } },
    };
    const out = mergeSettings(base, { alerts: { people: { alert_at_m: 8 } } });
    expect(out.alerts.people).toEqual({ alert_at_m: 8, announce: true });
    expect(out.alerts.vehicles.alert_at_m).toBe(20);
    expect(out.volume).toBe(0.8);
    expect(base.alerts.people.alert_at_m).toBe(6); // original not changed
  });
});

describe("texts from the slides", () => {
  it("has the three incident causes of slide 46", () => {
    expect(Object.values(CAUSE_TEXT)).toEqual(["Sudden brake", "Hard jolt", "Saved by driver"]);
  });

  it("has the three vision types of slide 36", () => {
    expect(VISION.map((v) => v.title)).toEqual(["Peripheral vision", "Night blindness", "Night vision"]);
    expect(VISION[0].changes[0]).toBe("Give the side cameras top priority");
  });
});

import { clampToStep, groupRows } from "./AdvancedPage";

describe("advanced settings", () => {
  it("groups rows in server order", () => {
    const g = groupRows([
      { name: "a", group: "Cars" },
      { name: "b", group: "Voice" },
      { name: "c", group: "Cars" },
    ]);
    expect(g.map((x) => x.name)).toEqual(["Cars", "Voice"]);
    expect(g[0].rows.map((r) => r.name)).toEqual(["a", "c"]);
  });
  it("keeps typed numbers inside the range and on the step", () => {
    const r = { min: 1, max: 8, step: 0.5 };
    expect(clampToStep(99, r)).toBe(8);
    expect(clampToStep(0, r)).toBe(1);
    expect(clampToStep(3.3, r)).toBe(3.5);
  });
});
