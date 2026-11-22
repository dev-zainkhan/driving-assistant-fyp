import { describe, expect, it } from "vitest";
import {
  coverCrop,
  DrivingAssistantClient,
  fromHex,
  mapBox,
  packCameraFrame,
  packViewerFrame,
  parseViewerFrame,
  ProtocolError,
  toHex,
  unpackCameraFrame,
  wsUrl,
} from "../src";

// Same byte fixtures as server/tests/test_protocol.py and docs/protocol.md
const CAMERA_FIXTURE_HEX = "01012a0000000000d0cdb2a979420000ffd8ffd9";

const VIEWER_FIXTURE_HEX = "01010200070000000000000000428f4000000000004c8f404a504547";

describe("binary protocol", () => {
  it("packs a camera frame identical to Python", () => {
    expect(toHex(packCameraFrame(42, 1763540000000.0, fromHex("ffd8ffd9")))).toBe(CAMERA_FIXTURE_HEX);
  });

  it("unpacks the camera fixture", () => {
    const f = unpackCameraFrame(fromHex(CAMERA_FIXTURE_HEX));
    expect(f.seq).toBe(42);
    expect(f.captureTsMs).toBe(1763540000000.0);
    expect(toHex(f.jpeg)).toBe("ffd8ffd9");
  });

  it("parses the viewer fixture from Python", () => {
    const f = parseViewerFrame(fromHex(VIEWER_FIXTURE_HEX));
    expect(f.camera).toBe("right");
    expect(f.seq).toBe(7);
    expect(f.captureTsMs).toBe(1000.25);
    expect(f.serverTsMs).toBe(1001.5);
    expect(new TextDecoder().decode(f.jpeg)).toBe("JPEG");
  });

  it("round-trips a viewer frame", () => {
    const bytes = packViewerFrame("back", 123456, 1.5, 2.5, new Uint8Array([1, 2, 3]));
    expect(toHex(bytes)).toBe(toHex(packViewerFrame("back", 123456, 1.5, 2.5, new Uint8Array([1, 2, 3]))));
    const f = parseViewerFrame(bytes.buffer);
    expect([f.camera, f.seq, f.captureTsMs, f.serverTsMs, Array.from(f.jpeg)]).toEqual([
      "back",
      123456,
      1.5,
      2.5,
      [1, 2, 3],
    ]);
  });

  it("rejects bad frames", () => {
    expect(() => parseViewerFrame(new Uint8Array(5))).toThrow(ProtocolError);
    expect(() => unpackCameraFrame(fromHex("0201" + "00".repeat(20)))).toThrow(ProtocolError);
  });
});

describe("labels", () => {
  it("knows the group of each class", async () => {
    const { groupOf } = await import("../src/draw");
    expect(groupOf("person")).toBe("people");
    expect(groupOf("bus")).toBe("vehicles");
    expect(groupOf("pothole")).toBe("pothole");
  });
  it("builds incident file URLs", () => {
    const c = new DrivingAssistantClient({ baseUrl: "h:8000" });
    expect(c.incidentVideoUrl(7, "left")).toBe("http://h:8000/api/incidents/7/video/left");
    expect(c.incidentPictureUrl(7)).toBe("http://h:8000/api/incidents/7/picture");
  });
});

describe("drawing maths", () => {
  it("cover crop takes the centre of a 16:9 frame for a tall slot", () => {
    const c = coverCrop(640, 360, 100, 400);
    expect(c.sh).toBe(360);
    expect(c.sw).toBeCloseTo(90);
    expect(c.sx).toBeCloseTo(275);
  });

  it("keeps the road in view in a wide, short slot (back camera)", async () => {
    const { roadFocus } = await import("../src/draw");
    const focus = roadFocus([
      [0.2, 1],
      [0.8, 1],
      [0.55, 0.45],
      [0.45, 0.45],
    ]);
    expect(focus).toBeCloseTo(0.725);
    const c = coverCrop(640, 360, 1000, 260, focus); // slot much wider than 16:9
    expect(c.sy + c.sh).toBeGreaterThan(300); // shows the lower part of the picture
    expect(c.sy).toBeGreaterThan(100); // not the sky at the top
    expect(coverCrop(640, 360, 1000, 260, 0.99).sy + coverCrop(640, 360, 1000, 260, 0.99).sh).toBe(360); // never past the bottom
  });

  it("maps a normalised box through the crop", () => {
    const crop = coverCrop(640, 360, 640, 360); // no crop
    expect(mapBox([0.5, 0.5, 1, 1], crop, 640, 360, 320, 180)).toEqual([160, 90, 320, 180]);
  });
});

