# FormFiller

Auto-fill bank forms from corporate documents using Claude AI.

## How it works

1. **Upload PDFs** — corporate documents (licences, registry extracts, articles of association, tax certificates)
2. **Review & edit** — Claude extracts all data into a structured dictionary you can edit
3. **Fill forms** — upload .docx bank forms, Claude maps fields automatically, download filled forms

## Quick start (local)

### Prerequisites
- Docker & Docker Compose
- Anthropic API key ([get one here](https://console.anthropic.com/settings/keys))

### Run

```bash
# 1. Clone the repo
git clone https://github.com/YOUR_USERNAME/formfiller.git
cd formfiller

# 2. Create .env file
cp .env.example .env
# Edit .env and add your ANTHROPIC_API_KEY

# 3. Start
docker compose up --build

# 4. Open http://localhost:8080
```

## Deploy to Digital Ocean

### Option A: App Platform (recommended, ~$12/mo)

1. Push this repo to GitHub
2. Go to [Digital Ocean App Platform](https://cloud.digitalocean.com/apps)
3. Click **Create App** → connect your GitHub repo
4. It will detect the Dockerfile automatically
5. Add environment variables:
   - `ANTHROPIC_API_KEY` — your Claude API key (mark as Secret)
   - `GATE_PASSWORD` — shared team password (mark as Secret)
6. Choose **Basic** plan ($12/mo)
7. Deploy!

### Option B: Droplet (more control)

```bash
# On a fresh Ubuntu 24.04 droplet:
ssh root@your-droplet-ip

# Install Docker
curl -fsSL https://get.docker.com | sh

# Clone and run
git clone https://github.com/YOUR_USERNAME/formfiller.git
cd formfiller
cp .env.example .env
nano .env  # add your keys

docker compose up -d --build

# Optional: add SSL with Caddy
apt install caddy
cat > /etc/caddy/Caddyfile << 'EOF'
formfiller.yourdomain.com {
    reverse_proxy localhost:8080
}
EOF
systemctl restart caddy
```

## Development (without Docker)

```bash
# Backend
cd backend
pip install -r requirements.txt
export ANTHROPIC_API_KEY=sk-ant-...
uvicorn main:app --reload --port 8080

# Frontend (separate terminal)
cd frontend
npm install
npm run dev
```

The Vite dev server (port 3000) proxies `/api` calls to the backend (port 8080).

## Tech stack

- **Backend**: Python, FastAPI, python-docx, SQLite
- **Frontend**: React, Vite
- **AI**: Claude Sonnet (via Anthropic API)
- **Deploy**: Docker, Digital Ocean App Platform

## Configuration

| Variable | Required | Description |
|---|---|---|
| `ANTHROPIC_API_KEY` | Yes | Your Anthropic API key |
| `GATE_PASSWORD` | No | Shared password for team access (empty = no auth) |
| `DB_PATH` | No | SQLite database path (default: `/data/formfiller.db`) |

## Cost estimate

| Item | Monthly |
|---|---|
| Digital Ocean (Basic plan) | ~$12 |
| Claude API (~50 operations/mo) | ~$5–15 |
| **Total** | **~$17–27** |
