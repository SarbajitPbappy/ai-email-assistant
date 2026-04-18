# 🔗 Hybrid Deployment: Streamlit Cloud + Local Bot

## Architecture

```
╔════════════════════════════════════════════════════════════════╗
║                    YOUR SETUP                                 ║
╠════════════════════════════════════════════════════════════════╣
║                                                                ║
║  CLOUD (Streamlit)                LOCAL (Your Computer)       ║
║  ┌──────────────────────────┐     ┌──────────────────────────┐ ║
║  │ 📊 Dashboard (FREE)      │     │ 🤖 Telegram Bot         │ ║
║  │ Web UI for reviewing     │     │ Runs 24/7               │ ║
║  │ https://your-app-*.app   │◄───►│ unifi_bot.py            │ ║
║  │                          │     │                          │ ║
║  │ ✅ Easy to update        │     │ ✅ Full control         │ ║
║  │ ✅ Auto-scaling          │     │ ✅ No latency          │ ║
║  └──────────────────────────┘     │                          │ ║
║            ▲                       │ 📧 Email Processing    │ ║
║            │                       │ Checks every 15 min    │ ║
║            │                       │                          │ ║
║            ├──────────────────────►│ 🔤 CV Parser           │ ║
║            │                       │                          │ ║
║            │  Firebase             │ 🧠 LLM (Ollama)        │ ║
║            │  (Real-time sync)     │                          │ ║
║            │                       │ 📚 Job Matcher         │ ║
║            │                       │                          │ ║
║            └───────────────────────┘                          │ ║
║                                                                ║
║  Costs: $0/month                                              ║
║  ✅ Dashboard: FREE (Streamlit Cloud)                         ║
║  ✅ Bot: FREE (your computer)                                 ║
║  ✅ Database: FREE (Firebase free tier)                       ║
║                                                                ║
╚════════════════════════════════════════════════════════════════╝
```

---

## 🎯 Quick Setup (15 minutes total)

### Part 1: Deploy Dashboard to Streamlit Cloud (5 min)

```bash
# 1. Push code to GitHub
cd /Volumes/Sarbajit/Personal/ai-email-assistant
git add .
git commit -m "Ready for hybrid deployment"
git push origin main

# 2. Go to https://share.streamlit.io
# 3. Click "New app"
# 4. Select:
#    - Repository: your-repo
#    - Branch: main
#    - Main file: src/dashboard/app.py
# 5. Deploy! (wait 2-3 min)

# Dashboard is now live at: https://your-username-xxx.streamlit.app
```

### Part 2: Setup Local Bot (10 min)

```bash
# 1. Environment setup
conda activate email-assistant
cd /Volumes/Sarbajit/Personal/ai-email-assistant

# 2. Configure environment
cp config/.env.example config/.env
nano config/.env  # Add your credentials

# 3. Start bot
python unified_bot.py

# 4. Keep running via screen/tmux (optional)
screen -S email-bot
python unified_bot.py
# Detach: Ctrl+A then D
```

---

## 📋 Step-by-Step Details

### STEP 1: Setup Dashboard (Streamlit Cloud)

See [DEPLOY_STREAMLIT_CLOUD.md](DEPLOY_STREAMLIT_CLOUD.md) for full details.

**Summary**:
1. Push code to GitHub
2. Go to https://share.streamlit.io
3. Click "New app"
4. Select repository, branch, and main file
5. Add environment secrets via dashboard
6. Done! ✅

---

### STEP 2: Setup Local Bot

See [DEPLOY_LOCAL_BOT.md](DEPLOY_LOCAL_BOT.md) for full details.

**Summary**:
1. Setup Python environment (conda/venv)
2. Install dependencies: `pip install -r requirements.txt`
3. Configure `config/.env`
4. Run: `python unified_bot.py`
5. Keep running with screen/tmux/systemd/launchd
6. Done! ✅

---

## 🔄 Data Flow & Sync

```
┌────────────────────────────────────────────────────────────┐
│                    Data Synchronization                    │
└────────────────────────────────────────────────────────────┘

1. Email Processing (Local Bot)
   └─> Bot processes emails locally
   └─> Writes to Firebase
   └─> Dashboard reads from Firebase

2. Manual Trigger (Streamlit Cloud)
   └─> User clicks "Process Emails Now" in dashboard
   └─> Sends command to local bot via Firebase
   └─> Local bot processes
   └─> Results updated in Firebase
   └─> Dashboard refreshes

3. Telegram Approval (Local Bot)
   └─> Bot shows pending reply via Telegram
   └─> User approves/edits via Telegram
   └─> Status updated in Firebase
   └─> Dashboard shows latest status

4. File Uploads (Streamlit Cloud)
   └─> User uploads CV or research profile in dashboard
   └─> Stored in Firebase
   └─> Local bot reads and uses for processing
```

---

## ✅ Verification Checklist

