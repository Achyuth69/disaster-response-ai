# 🚨 Disaster Response AI — Deployment Guide

## Step 1: Push to GitHub

```bash
cd "e:\E\SURE TRUST\AGENT"
git init
git add .
git commit -m "Disaster Response AI System v2.0"
```

Create a repo on github.com, then:
```bash
git remote add origin https://github.com/YOUR_USERNAME/disaster-response-ai.git
git push -u origin main
```

---

## Option A: Railway (Recommended — Free 500hrs/month)

1. Go to **railway.app** and sign in with GitHub
2. Click **New Project** → **Deploy from GitHub repo**
3. Select your repo
4. Click **Variables** → Add:
   - `GROQ_API_KEY` = your key from console.groq.com
5. Railway auto-detects Dockerfile and deploys in ~3 minutes
6. Your URL: `https://YOUR-APP.railway.app/ui/index.html`

---

## Option B: Render (Free — may sleep after 15min inactivity)

1. Go to **render.com** → New → Web Service
2. Connect your GitHub repo
3. Settings auto-fill from `render.yaml`
4. Add env var: `GROQ_API_KEY=your_key`
5. Click **Create Web Service**
6. Your URL: `https://YOUR-APP.onrender.com/ui/index.html`

---

## Option C: Fly.io (Free — global, fast)

```bash
# Install: https://fly.io/docs/hands-on/install-flyctl/
fly auth login
fly launch --name disaster-response-ai
fly secrets set GROQ_API_KEY=your_key
fly deploy
```

URL: `https://disaster-response-ai.fly.dev/ui/index.html`

---

## Option D: Google Cloud Run (Free tier)

```bash
gcloud builds submit --tag gcr.io/YOUR_PROJECT/disaster-ai
gcloud run deploy disaster-ai \
  --image gcr.io/YOUR_PROJECT/disaster-ai \
  --platform managed \
  --allow-unauthenticated \
  --set-env-vars GROQ_API_KEY=your_key \
  --region asia-south1
```

---

## Local Run (for testing before deploy)

```bash
cd "e:\E\SURE TRUST\AGENT"
python run_api.py
```

- Desktop: http://127.0.0.1:8000/ui/index.html
- Phone (same WiFi): http://YOUR_PC_IP:8000/ui/index.html

---

## Environment Variables

| Variable | Required | Where to get |
|----------|----------|-------------|
| `GROQ_API_KEY` | ✅ Yes | console.groq.com (free) |
| `PRIMARY_MODEL` | No | Default: llama-3.3-70b-versatile |
| `SECONDARY_MODEL` | No | Default: llama-3.1-8b-instant |
| `SMTP_USER` | No | Gmail for email alerts |
| `SMTP_PASS` | No | Gmail App Password |

---

## After Deploy

1. Open your URL
2. Click **🎯 HYDERABAD DEMO** to test
3. All 20+ intelligence panels will load automatically
4. Share the URL — works on any device, any browser
