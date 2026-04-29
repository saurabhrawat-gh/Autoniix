# Setup Guide — Windows

A complete, copy-paste-friendly guide to get the YouTube Automation stack running on a fresh Windows machine.

> **Time required:** ~45 minutes (most of it is downloads).
> **Skill level:** Beginner-friendly. No prior Linux/Docker experience needed.

---

## What you'll end up with

- Dashboard UI at **http://localhost:3000**
- Dashboard API at **http://localhost:8020**
- Temporal UI at **http://localhost:8080**
- All services running locally via Docker

---

## Step 1 — Install WSL2 (Windows Subsystem for Linux)

WSL2 gives you a real Ubuntu Linux environment inside Windows. Our app runs on Linux, so this is required.

### 1.1 Open **PowerShell as Administrator**
- Press `Windows` key
- Type `powershell`
- Right-click "Windows PowerShell" → **Run as administrator**

### 1.2 Run this command
```powershell
wsl --install -d Ubuntu
```

This installs WSL2 + Ubuntu in one shot.

### 1.3 Restart your computer when prompted

### 1.4 After restart, Ubuntu launches automatically
- It'll ask you to **create a Linux username** (lowercase, e.g. `saurabh`)
- It'll ask you to **set a password** (you'll need this for `sudo` commands later)
- **Save these somewhere — you'll need them often.**

### 1.5 Verify WSL is working
Open **PowerShell** (no admin needed) and run:
```powershell
wsl --status
```
You should see `Default Version: 2`.

---

## Step 2 — Install Docker Desktop

### 2.1 Download
Go to **https://www.docker.com/products/docker-desktop/** → click **Download for Windows**

### 2.2 Run the installer
- ✅ Check **"Use WSL 2 instead of Hyper-V"** when prompted
- ✅ Check **"Add shortcut to desktop"**

### 2.3 Restart your computer when prompted

### 2.4 Launch Docker Desktop
- Skip the survey / sign-in (not required)
- Wait for the Docker icon (whale) in the system tray to stop animating — means it's ready

### 2.5 Enable WSL2 integration
- Open Docker Desktop → **Settings** (gear icon)
- Go to **Resources → WSL Integration**
- ✅ Enable integration with **Ubuntu**
- Click **Apply & Restart**

### 2.6 Verify
Open Ubuntu (search "Ubuntu" in Start menu) and run:
```bash
docker --version
docker compose version
```
You should see version numbers for both.

---

## Step 3 — Install required tools inside Ubuntu

**Open Ubuntu** (from Start menu). Everything from here on runs inside the Ubuntu terminal, not PowerShell.

### 3.1 Update package lists
```bash
sudo apt update && sudo apt upgrade -y
```
(Enter your Ubuntu password when prompted.)

### 3.2 Install Git, Make, Python, build tools
```bash
sudo apt install -y git make python3 python3-venv python3-pip build-essential curl
```

### 3.3 Install Node.js 20 (for the dashboard UI)
```bash
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt install -y nodejs
```

### 3.4 Verify everything
```bash
git --version          # should be 2.x+
make --version         # should be 4.x+
python3 --version      # should be 3.10+ or 3.11+
node --version         # should be v20.x
npm --version          # should be 10.x
docker --version       # should be 28.x+
```

---

## Step 4 — Get the project code

### Option A — Clone with Git (recommended)
```bash
cd ~
git clone <REPO_URL_HERE> youtube-automation
cd youtube-automation
```