describe("client", () => {
  it("sends PATCH with JSON and reads errors", async () => {
    const calls = [];
    const fakeFetch = async (url, init) => {
      calls.push({ url, init });
      if (init.method === "PATCH" && String(init.body).includes("99")) {
        return new Response(JSON.stringify({ error: { code: "INVALID_SETTING", message: "too far" } }), {
          status: 400,
        });
      }
      return new Response(JSON.stringify({ volume: 0.5 }), { status: 200 });
    };
    const c = new DrivingAssistantClient({ baseUrl: "h:8000", fetchImpl: fakeFetch });
    const s = await c.patchSettings({ volume: 0.5 });
    expect(s.volume).toBe(0.5);
    expect(calls[0].url).toBe("http://h:8000/api/settings");
    expect(calls[0].init.method).toBe("PATCH");
    expect(JSON.parse(String(calls[0].init.body))).toEqual({ volume: 0.5 });
    await expect(c.patchSettings({ alerts: { people: { alert_at_m: 99 } } })).rejects.toThrow("too far");
  });

  it("builds ws urls", () => {
    expect(wsUrl("192.168.1.5:8000", "/ws/viewer")).toBe("ws://192.168.1.5:8000/ws/viewer");
    expect(wsUrl("https://x.test/", "/ws/viewer")).toBe("wss://x.test/ws/viewer");
  });

  it("tracks state from messages", () => {
    const c = new DrivingAssistantClient({ baseUrl: "localhost:8000" });
    const frames = [];
    const overlays = [];
    c.on("frame", (f) => frames.push(f));
    c.on("overlay", (o) => overlays.push(o));
    c.handle(
      JSON.stringify({
        type: "welcome",
        protocol: 1,
        server_version: "0.1.0",
        cameras: [{ position: "front", status: "online" }],
        settings: { voice: true },
      }),
    );
    expect(c.cameras.front).toBe("online");
    c.handle(JSON.stringify({ type: "camera_status", position: "left", status: "online" }));
    expect(c.cameras.left).toBe("online");
    c.handle(
      JSON.stringify({
        type: "warning_state",
        ts: 1,
        cameras: { right: { level: "danger", codes: ["VEHICLE_RIGHT"], text: "Car on right", since: 1 } },
      }),
    );
    expect(c.warnings.right.level).toBe("danger");
    expect(c.warnings.front.level).toBe("none");
    c.handle(fromHex(VIEWER_FIXTURE_HEX).buffer);
    c.handle(
      JSON.stringify({
        type: "overlay",
        camera: "right",
        seq: 7,
        det_seq: 7,
        objects: [],
        warning: { level: "danger", codes: [], text: "" },
      }),
    );
    expect(frames[0].camera).toBe("right");
    expect(overlays[0].seq).toBe(frames[0].seq);
    const seen = [];
    c.on("settings", (m) => seen.push(m.settings.volume));
    c.handle(JSON.stringify({ type: "settings", settings: { volume: 0.4 } }));
    expect(seen).toEqual([0.4]);
    expect(c.settings?.volume).toBe(0.4);
    c.handle("not json");
  });

  it("reconnects with backoff using an injected WebSocket", async () => {
    const created = [];
    class FakeWS {
      url;
      static OPEN = 1;
      readyState = 0;
      binaryType = "";
      sent = [];
      onopen = null;
      onclose = null;
      onmessage = null;
      onerror = null;
      constructor(url) {
        this.url = url;
        created.push(this);
      }
      send(d) {
        this.sent.push(d);
      }
      close() {
        this.onclose?.();
      }
    }
    const c = new DrivingAssistantClient({ baseUrl: "h:1", backoffMs: [5], WebSocketImpl: FakeWS });
    const states = [];
    c.on("connection", (s) => states.push(s));
    c.connect();
    created[0].readyState = 1;
    created[0].onopen?.();
    expect(JSON.parse(created[0].sent[0])).toEqual({ type: "subscribe", video: "auto" });
    created[0].onclose?.();
    await new Promise((r) => setTimeout(r, 20));
    expect(created.length).toBe(2);
    expect(states).toEqual(["connecting", "open", "reconnecting"]);
    c.close();
    expect(c.connection).toBe("closed");
  });
});
