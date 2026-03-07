# BetterBundle — Local Development Setup

## Prerequisites

- Node.js (^18.20 / ^20.10 / >=21)
- Python 3.10+
- Docker & Docker Compose
- ngrok (installed via Homebrew: `brew install ngrok`)
- Two free ngrok accounts (free tier = 1 tunnel per account)
- Shopify Partner account + development store

---

## Step 1: Start Infrastructure

```bash
cd /Users/gouravkargwal/Desktop/BetterBundle
docker compose -f docker-compose.local.yml up -d
```

This starts:

| Service    | Port  |
| ---------- | ----- |
| Postgres   | 5432  |
| Kafka      | 9092  |
| Redis      | 6379  |
| Kafka UI   | 8080  |
| Gorse      | 8086, 8088 |
| Grafana    | 3001  |
| Loki       | 3100  |

Verify: `docker compose -f docker-compose.local.yml ps`

---

## Step 2: Start ngrok Tunnels

You need **2 tunnels** on **2 separate ngrok accounts**.

### Tunnel 1 — Shopify Remix Frontend (port 3000)

Uses default ngrok config (account 1):

```bash
ngrok http 3000
```

### Tunnel 2 — Python Worker (port 8001)

Uses second ngrok account config:

```bash
ngrok http 8001 --config "$HOME/Library/Application Support/ngrok/ngrok-account2.yml"
```

> Copy the two `https://xxxx.ngrok-free.app` URLs from the terminal output. You'll need them in Step 3.

---

## Step 3: Update URLs

Every time ngrok gives new URLs (free tier = random URLs each restart), update these files:

### Frontend URL (Tunnel 1 URL)

**File: `better-bundle/shopify.app.dev.toml`**

```toml
application_url = "https://YOUR-FRONTEND-URL.ngrok-free.app"

[auth]
redirect_urls = [
  "https://YOUR-FRONTEND-URL.ngrok-free.app/auth/callback",
  "https://YOUR-FRONTEND-URL.ngrok-free.app/auth/shopify/callback",
]
```

**File: `better-bundle/.env.dev`** — update `SHOPIFY_APP_URL`:

```
SHOPIFY_APP_URL=https://YOUR-FRONTEND-URL.ngrok-free.app
```

### Python Worker URL (Tunnel 2 URL)

**File: `better-bundle/.env.dev`** — update `BACKEND_URL`:

```
BACKEND_URL=https://YOUR-WORKER-URL.ngrok-free.app
```

**File: `better-bundle/extensions/atlas/src/config/constants.ts`**

```ts
export const BACKEND_URL = "https://YOUR-WORKER-URL.ngrok-free.app" as const;
```

**File: `better-bundle/extensions/apollo/src/config/constants.ts`**

```ts
export const BACKEND_URL = "https://YOUR-WORKER-URL.ngrok-free.app" as const;
export const SHOPIFY_APP_URL = "https://YOUR-FRONTEND-URL.ngrok-free.app" as const;
```

**File: `better-bundle/extensions/venus/src/config/constants.ts`**

```ts
export const BACKEND_URL = "https://YOUR-WORKER-URL.ngrok-free.app" as const;
```

**File: `better-bundle/extensions/mercury/src/config/constants.js`**

```js
export const BACKEND_URL = "https://YOUR-WORKER-URL.ngrok-free.app";
```

**File: `better-bundle/extensions/phoenix/assets/jwtTokenManager.js`** (line ~23)

```js
this.BACKEND_URL = window.getBaseUrl ? window.getBaseUrl() : "https://YOUR-WORKER-URL.ngrok-free.app";
```

---

## Step 4: Start the Shopify Remix App (Frontend)

```bash
cd better-bundle
npm install
npx prisma generate
npm run dev:tunnel
```

> `npm run dev:tunnel` runs: `dotenv -e .env.dev -- shopify app dev --tunnel-url <your-frontend-ngrok>:3000`
>
> **Note:** Update the `dev:tunnel` script in `package.json` if your frontend ngrok URL changed:
> ```json
> "dev:tunnel": "dotenv -e .env.dev -- shopify app dev --tunnel-url https://YOUR-FRONTEND-URL.ngrok-free.app:3000"
> ```

The CLI will ask you to select your dev store on first run. The app runs on `http://localhost:3000`.

---

## Step 5: Start the Python Worker (Backend)

```bash
cd python-worker
pip install -r requirements.txt   # first time only
python run_local.py
```

This starts the FastAPI worker on `http://localhost:8001`. The ngrok tunnel (Tunnel 2) exposes it to the internet so Shopify extensions can reach it.

---

## Step 6: Open the App

1. Go to your Shopify Partner dashboard
2. Open your **development store**
3. Navigate to **Apps** > **Better-Bundle-Dev**
4. The app loads inside Shopify admin via the ngrok tunnel

---

## Quick Reference — Terminal Layout

| Terminal | Command |
| -------- | ------- |
| 1        | `docker compose -f docker-compose.local.yml up -d` |
| 2        | `ngrok http 3000` |
| 3        | `ngrok http 8001 --config "$HOME/Library/Application Support/ngrok/ngrok-account2.yml"` |
| 4        | `cd better-bundle && npm run dev:tunnel` |
| 5        | `cd python-worker && python run_local.py` |

---

## Troubleshooting

- **"Session not found" or auth errors** — Your frontend ngrok URL changed but `shopify.app.dev.toml` still has the old one. Update it and restart.
- **Extensions can't reach backend** — The BACKEND_URL in extension constants doesn't match your python worker ngrok URL. Update the constants files and redeploy extensions.
- **Prisma errors** — Run `npx prisma generate` and make sure Postgres is running (`docker compose -f docker-compose.local.yml ps`).
- **Kafka connection refused** — Kafka takes ~40s to start. Wait and retry.
- **ngrok "tunnel session limit"** — Free accounts only allow 1 tunnel. Make sure each tunnel uses a different account config.
