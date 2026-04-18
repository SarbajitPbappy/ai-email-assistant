# ⚡ HYBRID SETUP - QUICK START (10 minutes)

**Dashboard on Streamlit Cloud (FREE) + Bot on Your Computer (FREE) = $0/month**

---

## 🚀 PART 1: Deploy Dashboard (5 minutes)

### Step 1: Push Code to GitHub
```bash
cd /Volumes/Sarbajit/Personal/ai-email-assistant
git add .
git commit -m "Hybrid deployment setup"
git push origin main
```

### Step 2: Deploy to Streamlit Cloud
1. Go to **https://share.streamlit.io**
2. Click **"New app"**
3. Select:
   - **GitHub account**: Your account
   - **Repository**: `ai-email-assistant`
   - **Branch**: `main`
   - **Main file path**: `src/dashboard/app.py`
4. Click **"Deploy"**
5. **Wait 2-3 minutes for deployment**

### Step 3: Add Secrets
1. Go to your deployed app
2. Click **⋮** (three dots) → **Settings**
3. Click **"Secrets"** tab
4. Add these:
```
OPENAI_API_KEY=your_openai_key
GOOGLE_API_KEY=your_gemini_key
TELEGRAM_BOT_TOKEN=your_telegram_token
TELEGRAM_CHAT_ID=your_chat_id
USER_EMAIL=your_email@gmail.com
USER_NAME=Your Name
FIREBASE_KEY_PATH=config/firebase_key.json
```

✅ **Dashboard is now LIVE!** Your URL: `https://your-username-ai-email-assistant-xxxxx.streamlit.app`

---

## 🤖 PART 2: Start Bot Locally (5 minutes)

### Step 1: Setup Environment
```bash
# Activate conda environment
conda activate email-assistant

# Go to project directory
cd /Volumes/Sarbajit/Personal/ai-email-assistant
```

### Step 2: Configure
```bash
# Copy example config
cp config/.env.example config/.env

# Edit with your credentials
nano config/.env

# Required values to fill in:
# - OPENAI_API_KEY
# - GOOGLE_API_KEY
# - TELEGRAM_BOT_TOKEN
# - TELEGRAM_CHAT_ID
# - USER_EMAIL
```

### Step 3: Run Bot
```bash
python unified_bot.py
```

**You should see:**
```
🤖 Initializing AI Personal Assistant...
✅ All modules ready!
🤖 Bot is running. Listening for Telegram commands...
```

### Step 4: Keep Bot Running
**Option A: Use Screen** (Simple)
```bash
# Start new screen session
screen -S email-bot

# Inside screen:
python unified_bot.py

# Detach: Press Ctrl+A then D
# Reattach later: screen -r email-bot
```

**Option B: Use Tmux** (Better)
```bash
tmux new-session -d -s email-bot "python unified_bot.py"
# Check: tmux ls
# Attach: tmux attach -t email-bot
```

**Option C: Keep Terminal Open**
```bash
# Just let it run in a terminal window
python unified_bot.py
```

---

## ✅ TEST EVERYTHING

### Test 1: Dashboard Loads
1. Visit your Streamlit dashboard URL
2. Login with password
3. Should load without errors

### Test 2: Bot Responds
1. Open Telegram
2. Send command to your bot: `/CHECK`
3. Bot should respond with status

### Test 3: Data Syncs
1. Click **"🔄 Process Emails Now"** in dashboard
2. Should process emails
3. Bot should log the activity
4. Dashboard should show results

### Test 4: Telegram Approval
1. Wait for bot to find pending replies
2. Bot sends Telegram message with YES/NO/EDIT options
3. Click YES
4. Dashboard should update

---

## 🎉 YOU'RE DONE!

**What's Running:**
- ✅ Dashboard: On Streamlit Cloud (FREE, always live)
- ✅ Bot: On your computer (FREE, runs when computer is on)
- ✅ Email Processing: On your computer (automatic)
- ✅ Data Sync: Via Firebase (FREE)

**Monthly Cost: $0** 🎊

---

## 📚 Need Help?

**For Dashboard**: See [DEPLOY_STREAMLIT_CLOUD.md](DEPLOY_STREAMLIT_CLOUD.md)
**For Local Bot**: See [DEPLOY_LOCAL_BOT.md](DEPLOY_LOCAL_BOT.md)
**Full Details**: See [DEPLOY_HYBRID.md](DEPLOY_HYBRID.md)
**All Options**: See [DEPLOYMENT_QUICK_START.md](DEPLOYMENT_QUICK_START.md)

---

## 🐛 Quick Troubleshooting

### Bot won't start
```bash
# Check if conda activated
conda activate email-assistant

# Check Python version
python --version

# Check dependencies
pip list | grep streamlit

# See the actual error
python unified_bot.py
```

### Dashboard shows "Connection Error"
- Check you added all secrets to Streamlit Cloud
- Click ⋮ → Reboot app
- Wait 1 minute and refresh

### Bot not responding to Telegram
```bash
# Check if bot is running
ps aux | grep unified_bot

# Check token is correct
echo $TELEGRAM_BOT_TOKEN

# Try sending a test message
python -c "
from src.utils.telegram_bot import TelegramBot
bot = TelegramBot()
bot.send_message('Test!')
"
```

### Dashboard and bot not syncing
- Verify both use same Firebase key
- Restart bot: `Ctrl+C` then run again
- Restart dashboard: Click ⋮ → Reboot app

---

## 🚀 Next Steps (Optional)

### Want Reliable 24/7 Uptime?
Later, move bot to **DigitalOcean** ($4-6/month):
- See [DEPLOY_DIGITALOCEAN.md](DEPLOY_DIGITALOCEAN.md)
- Dashboard stays on Streamlit (still free)
- Total: $4-6/month with perfect uptime

### Want Everything in One Place?
Move to **Railway** ($10-20/month):
- See [DEPLOY_RAILWAY.md](DEPLOY_RAILWAY.md)
- Everything runs in cloud
- Simple setup, paid option

### Current Setup is Perfect?
Just keep bot running on your computer!
- No additional cost
- Full control
- Easy to update code locally

---

**Happy automating! 🚀**
