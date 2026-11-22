// Protocol v1: constants and the shape of every message (docs/protocol.md is the contract).
//
// JavaScript has no types, so the shapes below are written as JSDoc comments. VS Code reads
// them and shows hints and autocomplete, but nothing is checked when the code runs.

export const PROTOCOL_VERSION = 1;

/** The four cameras, in the same order as the camera index in binary frames (0..3). */
export const POSITIONS = ["front", "left", "right", "back"];

/**
 * @typedef {"front" | "left" | "right" | "back"} Position
 * @typedef {"none" | "caution" | "danger" | "info"} Level  white, yellow, orange, blue
 * @typedef {"online" | "offline"} CameraStatus
 * @typedef {"auto" | "all" | "none"} VideoMode
 *   auto = front always, other cameras only while they warn; all = debug; none = data only
 * @typedef {[number, number, number, number]} Box  [x1, y1, x2, y2], each 0..1
 */

/**
 * One detected object in an `overlay` message.
 * @typedef {object} OverlayObject
 * @property {number} track_id   stable id while the object stays in view
 * @property {string} cls        "person", "car", "bus", ...
 * @property {number} conf       0..1
 * @property {Box} box
 * @property {boolean} predicted true when the box was moved forward between detections
 * @property {"left" | "center" | "right"} zone
 * @property {number | null} distance_m  rough distance, null when the box is too small
 * @property {Level} level
 */

/**
 * @typedef {object} WarningInfo
 * @property {Level} level
 * @property {string[]} codes  e.g. ["PERSON_AHEAD"]
 * @property {string} text     e.g. "Person ahead, 5 m"
 */

/**
 * @typedef {WarningInfo & { since: number }} CameraWarning  since = time in ms
 */

/**
 * One row of the Detection and alerts screen (slide 35).
 * @typedef {object} ObjectAlert
 * @property {string} title          "Vehicles"
 * @property {boolean} is_safety     shows the "Safety" badge
 * @property {boolean} detect
 * @property {boolean} announce
 * @property {number} alert_at_m     orange when closer than this
 * @property {number} recommended_m  value restored by "Reset to recommended"
 * @property {number} min_m          minus button stops here
 * @property {number} max_m          plus button stops here
 * @property {boolean} show_text
 * @property {number} phase          1 = works now, 3 = later (signs, potholes...)
 */

/**
 * Warning area of a camera. `polygon` (the lane shape) wins over the x/y band when set.
 * @typedef {object} Zone
 * @property {number} x_min
 * @property {number} x_max
 * @property {number} y_min
 * @property {number} y_max
 * @property {[number, number][] | null} polygon
 */

/**
 * All settings, as returned by GET /api/settings. Only the fields the apps use are listed.
 * @typedef {object} Settings
 * @property {Record<Position, number>} det_fps   detections per second per camera
 * @property {Record<Position, boolean>} camera_on
 * @property {Record<string, ObjectAlert>} alerts  key: "vehicles", "people", ...
 * @property {Record<string, Zone>} zones           key: "front_vehicles", ...
 * @property {{peripheral_vision: boolean, night_blindness: boolean, night_vision: boolean}} vision
 * @property {boolean} voice         "Voice assistance"
 * @property {boolean} beep
 * @property {number} volume         0..1
 * @property {number} speech_speed   0.5..2.0
 * @property {number} voice_gap_s    at least this long between two spoken warnings
 * @property {number} voice_repeat_s the same warning is not spoken again within this time
 * @property {boolean} ar_mirror
 */

/**
 * @typedef {object} CameraStats
 * @property {CameraStatus} [status]
 * @property {number} in_fps
 * @property {number} det_fps
 * @property {number | null} latency_ms
 * @property {number | null} infer_ms
 * @property {"phone" | "file" | null} [source]
 * @property {string | null} [video_name]
 */

/**
 * @typedef {"sudden_brake" | "hard_jolt" | "saved_by_driver"} IncidentCause
 *
 * @typedef {object} IncidentWarning  one line of "Warnings before it" (slide 47)
 * @property {Position} camera
 * @property {number} time_in_video_s
 * @property {string} message
 * @property {number | null} distance_m
 * @property {"orange" | "yellow"} colour
 * @property {boolean} was_spoken
 *
 * @typedef {object} Incident
 * @property {number} id
 * @property {IncidentCause} cause
 * @property {string} happened_at  date and time (ISO text)
 * @property {number} length_s
 * @property {string | null} front_picture
 * @property {Partial<Record<Position, string>>} videos
 * @property {IncidentWarning[]} warnings
 */

/**
 * Messages the server sends to viewers as text (JSON). Check `type` first.
 *
 * @typedef {{type: "welcome", protocol: number, server_version: string,
 *   cameras: {position: Position, status: CameraStatus}[], settings: Settings}} WelcomeMsg
 * @typedef {{type: "overlay", camera: Position, seq: number, det_seq: number | null,
 *   objects: OverlayObject[], warning: WarningInfo}} OverlayMsg
 * @typedef {{type: "warning_state", ts: number, cameras: Record<Position, CameraWarning>}} WarningStateMsg
 * @typedef {{type: "camera_status", position: Position, status: CameraStatus}} CameraStatusMsg
 * @typedef {{type: "stats", cameras: Record<Position, CameraStats>, gpu: string, detector?: string}} StatsMsg
 * @typedef {{type: "incident", id: number, camera: Position | null, codes: string[], ts: number}} IncidentMsg
 * @typedef {{type: "settings", settings: Settings}} SettingsMsg
 * @typedef {{type: "error", code: string, message: string}} ErrorMsg
 * @typedef {WelcomeMsg | OverlayMsg | WarningStateMsg | CameraStatusMsg | StatsMsg | IncidentMsg | SettingsMsg | ErrorMsg} ServerMessage
 */

/**
 * A binary video frame from the server, already split from its 24-byte header.
 * @typedef {object} ViewerFrame
 * @property {Position} camera
 * @property {number} seq
 * @property {number} captureTsMs
 * @property {number} serverTsMs
 * @property {Uint8Array} jpeg
 */

/**
 * @typedef {object} Health  GET /api/health
 * @property {string} status
 * @property {string} device
 * @property {string} model
 * @property {"ready" | "loading" | "disabled" | "error"} detector
 * @property {number} protocol
 */
