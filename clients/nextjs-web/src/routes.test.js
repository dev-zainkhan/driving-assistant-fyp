import { existsSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import { ROUTES } from "./DAProvider";

const appDir = join(dirname(fileURLToPath(import.meta.url)), "..", "app");

/** "/settings/incidents/7?x=1" -> app/settings/incidents/[id]/page.jsx (or the static folder) */
function pageFile(url) {
  const parts = url.split("?")[0].split("/").filter(Boolean);
  const direct = join(appDir, ...parts, "page.jsx");
  if (existsSync(direct)) return direct;
  return join(appDir, ...parts.slice(0, -1), "[id]", "page.jsx");
}

describe("Next.js routes", () => {
  it("has a URL for every screen of the app map", () => {
    expect(Object.keys(ROUTES).sort()).toEqual([
      "advanced",
      "alerts",
      "camera-missing",
      "check",
      "demo",
      "incidents",
      "lane",
      "live",
      "not-driving",
      "playback",
      "settings",
      "setup-vision",
      "status",
      "vision",
    ]);
  });

  it("has a page file for every URL", () => {
    const params = { playback: 7, "camera-missing": ["left"] };
    for (const [name, route] of Object.entries(ROUTES)) {
      const url = route(params[name]);
      expect(existsSync(pageFile(url)), `${name}: ${url}`).toBe(true);
    }
  });

  it("builds URLs with their parameters", () => {
    expect(ROUTES.playback(7)).toBe("/settings/incidents/7");
    expect(ROUTES["camera-missing"](["left", "back"])).toBe("/setup/camera-not-found?missing=left,back");
    expect(ROUTES.check()).toMatch(/^\/setup\/check\?t=\d+$/);
  });
});
