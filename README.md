# Dridha Weed Detection System
### Full-stack dashboard for drone-based AI weed detection

---

## What this does

When you fly your drone with the WeedEye app, images auto-sync to Google Drive.
This system watches that folder, runs your YOLO AI model on each new image,
and if weeds are found, writes a `.waypoints` mission file automatically.

The dashboard UI (deployed on Vercel) shows:
- **Live terminal** — real-time log of every detection event
- **Detections tab** — images of detected weeds with GPS coordinates
- **Synced tab** — all images received from the drone
- **Waypoints tab** — preview and download of the mission file

---

## Folder structure

```
dridha/
├── backend/
│   ├── server.py          ← FastAPI + WebSocket + YOLO watcher
│   ├── requirements.txt   ← Python dependencies
│   ├── start.bat          ← Double-click to run (Windows)
│   ├── start_tunnel.bat   ← Double-click to expose publicly via ngrok
│   └── best.pt            ← YOUR YOLO model (copy it here)
│
└── frontend/
    ├── src/
    │   ├── App.jsx        ← Full React dashboard
    │   ├── main.jsx       ← Entry point
    │   └── index.css      ← Reset styles
    ├── index.html
    ├── package.json
    ├── vite.config.js
    ├── vercel.json
    └── .env.example       ← Copy to .env and fill in backend URL
```

---

## STEP 1 — Set up the backend (your Windows PC)

### 1a. Prerequisites
- Python 3.10 or newer — https://python.org/downloads
- Your `best.pt` YOLO model file

### 1b. Copy your model file
Copy `best.pt` into the `backend/` folder.

### 1c. Set your Google Drive path
Open `backend/server.py` in Notepad and find line 14:
```python
WEEDEYE_PATH = r"G:\My Drive\WeedEye_Flights"
```
Change it to match the actual path of your WeedEye folder.

To find it: open File Explorer → navigate to your Google Drive folder
→ right-click the WeedEye_Flights folder → Properties → copy the path.

### 1d. Start the backend
Double-click `backend/start.bat`

First run will install all dependencies automatically.
You should see:
```
[SYSTEM] Dridha backend started
[SYSTEM] YOLO model loaded from best.pt
[SYSTEM] Watching: G:\My Drive\WeedEye_Flights
```

The backend runs on http://localhost:8000

---

## STEP 2 — Expose backend publicly (ngrok)

The Vercel UI is on the internet. Your PC backend is local.
ngrok creates a permanent tunnel so they can connect.

### 2a. Create free ngrok account
Go to https://ngrok.com → Sign up free

### 2b. Download ngrok
Download ngrok.exe from the dashboard → put it in `backend/` folder

### 2c. Add your auth token
In the ngrok dashboard, copy your authtoken, then run:
```
ngrok config add-authtoken YOUR_TOKEN_HERE
```

### 2d. Get a free static domain
In your ngrok dashboard → Cloud Edge → Domains → Create Domain
You'll get something like: `dridha-weed.ngrok-free.app`

### 2e. Start the tunnel
Double-click `backend/start_tunnel.bat`
OR run:
```
ngrok http 8000 --domain=YOUR_STATIC_DOMAIN.ngrok-free.app
```

Your backend is now publicly available at:
`https://YOUR_STATIC_DOMAIN.ngrok-free.app`

Keep BOTH windows open (start.bat + start_tunnel.bat) while flying.

---

## STEP 3 — Deploy the frontend to Vercel (permanent public URL)

### 3a. Install Node.js
Download from https://nodejs.org (LTS version)

### 3b. Create a GitHub repo
1. Go to https://github.com → New repository
2. Name it `dridha-ui` → Create
3. Upload all files from the `frontend/` folder to this repo

### 3c. Deploy to Vercel
1. Go to https://vercel.com → Sign up free (use GitHub login)
2. Click "Add New Project"
3. Import your `dridha-ui` GitHub repo
4. Vercel auto-detects Vite — click Deploy

### 3d. Set the backend URL
1. In your Vercel project → Settings → Environment Variables
2. Add:
   - Name: `VITE_API_URL`
   - Value: `https://YOUR_STATIC_DOMAIN.ngrok-free.app`
3. Click Save → Go to Deployments → Redeploy

Your dashboard is now live at:
`https://dridha-ui.vercel.app`

This URL is **permanent and public** — share it with anyone.

---

## STEP 4 — Test it works

1. Start `start.bat` (backend)
2. Start `start_tunnel.bat` (ngrok)
3. Open `https://dridha-ui.vercel.app`
4. You should see "● LIVE" in the top right

To test without flying:
- Copy any `.jpg` image into your WeedEye_Flights folder
- Create a FlightLog.txt in the same folder with format:
  ```
  image.jpg | 17.3850 | 78.4867 | 50 | 12:00:00
  ```
- Watch the terminal tab detect it

---

## STEP 5 — Every time you fly

1. Double-click `start.bat`
2. Double-click `start_tunnel.bat`
3. Fly your mission with WeedEye app
4. Open `https://dridha-ui.vercel.app` to watch live

After flight:
- Go to Waypoints tab → Download `.waypoints`
- Load into Mission Planner / QGroundControl for spraying mission

---

## Troubleshooting

| Problem | Fix |
|---|---|
| "MODEL MISSING" in UI | Copy `best.pt` to `backend/` folder |
| "RECONNECTING" in UI | Make sure `start.bat` and `start_tunnel.bat` are both running |
| Images not syncing | Check that WeedEye app is connected and Google Drive is syncing |
| Wrong GPS in waypoints | Check your FlightLog.txt format — fields separated by `\|` |
| Vercel shows old backend | Update `VITE_API_URL` in Vercel settings and redeploy |
| Port 8000 already in use | Change `--port 8000` to `--port 8001` in `start.bat` and `start_tunnel.bat` |

---

## Architecture

```
Drone (WeedEye app)
       │  photos + FlightLog.txt
       ▼
Google Drive (auto-sync)
       │  watchdog detects new file
       ▼
backend/server.py  ──── best.pt (YOLO AI)
       │  WebSocket stream
       │  REST API (detections, images, waypoints)
       │
    ngrok tunnel
       │
       ▼
Vercel (React UI)  ◄── permanent public URL
       │
       ▼
Dridha_Mission.waypoints → Mission Planner → Spray drone
```

---

Built for Antigravity · Dridha Precision Agriculture System
