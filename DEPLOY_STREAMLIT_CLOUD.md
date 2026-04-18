# ☁️ Streamlit Cloud - Dashboard Only (FREE)

## Setup Architecture

```
┌─────────────────────────────────┐
│  Streamlit Cloud (FREE)         │
│  Dashboard: streamlit.app       │
│  ✅ Web UI for reviewing emails │
└─────────────────────────────────┘
           ↕ Firebase
┌─────────────────────────────────┐
│  Your Local Machine             │
│  Telegram Bot + Email Processor │
│  ✅ Runs 24/7 on your computer  │
└─────────────────────────────────┘
```

## Prerequisites

- GitHub account with repo pushed
- Streamlit Cloud account (free)
- Local machine with bot running
- Firebase credentials (`config/firebase_key.json`)

---

## Step 1: Prepare Streamlit Config

Create/update `.streamlit/config.toml`:

```toml
[theme]
primaryColor = "#FF6B6B"
backgroundColor = "#1E1E1E"
secondaryBackgroundColor = "#2E2E2E"
textColor = "#FFFFFF"
font = "sans serif"

[client]
showErrorDetails = true

[logger]
level = "info"
```

---

## Step 2: Create `requirements_streamlit.txt`

This file only includes dashboard dependencies (smaller = faster deploys):

```bash
# Copy to a new file for Streamlit Cloud
cat > requirements_streamlit.txt << 'EOF'
streamlit==1.37.0
firebase-admin==6.5.0
google-auth==2.29.0
requests==2.32.3
python-dotenv==1.0.1
pydantic==2.8.2
pydantic-settings==2.4.0
EOF
```

Tell Streamlit to use this file by creating `.streamlit/config.toml`:

```toml
[client]
# Tell Streamlit Cloud to use specific requirements file
toolbarMode = "viewer"
```

---

## Step 3: Create `streamlit_app.py` (Entry Point)

Streamlit Cloud looks for `streamlit_app.py` or specified main file:

```bash
# Create a simple wrapper if not already
cat > streamlit_app.py << 'EOF'
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Run the dashboard
from src.dashboard.app import *
EOF
```

Or directly specify `src/dashboard/app.py` in Streamlit Cloud settings.

---

## Step 4: Push to GitHub

```bash
cd /Volumes/Sarbajit/Personal/ai-email-assistant

# Add all files
git add .
git commit -m "Prepare for Streamlit Cloud deployment"
git push origin main
```

---

## Step 5: Deploy to Streamlit Cloud

### Method 1: Web Interface (Easiest)

1. Go to **https://share.streamlit.io**
2. Click **"New app"**
3. Select:
   - **GitHub account**: Your account
   - **Repository**: `ai-email-assistant`
   - **Branch**: `main`
   - **Main file path**: `src/dashboard/app.py`
4. Click **"Deploy"**
5. Wait 2-3 minutes for deployment

**Your dashboard is now live at:**
```
https://your-username-ai-email-assistant-xxxxx.streamlit.app
```

### Method 2: Streamlit CLI

```bash
# Install Streamlit CLI
pip install streamlit

# Deploy
streamlit run src/dashboard/app.py --logger.level=info
```

---

## Step 6: Add Environment Variables

After deployment, add secrets to Streamlit Cloud:

1. Go to your app dashboard
2. Click **⋮** (three dots) → **Settings**
3. Click **Secrets**
4. Add your environment variables:

```toml
# .streamlit/secrets.toml (uploaded to Streamlit Cloud)
OPENAI_API_KEY = "your_key"
GOOGLE_API_KEY = "your_key"
TELEGRAM_BOT_TOKEN = "your_token"
TELEGRAM_CHAT_ID = "your_chat_id"
USER_EMAIL = "your_email@gmail.com"
USER_NAME = "Your Name"
FIREBASE_KEY_PATH = "config/firebase_key.json"
```

**Access secrets in code:**
```python
import streamlit as st
openai_key = st.secrets["OPENAI_API_KEY"]
```

---

## Step 7: Upload Firebase Credentials

Firebase credentials need to be accessible:

