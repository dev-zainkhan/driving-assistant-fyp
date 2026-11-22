# How to set up and run this project (for AI coding assistants: GitHub Copilot, Claude, Cursor ...)

Driving Assistant FYP. Python FastAPI server with YOLOv8n (cars and people) + a Next.js 14 dashboard.
Target machine: **Windows 10/11**. Use **PowerShell** or `cmd`. Run every command from the repo root.

## Requirements (check first)

- Python **3.12** with the `py` launcher: `py -3.12 --version`
- Node.js **20 or newer**: `node --version`
- No GPU is needed. With an NVIDIA GPU, PyTorch uses it automatically.

If one is missing, tell the user to install it (python.org, tick "Add to PATH"; nodejs.org LTS). Do not use another Python version.

## 1. Install all dependencies (once)

```powershell
.\setup.bat
```

It creates `.venv`, installs PyTorch 2.14 (CPU build, or the CUDA 12.6 build if `nvidia-smi` exists),
then `server\requirements.txt`, then `npm install` in `clients\`. It can be run again safely.

Manual equivalent:

```powershell
py -3.12 -m venv .venv
.venv\Scripts\python.exe -m pip install torch==2.14.0 torchvision==0.29.0 --index-url https://download.pytorch.org/whl/cpu
.venv\Scripts\python.exe -m pip install -r server\requirements.txt
cd clients; npm install; cd ..
```

(For an NVIDIA GPU use `--index-url https://download.pytorch.org/whl/cu126` instead of `/cpu`.)

## 2. Run

```powershell
.\start.bat
```

It opens the server in a new window (port 8000), waits until the model is loaded, builds the
Next.js dashboard and serves it on http://localhost:3000.

Manual equivalent (two terminals):

```powershell
# terminal 1: server
cd server; ..\.venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --ws-per-message-deflate false
# terminal 2: dashboard (dev mode with live reload)
cd clients; npm run dev:next
```

## 3. Check that it works

- http://localhost:8000/api/health returns `"detector":"ready"` (`"device":"cpu"` or `"cuda:0"`).
- Open http://localhost:3000, press **Start Driving Assistant**.
- Test without phones: tap the screen, Settings, Backup mode, choose `abc.mp4` (or `test/*.webm`) per camera, Start.
  Or by API: `POST http://localhost:8000/api/sources/files` with `{"front":"videos/abc.mp4","left":"videos/abc.mp4","right":"videos/abc.mp4","back":"videos/abc.mp4"}`.
- Tests: `.\run_tests.bat` (pytest in `server\`, Vitest in `clients\`). No GPU needed.

## Rules (do not break)

- **Never** install a PyTorch newer than 2.14.0 or a CUDA 12.8+ build: they don't support GTX 10xx (Pascal) GPUs used by the team.
- Keep `--ws-per-message-deflate false` on uvicorn (compression made the video drop from 30 to 17 fps).
- The log line `CUDA not available, falling back to CPU` is normal on laptops without an NVIDIA GPU. CPU is slower (about 4 AI checks per camera per second) but works.
- Frontend code is plain **JavaScript** (no TypeScript). Format with `npm run format` in `clients\`.
- Message formats between server and apps are in `docs/protocol.md`; change it, `server/app/core/protocol.py` and `clients/shared` together.

## Troubleshooting

| Problem | Fix |
| --- | --- |
| `py` not found | Install Python 3.12 from python.org with "Add to PATH" and the py launcher |
| Port 8000 or 3000 in use | Close the old server/dashboard window, or `netstat -ano | findstr :8000` and end that process |
| `npm run build:next` fails | Run `npm install` in `clients\` again |
| Phones cannot connect | Same Wi-Fi; Wi-Fi profile Private; allow Python in Windows Firewall; use `http://<laptop-ip>:8000/camera` |
| Slow boxes on CPU | Settings, Advanced, YOLO image size 416 or 320; switch off unused cameras |

## Layout

- `server/` FastAPI app (`app/`), tests (`tests/`), tools (`tools/`), model `weights/yolov8n.pt`. Database is created at `server/data/` on first start.
- `clients/shared/` shared JS client `@da/client`; `clients/nextjs-web/` Next.js dashboard (npm workspaces in `clients/package.json`).
- `videos/` sample videos for backup mode.
