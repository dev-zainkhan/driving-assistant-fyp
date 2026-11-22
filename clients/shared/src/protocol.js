// Binary header pack/unpack. Little-endian. Mirrors server/app/core/protocol.py.
import { POSITIONS, PROTOCOL_VERSION } from "./types";

export const MSG_FRAME = 1;

export const CAMERA_HEADER_SIZE = 16;

export const VIEWER_HEADER_SIZE = 24;

export class ProtocolError extends Error {}

/** Camera node -> server frame (used by JS camera nodes and tests). */
export function packCameraFrame(seq, captureTsMs, jpeg) {
  const out = new Uint8Array(CAMERA_HEADER_SIZE + jpeg.length);
  const dv = new DataView(out.buffer);
  dv.setUint8(0, PROTOCOL_VERSION);
  dv.setUint8(1, MSG_FRAME);
  dv.setUint32(2, seq >>> 0, true);
  dv.setFloat64(6, captureTsMs, true);
  dv.setUint16(14, 0, true);
  out.set(jpeg, CAMERA_HEADER_SIZE);
  return out;
}

export function unpackCameraFrame(data) {
  const u8 = data instanceof Uint8Array ? data : new Uint8Array(data);
  if (u8.length < CAMERA_HEADER_SIZE) throw new ProtocolError("frame shorter than header");
  const dv = new DataView(u8.buffer, u8.byteOffset, u8.byteLength);
  if (dv.getUint8(0) !== PROTOCOL_VERSION) throw new ProtocolError(`unsupported version ${dv.getUint8(0)}`);
  if (dv.getUint8(1) !== MSG_FRAME) throw new ProtocolError(`unknown msg_type ${dv.getUint8(1)}`);
  return {
    seq: dv.getUint32(2, true),
    captureTsMs: dv.getFloat64(6, true),
    jpeg: u8.subarray(CAMERA_HEADER_SIZE),
  };
}

/** Server -> viewer frame (used by tests and fake servers). */
export function packViewerFrame(camera, seq, captureTsMs, serverTsMs, jpeg) {
  const out = new Uint8Array(VIEWER_HEADER_SIZE + jpeg.length);
  const dv = new DataView(out.buffer);
  dv.setUint8(0, PROTOCOL_VERSION);
  dv.setUint8(1, MSG_FRAME);
  dv.setUint8(2, POSITIONS.indexOf(camera));
  dv.setUint8(3, 0);
  dv.setUint32(4, seq >>> 0, true);
  dv.setFloat64(8, captureTsMs, true);
  dv.setFloat64(16, serverTsMs, true);
  out.set(jpeg, VIEWER_HEADER_SIZE);
  return out;
}

export function parseViewerFrame(data) {
  const u8 = data instanceof Uint8Array ? data : new Uint8Array(data);
  if (u8.length < VIEWER_HEADER_SIZE) throw new ProtocolError("frame shorter than header");
  const dv = new DataView(u8.buffer, u8.byteOffset, u8.byteLength);
  if (dv.getUint8(0) !== PROTOCOL_VERSION || dv.getUint8(1) !== MSG_FRAME)
    throw new ProtocolError("bad viewer frame header");
  const cam = POSITIONS[dv.getUint8(2)];
  if (!cam) throw new ProtocolError(`bad camera index ${dv.getUint8(2)}`);
  return {
    camera: cam,
    seq: dv.getUint32(4, true),
    captureTsMs: dv.getFloat64(8, true),
    serverTsMs: dv.getFloat64(16, true),
    jpeg: u8.subarray(VIEWER_HEADER_SIZE),
  };
}

export function parseServerMessage(text) {
  try {
    const m = JSON.parse(text);
    return m && typeof m.type === "string" ? m : null;
  } catch {
    return null;
  }
}

export function toHex(u8) {
  return Array.from(u8, (b) => b.toString(16).padStart(2, "0")).join("");
}

export function fromHex(hex) {
  const out = new Uint8Array(hex.length / 2);
  for (let i = 0; i < out.length; i++) out[i] = parseInt(hex.slice(i * 2, i * 2 + 2), 16);
  return out;
}