### Dashboard Deployed Successfully?
```bash
# 1. Visit your dashboard URL
https://your-username-ai-email-assistant-xxxxx.streamlit.app

# 2. Try to login
# (Default password in app.py: "sarbajit2026")

# 3. Check if it connects to Firebase
# (Should load without errors)
```

### Local Bot Running?
```bash
# 1. Check bot is running
ps aux | grep unified_bot

# 2. Send Telegram command
/CHECK

# 3. Bot should respond with status

# 4. Check logs
tail -f logs/bot.log
```

### Data Syncing?
```bash
# 1. Click "Process Emails Now" in dashboard
# 2. Should process locally and show results
# 3. Bot should log the activity
# 4. Dashboard should refresh with results
```

---

## 🛠️ Troubleshooting

### Dashboard shows "Connection Error"

**Check Firebase credentials**:
```bash
ls -la config/firebase_key.json
```

**Add to Streamlit Cloud secrets**:
1. Go to your app on streamlit.io
2. Click ⋮ → Settings → Secrets
3. Add all environment variables
4. Restart app

**Restart dashboard**:
```bash
# In streamlit.io dashboard
Click ⋮ → Reboot app
```

---

### Bot Not Responding

**Check if running**:
```bash
ps aux | grep unified_bot
```

**Start if stopped**:
```bash
source venv/bin/activate
python unified_bot.py
```

**Check logs**:
```bash
tail -50 logs/bot.log
tail -50 logs/bot.error.log
```

---

### Telegram Commands Not Working

**Verify bot token**:
```bash
echo $TELEGRAM_BOT_TOKEN
```

**Test manually**:
```bash
python -c "
from src.utils.telegram_bot import TelegramBot
bot = TelegramBot()
bot.send_message('Hello from bot!')
"
```

---

### Dashboard Not Syncing with Bot

**Verify Firebase is same for both**:
```bash
# Check local bot's Firebase
cat config/firebase_key.json | head -5

# Compare with Streamlit Cloud secrets
# (Go to app settings → Secrets)
```

**Force refresh**:
- Local bot: Restart with `python unified_bot.py`
- Dashboard: Click ⋮ → Reboot app

---

## 📊 Monitoring

### Check Bot Health Daily

```bash
# Add to cron (runs daily at 9 AM)
0 9 * * * ps aux | grep unified_bot | grep -v grep || echo "Bot is down!" | mail -s "Alert" your-email@example.com
```

### View Recent Activity

```bash
# Check what bot did today
grep "$(date +%Y-%m-%d)" logs/bot.log | tail -20
```

### Monitor Streamlit Cloud

1. Go to https://share.streamlit.io
2. Select your app
3. View logs and metrics

---

## 🚀 Deployment Options Comparison

Now that you have dashboard + bot setup, here are your expansion options:

| Component | Current | Option 1 | Option 2 |
|-----------|---------|----------|----------|
| Dashboard | Streamlit Cloud (FREE) | Stay on Streamlit | Move to Render/Railway |
| Bot | Your computer (FREE) | Keep local | Move to VPS ($4-6/mo) |
| Cost | **$0/month** | **$0/month** | **$4-6/month** |

**Option 1 (Current - Recommended): $0/month**
- Dashboard on Streamlit Cloud (free)
- Bot on your computer (free)
- Computer must be on ~24/7

**Option 2 (Future upgrade): $4-6/month**
- Dashboard on Streamlit Cloud (free)
- Bot on DigitalOcean VPS ($4-6/month)
- Both run 24/7 reliably

---

## 📱 Features Available Now

✅ **Telegram Bot** (Local)
- Email approval workflow
- Daily statistics
- Job opportunity notifications
- Professor outreach commands

✅ **Streamlit Dashboard** (Cloud)
- Review pending emails
- Process emails manually
- View job matches
- Upload CV/research profile
- Monitor statistics

✅ **Email Processing** (Local)
- Auto Gmail reading
- CV parsing
- Job matching
- Cover letter generation
- Reply generation

✅ **Data Sync** (Firebase)
- Real-time updates
- Shared database
- State persistence

---

## 💰 Total Cost

```
Streamlit Cloud: FREE
Local Bot: FREE (your computer's electricity)
Firebase: FREE (up to 1GB storage)
──────────────────
TOTAL: $0/month ✅
```

---

## 🎓 Next Steps

1. **Immediately**: Deploy dashboard to Streamlit Cloud (5 min)
2. **Same day**: Start bot locally and verify sync
3. **Monitor**: Check logs daily for issues
4. **Optional later**: Move bot to VPS if you want 24/7 reliability

---

## 📚 Full Guides

- **Dashboard Setup**: [DEPLOY_STREAMLIT_CLOUD.md](DEPLOY_STREAMLIT_CLOUD.md)
- **Local Bot Setup**: [DEPLOY_LOCAL_BOT.md](DEPLOY_LOCAL_BOT.md)
- **All Deployment Options**: [DEPLOYMENT_QUICK_START.md](DEPLOYMENT_QUICK_START.md)

---

**You're all set! Deploy now and enjoy your AI Email Assistant! 🚀**