### Option A: Use secrets (Recommended)
```python
# In app.py
import json
import streamlit as st

firebase_key_dict = st.secrets.get("FIREBASE_KEY")
if firebase_key_dict:
    firebase_admin.initialize_app(
        cred=firebase_admin.credentials.Certificate(firebase_key_dict)
    )
```

Then add full JSON to Streamlit Cloud secrets.

### Option B: Store in `.streamlit/secrets.toml`
```toml
[firebase]
type = "service_account"
project_id = "your_project"
private_key_id = "your_key_id"
private_key = "your_private_key"
client_email = "your_email"
# ... etc
```

---

## Step 8: Update Dashboard Code for Streamlit Cloud

Add this to top of `src/dashboard/app.py`:

```python
import streamlit as st
import os
from pathlib import Path

# Streamlit Cloud detection
if "STREAMLIT_CLOUD" not in os.environ or os.getenv("STREAMLIT_CLOUD") == "true":
    # Load secrets from Streamlit Cloud
    if hasattr(st, 'secrets'):
        os.environ.setdefault("OPENAI_API_KEY", st.secrets.get("OPENAI_API_KEY", ""))
        os.environ.setdefault("GOOGLE_API_KEY", st.secrets.get("GOOGLE_API_KEY", ""))
        # ... load all secrets
```

---

## Step 9: Test the Dashboard

1. Visit your deployed URL
2. Login with password (if configured)
3. Check that it connects to Firebase
4. Test "Process Emails Now" button

The bot running locally should sync data via Firebase!

---

## Configuration: Local Bot + Cloud Dashboard

### Local Machine (`start_bot.sh`)
```bash
#!/bin/bash
source /opt/anaconda3/etc/profile.d/conda.sh
conda activate email-assistant
cd /Volumes/Sarbajit/Personal/ai-email-assistant

# Start bot (runs locally)
python unified_bot.py
```

### Streamlit Cloud (Dashboard)
- Reads from Firebase
- Shows email status
- Allows manual email processing
- Reviews and approves pending replies

### Data Flow
```
Local Bot                 Firebase                 Streamlit Cloud
   ↓                        ↓                            ↓
Process emails    →    Store results      ←    Read results
Generate replies  →    Update status      ←    Show UI
                        Sync state
```

---

## Monitoring & Troubleshooting

### View Deployment Logs
1. Go to https://share.streamlit.io
2. Select your app
3. Click **"Manage app"**
4. View logs in terminal output

### Common Issues

**Problem: "ModuleNotFoundError"**
```bash
# Make sure requirements_streamlit.txt has all dependencies
pip freeze > requirements_streamlit.txt
```

**Problem: "Firebase connection error"**
- Check `FIREBASE_KEY_PATH` in secrets
- Verify Firebase credentials are valid
- Make sure local bot has same credentials

**Problem: Dashboard shows old data**
- Verify local bot is running and updating Firebase
- Check Firebase real-time database permissions
- Restart the app: Click **⋮** → **Reboot app**

### Check Local Bot Status
```bash
# See if bot is running
ps aux | grep unified_bot

# Check bot logs
tail -f logs/bot.log
```

---

## Updating Dashboard

Whenever you update the dashboard code:

```bash
# 1. Test locally
streamlit run src/dashboard/app.py

# 2. Commit and push
git add .
git commit -m "Update dashboard UI"
git push origin main

# 3. Streamlit Cloud auto-deploys
# (Wait 1-2 minutes for redeploy)
```

---

## Cost

| Component | Cost |
|-----------|------|
| Streamlit Cloud (dashboard) | **FREE** ✅ |
| Local Machine (bot) | **FREE** (your computer) ✅ |
| Firebase | **FREE tier** (up to 1GB) ✅ |
| **TOTAL** | **$0** ✅✅✅ |

---

## Free Tier Limitations

- Max 3 deployed apps
- ~1GB storage
- Spins down after 1 hour inactivity (but restarts quickly)
- ~100MB per deploy

**Not an issue** for a dashboard-only app!

---

## Resources

- **Streamlit Cloud Docs**: https://docs.streamlit.io/streamlit-community-cloud
- **Streamlit Secrets**: https://docs.streamlit.io/streamlit-community-cloud/deploy-your-app/secrets-management
- **Firebase Admin**: https://firebase.google.com/docs/admin/setup

---

**Your dashboard is now live and free! 🚀**
