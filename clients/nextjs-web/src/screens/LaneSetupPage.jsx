import { useEffect, useRef, useState } from "react";
import { drawZone } from "@da/client";
import { Icon } from "../components/Icon";
import { laneFromSliders, slidersFromLane } from "../logic";
import { PageHeader } from "./common";

const DEFAULT = { horizon: 0.45, width: 0.64, centre: 0.5 };
const CAMERAS = [
  ["front", "Front camera"],
  ["back", "Back camera"],
];

function Slider({ label, hint, value, min, max, onChange }) {
  return (
    <label className="lp-slider">
      <span className="lp-slider-top">
        <b>{label}</b>
        <span className="lp-mono">{Math.round(value * 100)}%</span>
      </span>
      <input
        type="range"
        min={min}
        max={max}
        step={0.005}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
      />
      <small>{hint}</small>
    </label>
  );
}

/**
 * Settings > Lane setup. Every phone is mounted a bit differently, so the "own lane" area
 * (only cars inside it can warn; parked cars and oncoming traffic stay white) is set per
 * camera on its live picture: move Horizon to where the road ends, then fit the width.
 */
export function LaneSetupPage({ da, go }) {
  const { client, settings, updateSettings, cameras } = da;
  const [camera, setCamera] = useState("front");
  const [vals, setVals] = useState(null);
  const [saved, setSaved] = useState(false);
  const canvasRef = useRef(null);
  const bitmapRef = useRef(null);
  const valsRef = useRef(vals);
  valsRef.current = vals;

  // load the saved lane of the chosen camera
  useEffect(() => {
    if (!settings) return;
    setVals(slidersFromLane(settings.zones?.[`${camera}_vehicles`]?.polygon));
    setSaved(false);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [camera, settings === null]);

  // live picture of that camera (ask the server for every camera while this page is open)
  useEffect(() => {
    client.setVideoMode("all");
    let busy = false;
    const off = client.on("frame", (f) => {
      if (f.camera !== camera || busy) return;
      busy = true;
      createImageBitmap(new Blob([f.jpeg], { type: "image/jpeg" }))
        .then((bmp) => {
          bitmapRef.current?.close();
          bitmapRef.current = bmp;
        })
        .catch(() => {})
        .finally(() => (busy = false));
    });
    let raf = 0;
    const draw = () => {
      raf = requestAnimationFrame(draw);
      const canvas = canvasRef.current;
      const v = valsRef.current;
      if (!canvas || !v) return;
      const ctx = canvas.getContext("2d");
      const W = canvas.width,
        H = canvas.height;
      ctx.fillStyle = "#111";
      ctx.fillRect(0, 0, W, H);
      if (bitmapRef.current) ctx.drawImage(bitmapRef.current, 0, 0, W, H);
      const crop = { sx: 0, sy: 0, sw: W, sh: H };
      drawZone(ctx, laneFromSliders(v, "people"), crop, W, H, W, H, "rgba(34,197,94,0.95)", 1.5);
      drawZone(ctx, laneFromSliders(v), crop, W, H, W, H, "rgba(59,130,246,0.95)", 1.5);
      // horizon guide
      ctx.save();
      ctx.strokeStyle = "rgba(250,204,21,0.9)";
      ctx.setLineDash([10, 8]);
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.moveTo(0, v.horizon * H);
      ctx.lineTo(W, v.horizon * H);
      ctx.stroke();
      ctx.restore();
    };
    raf = requestAnimationFrame(draw);
    return () => {
      off();
      cancelAnimationFrame(raf);
      bitmapRef.current?.close();
      bitmapRef.current = null;
      client.setVideoMode("auto");
    };
  }, [client, camera]);

  if (!vals) return null;
  const set = (k) => (v) => {
    setVals({ ...vals, [k]: v });
    setSaved(false);
  };
  const save = async () => {
    await updateSettings({
      zones: {
        [`${camera}_vehicles`]: { polygon: laneFromSliders(vals) },
        [`${camera}_people`]: { polygon: laneFromSliders(vals, "people") },
      },
    });
    setSaved(true);
  };

  return (
    <div className="lp">
      <PageHeader
        title="Lane setup"
        onBack={() => go("settings")}
        right={
          <span className="lane-tabs">
            {CAMERAS.map(([key, label]) => (
              <button
                key={key}
                className={`lp-btn ${camera === key ? "lane-tab-on" : ""}`}
                onClick={() => setCamera(key)}
              >
                {label}
              </button>
            ))}
          </span>
        }
      />
      <div className="lane-split">
        <div className="lp-card lane-view">
          <canvas ref={canvasRef} width={960} height={540} />
          {cameras[camera] !== "online" && (
            <p className="lp-note">The {camera} camera is not connected: start it to see its picture.</p>
          )}
          <p className="lp-note">
            <b style={{ color: "#2563eb" }}>Blue</b>: a car must be inside to warn.{" "}
            <b style={{ color: "#16a34a" }}>Green</b>: the same for people.{" "}
            <b style={{ color: "#ca8a04" }}>Yellow line</b>: horizon.
          </p>
        </div>
        <div className="lp-card">
          <h2>
            <Icon name="eye" /> Fit the lane
          </h2>
          <Slider
            label="Horizon"
            hint="Move the yellow line to where the road ends."
            value={vals.horizon}
            min={0.3}
            max={0.95}
            onChange={set("horizon")}
          />
          <Slider
            label="Lane width"
            hint="Our own lane at the bottom of the picture."
            value={vals.width}
            min={0.25}
            max={1}
            onChange={set("width")}
          />
          <Slider
            label="Lane centre"
            hint="Move left or right if the phone is not in the middle."
            value={vals.centre}
            min={0.3}
            max={0.7}
            onChange={set("centre")}
          />
          <div className="lp-spacer" />
          <div className="lp-btnrow">
            <button className="lp-primary lp-small" onClick={save}>
              <Icon name="check" /> Save
            </button>
            <button
              className="lp-btn"
              onClick={() => {
                setVals(DEFAULT);
                setSaved(false);
              }}
            >
              <Icon name="reset" /> Default
            </button>
          </div>
          {saved && <p className="lp-note lp-okay">Saved. Warnings use the new lane now.</p>}
        </div>
      </div>
    </div>
  );
}
