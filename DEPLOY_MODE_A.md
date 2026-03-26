# Dridha Mode A Deployment

This setup uses one shared Google account and a fully deployed backend/frontend.

## Already prepared

- Google Drive root folder id:
  - `1tDOsMdzZVtMDfbtzp6PckVXOPXaSVCy-`
- Service account file:
  - `c:\Users\gliri\Downloads\dridha-hackathon-2830325bc4ca.json`
- Compact one-line JSON for Render:
  - [service_account_compact.txt](c:\Users\gliri\Desktop\dridha_project\imported\dridha\backend\service_account_compact.txt)
- Backend code already switched to Google Drive polling
- Frontend UI kept as-is

## What you need to do

### 1. Put `best.pt` in the backend folder

File path should exist:

- [best.pt](c:\Users\gliri\Desktop\dridha_project\imported\dridha\backend\best.pt)

### 2. Create a GitHub repo and upload the project

Upload this folder:

- [dridha](c:\Users\gliri\Desktop\dridha_project\imported\dridha)

### 3. Deploy backend on Render

Render will use:

- [render.yaml](c:\Users\gliri\Desktop\dridha_project\imported\dridha\render.yaml)

In Render, set these environment variables:

- `DRIDHA_DRIVE_ROOT_FOLDER_ID`
  - `1tDOsMdzZVtMDfbtzp6PckVXOPXaSVCy-`
- `DRIDHA_GOOGLE_SERVICE_ACCOUNT_JSON`
  - paste the full contents of:
  - [service_account_compact.txt](c:\Users\gliri\Desktop\dridha_project\imported\dridha\backend\service_account_compact.txt)
- `DRIDHA_ALLOWED_ORIGINS`
  - `*`
- `DRIDHA_CONFIDENCE`
  - `0.50`

Optional:

- `DRIDHA_POLL_INTERVAL_SECONDS`
  - `4`

After deploy, test:

- `https://YOUR-RENDER-URL/api/health`

### 4. Deploy frontend on Vercel

Project root:

- `frontend`

Set environment variable:

- `VITE_API_URL`
  - `https://YOUR-RENDER-URL`

Then redeploy.

### 5. Test the full flow

1. Use the shared Google account in WeedEye.
2. Start a new survey.
3. Confirm new `Session_*` folder appears in `WeedEye_Flights`.
4. Confirm session contains images and `FlightLog*.txt`.
5. Open deployed frontend.
6. Check:
   - synced photos
   - weed detections
   - `.waypoints` download

## Important notes

- This is a hackathon-friendly shared-account deployment.
- Everyone using the system is effectively using one shared workspace.
- No local backend should be required once Render/Vercel are configured correctly.
- If the backend shows no data, first verify the new session folder is visible in Google Drive and the service account still has access to `WeedEye_Flights`.
