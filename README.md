# Driving Assistant (FYP): backend + Next.js dashboard

Four phones act as the car's cameras (front, left, right, back) and stream to a laptop.
The laptop runs **YOLOv8n** to detect **cars and people**, tracks them, guesses their distance,
and sends video, boxes and warnings to the **Next.js dashboard**.

- How the backend works, in simple words: [`docs/Backend_Report.docx`](docs/Backend_Report.docx)
- Full design: [`DESIGN.md`](DESIGN.md)
- Message formats (the contract for every app): [`docs/protocol.md`](docs/protocol.md)
- Database tables: [`docs/database.md`](docs/database.md)

## Quick start (Windows)

You need **Python 3.12** and **Node.js 20+**. Then double-click:

1. **`setup.bat`**: installs everything (finds out by itself if you have an NVIDIA GPU).
2. **`start.bat`**: starts the server and opens the dashboard at http://localhost:3000.

Using GitHub Copilot, Claude or Cursor? Ask it to *"set up and run this project"*: the exact steps are in
[`AGENTS.md`](AGENTS.md) and [`.github/copilot-instructions.md`](.github/copilot-instructions.md).

## 1. Install step by step (if you prefer)

You need **Python 3.12** and **Node.js 20 or newer**. Then, in this folder, double-click one of:

| Your laptop | Run | Download |
| --- | --- | --- |
| **No NVIDIA graphics card** (most laptops) | `setup_cpu.bat` | about 1 GB |
| NVIDIA card (GTX 10xx and newer) | `setup_gpu.bat` | about 3 GB |

Both create a `.venv` folder (Python) and install the dashboard packages (`clients/node_modules`).

## 2. Run it

1. Double-click **`run_server.bat`**. Wait until it says `Application startup complete`.
   Check http://localhost:8000/api/health: it should say `"detector":"ready"`
   (`"device":"cpu"` without a GPU, `"cuda:0"` with one).
2. Double-click **`run_nextjs.bat`** (the first time it builds the app, about a minute).
   Open http://localhost:3000 and press **Start Driving Assistant**.
3. No phones? Test with the videos in this repo: on the dashboard tap the screen, **Settings**,
   **Backup mode**, pick `abc.mp4` (a real road video) or the `test` videos for each camera, **Start**.

With phones (same Wi-Fi as the laptop): on each phone open `http://<laptop-ip>:8000/camera`,
pick its position, choose a video or the camera, press Play. Find the laptop IP with `ipconfig`.
If phones cannot connect: set the Wi-Fi profile to **Private** and allow Python in Windows Firewall.

Useful keys on the live view: `D` shows the speed of each camera and the lane, `S` saves an incident
(or hold the screen for 1 second).

## 3. Running without a GPU (CPU)

**It works on the CPU, with no errors.** The server sees there is no GPU and uses the CPU by itself
(you will see one line: `CUDA not available, falling back to CPU`). It is only slower:

| | GPU (GTX 1070) | CPU (laptop) |
| --- | --- | --- |
| Video on the dashboard | 30 fps | 30 fps |
| AI checks per second | front 20, back 10, sides 8 | about 4 per camera |
| Delay of the boxes | 40 to 60 ms | about 250 ms |

The video stays smooth; the boxes just update less often. To make the CPU faster:

- Settings, **Advanced**, Detection, **YOLO image size**: 640 to **416** or **320** (faster, sees far cars less well).
- Settings, Advanced, **Cameras**: switch off cameras you don't need (for example left and right).
- Keep the laptop on the charger.

## 4. Tests

`run_tests.bat` runs the server tests (pytest) and the dashboard tests (Vitest). They do not need a GPU.

## Folders

- `server/`: FastAPI + YOLOv8n (Python). `app/core/` has one file per step (frame store, AI thread,
  tracker, distance, warnings, recorder). The settings database is created in `server/data/` on the first start.
- `server/weights/yolov8n.pt`: the YOLOv8n model (6 MB, pre-trained on COCO).
- `clients/shared/`: `@da/client`, the shared JavaScript client (WebSocket, message formats, box drawing).
- `clients/nextjs-web/`: the Next.js 14 dashboard (App Router, JavaScript). Each screen has its own URL:
  `/`, `/setup/...`, `/settings`, `/settings/alerts`, `/settings/lane`, `/settings/advanced`, `/settings/incidents` ...
- `videos/`: `abc.mp4` (a 640x360 road video) and `test/` (four generated test videos, no real road).

## Important

- Never install a PyTorch newer than 2.14 or a CUDA 12.8+ build on a GTX 10xx laptop: they don't support Pascal GPUs.
- Version 1 detects only cars (also bus, truck, motorcycle, bicycle) and people.