### Option B — From a `.zip` file
1. In Windows, copy the `.zip` to `\\wsl$\Ubuntu\home\<your-username>\`
2. In Ubuntu terminal:
```bash
cd ~
unzip youtube-automation.zip
cd youtube-automation
```

> ⚠️ **Important:** Always work inside `~` (your Linux home), **not** inside `/mnt/c/...` (your Windows drive). Performance is 10x slower on `/mnt/c/`.

---

## Step 5 — Configure secrets (`.env`)

```bash
cp .env.example .env
nano .env
```

Edit these **at minimum**:

| Variable | What to put |
|---|---|
| `DB_PASSWORD` | Any strong random string (e.g. `mysecret123abc`) |
| `TEMPORAL_DB_PASSWORD` | Any strong random string |
| `OPENAI_API_KEY` | Your OpenAI key (starts with `sk-`) |
| `ANTHROPIC_API_KEY` | Your Claude key (starts with `sk-ant-`) |
| `GOOGLE_AI_API_KEY` | Your Gemini key |
| `FISH_AUDIO_API_KEY` | Your Fish Audio TTS key |
| `YOUTUBE_API_KEY` | Your YouTube Data API key |

Save with `Ctrl+O` → `Enter` → exit with `Ctrl+X`.

> You can leave the others blank for now — fill them in only as needed.

---

## Step 6 — Install Python dependencies (for the dashboard backend)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

This takes **5-10 minutes** the first time.

> 💡 Anytime you open a new Ubuntu terminal, run `source .venv/bin/activate` first to use the same Python environment.

---

## Step 7 — Install dashboard UI dependencies

```bash
cd dashboard
npm install
cd ..
```

Takes about 1-2 minutes.

---

## Step 8 — Start everything (3 terminals)

You need **3 separate Ubuntu terminal windows** open. Open new ones from the Start menu (search "Ubuntu") or right-click the Ubuntu taskbar icon.

In each terminal, first do:
```bash
cd ~/youtube-automation
```

### Terminal 1 — Infrastructure (Postgres, Redis, Temporal)
```bash
make infra
```
Wait until you see `✅ Infrastructure ready!`. Leave this terminal open.

### Terminal 2 — Dashboard backend
```bash
source .venv/bin/activate
make bff
```
Wait until you see `Application startup complete.`. Leave this terminal open.

### Terminal 3 — Dashboard frontend
```bash
make ui
```
Wait until you see `Ready in Xs`. Leave this terminal open.

---

## Step 9 — Open the dashboard

In your **Windows browser** (Chrome, Edge, Firefox), go to:

**http://localhost:3000**

Login with the password **`admin`** (default — change later in dashboard settings).

---

## Stopping everything

When you're done for the day:

1. In each of Terminal 2 and Terminal 3 → press `Ctrl+C`
2. In any terminal:
   ```bash
   make stop
   ```

This stops all Docker containers cleanly. Your data is preserved for next time.

---

## Starting again next day

Just open 3 Ubuntu terminals and run:

```bash
# All terminals start with this:
cd ~/youtube-automation

# Terminal 1
make infra

# Terminal 2
source .venv/bin/activate
make bff

# Terminal 3
make ui
```

---

## Troubleshooting

### "make: command not found"
You skipped step 3.2. Run:
```bash
sudo apt install -y make
```

### "docker: command not found"
Docker Desktop isn't running, or WSL integration is off.
1. Open Docker Desktop on Windows → wait for whale icon
2. Settings → Resources → WSL Integration → enable Ubuntu

### "permission denied while trying to connect to the Docker daemon"
You're not in the docker group, OR Docker Desktop isn't running.
```bash
# Add yourself to docker group
sudo usermod -aG docker $USER

# Close and reopen Ubuntu terminal, then verify
groups | grep docker
```

### Port already in use (`bind: address already in use`)
Something else is using port 3000, 8020, or 5433. Find and stop it:
```bash
sudo lsof -i :3000   # or :8020 or :5433
# Kill the PID it shows
kill -9 <PID>
```

### Postgres "password authentication failed"
The volume was initialized with an old password. Wipe and recreate:
```bash
docker compose down
docker volume rm youtube-automation_pg_app_data
make infra
```

### "asyncpg.exceptions.InvalidPasswordError"
Same as above — wipe the postgres volume.

### WSL is slow
You're working on a Windows path (`/mnt/c/...`). Move the project to `~` (your Linux home):
```bash
cp -r /mnt/c/Users/YourName/youtube-automation ~/
cd ~/youtube-automation
```

### "make infra" hangs at "Waiting for Postgres"
Docker Desktop probably isn't running. Open Docker Desktop on Windows and wait for the whale icon. Then re-run `make infra`.

---

## Quick reference

| Command | What it does |
|---|---|
| `make` | Show help |
| `make infra` | Start Postgres, Redis, Temporal |
| `make bff` | Start dashboard backend (port 8020) |
| `make ui` | Start dashboard frontend (port 3000) |
| `make stop` | Stop all Docker containers |
| `make logs` | Tail infrastructure logs |

| URL | What |
|---|---|
| http://localhost:3000 | Dashboard UI |
| http://localhost:8020 | Dashboard API |
| http://localhost:8080 | Temporal UI |
| http://localhost:9001 | MinIO console (run `make minio` first) |

---

## Need help?

If something doesn't work:
1. Check the Troubleshooting section above
2. Look at the terminal that crashed — copy the error message
3. Make sure Docker Desktop is running (whale icon in system tray)
4. Try `make stop` then start again from Step 8
