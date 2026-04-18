# 🏠 Local Bot Setup - Run on Your Computer

## Overview

Keep your Telegram bot and email processing running on your local machine 24/7 while the dashboard lives on Streamlit Cloud.

```
Your Local Computer               Streamlit Cloud
│                                │
├─ Telegram Bot ────────┬────→ Firebase ←─── Dashboard UI
├─ Email Processor  ────┤
├─ Gmail Reader     ────┤
└─ Ollama (LLM)     ────┘
```

---

## Prerequisites

- Python 3.10+
- Conda or venv
- All dependencies installed
- Gmail API credentials
- Telegram bot token
- Firebase credentials
- Ollama (optional, for local LLM)

---

## Step 1: Setup Local Environment

### Create Conda Environment

```bash
conda create -n email-assistant python=3.10 -y
conda activate email-assistant

# Navigate to project
cd /Volumes/Sarbajit/Personal/ai-email-assistant

# Install dependencies
pip install -r requirements.txt
```

### Or Use venv

```bash
python3.10 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

pip install -r requirements.txt
```

---

## Step 2: Configure Environment

```bash
# Copy template
cp config/.env.example config/.env

# Edit with your credentials
nano config/.env
```

**Required variables:**
```
OPENAI_API_KEY=your_key
GOOGLE_API_KEY=your_key
TELEGRAM_BOT_TOKEN=your_token
TELEGRAM_CHAT_ID=your_chat_id
USER_EMAIL=your_email@gmail.com
USER_NAME=Your Name
FIREBASE_KEY_PATH=config/firebase_key.json
```

---

## Step 3: Setup Ollama (Optional but Recommended)

For free local AI inference:

```bash
# Install Ollama: https://ollama.com

# Download a model
ollama pull llama3

# Keep running in background
ollama serve
```

In another terminal:

```bash
# Test Ollama
curl http://localhost:11434/api/tags
```

---

## Step 4: Run Bot Locally

### Simple Method (One Terminal)

```bash
# Activate environment
source venv/bin/activate

# Run bot
python unified_bot.py
```

### Better Method (Use `screen` or `tmux` for persistence)

Using `screen`:

```bash
# Start new screen session
screen -S email-bot

# Inside screen:
source venv/bin/activate
python unified_bot.py

# Detach: Ctrl+A then D
# Reattach: screen -r email-bot
```

Using `tmux`:

```bash
# Start new tmux session
tmux new-session -d -s email-bot

# Run bot in session
tmux send-keys -t email-bot "source venv/bin/activate" Enter
tmux send-keys -t email-bot "python unified_bot.py" Enter

# View logs
tmux attach -t email-bot
```

---

## Step 5: Keep Bot Running 24/7

### macOS: Create Launch Agent

Create `~/Library/LaunchAgents/com.emailassistant.bot.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.emailassistant.bot</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/bin/python3</string>
        <string>/Volumes/Sarbajit/Personal/ai-email-assistant/unified_bot.py</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>/Volumes/Sarbajit/Personal/ai-email-assistant/logs/bot.log</string>
    <key>StandardErrorPath</key>
    <string>/Volumes/Sarbajit/Personal/ai-email-assistant/logs/bot.error.log</string>
</dict>
</plist>
```

Load it:

```bash
launchctl load ~/Library/LaunchAgents/com.emailassistant.bot.plist
launchctl start com.emailassistant.bot

# Check status
launchctl list | grep emailassistant

# Stop it
launchctl unload ~/Library/LaunchAgents/com.emailassistant.bot.plist
```

### Linux: Use systemd Service

Create `/etc/systemd/system/email-bot.service`:

```ini
[Unit]
Description=AI Email Assistant Bot
After=network.target

[Service]
Type=simple
User=your_username
WorkingDirectory=/home/your_user/ai-email-assistant
ExecStart=/home/your_user/email-assistant/bin/python unified_bot.py
Restart=always
RestartSec=10
StandardOutput=append:/home/your_user/ai-email-assistant/logs/bot.log
StandardError=append:/home/your_user/ai-email-assistant/logs/bot.error.log

[Install]
WantedBy=multi-user.target
```

Enable and start:

```bash
sudo systemctl daemon-reload
sudo systemctl enable email-bot
sudo systemctl start email-bot

# Check status
sudo systemctl status email-bot
```

### Windows: Use Task Scheduler

1. Open Task Scheduler
2. Create Basic Task → "Email Assistant Bot"
3. Trigger: "At startup"
4. Action: Start a program
5. Program: `C:\path\to\python.exe`
6. Arguments: `unified_bot.py`
7. Start in: `C:\path\to\ai-email-assistant`

---

## Step 6: Monitor Bot Activity

### Check Logs

```bash
# View recent logs
tail -f logs/bot.log

# View errors
tail -f logs/bot.error.log

# Check if running
ps aux | grep unified_bot
```

### Test Bot Manually

```bash
# Send test command via Telegram
# Bot should respond with status

# Or test directly
python -c "
from src.utils.telegram_bot import TelegramBot
bot = TelegramBot()
bot.send_message('Test: Bot is working!')
"
```

---

## Step 7: Verify Dashboard Sync

### In Streamlit Cloud Dashboard:

1. Login to dashboard
2. Click "🔄 Process Emails Now"
3. Check if it processes
4. Verify email appears in dashboard
5. Confirm bot received Telegram notification

### Check Firebase Sync

```bash
# View what's in Firebase
python -c "
from src.utils.firebase_db import FirebaseDatabase
db = FirebaseDatabase()
status = db.get('bot_status')
print('Current status:', status)
"
```

---

## Daily Maintenance

### Morning Check
```bash
# Verify bot is running
ps aux | grep unified_bot

# Check for errors
tail -20 logs/bot.error.log

# Monitor Telegram
# (Bot should be responsive)
```

### Weekly Tasks
```bash
# Check disk usage
df -h

# Check logs size
du -sh logs/

# Rotate old logs if needed
mv logs/bot.log logs/bot.log.old
```

---

## Troubleshooting

### Bot Won't Start

```bash
# Check Python
python --version

# Check dependencies
pip list | grep -E "streamlit|firebase|google"

# Try running manually for error details
python unified_bot.py
```

### Bot Not Responding to Telegram

```bash
# Verify token
echo $TELEGRAM_BOT_TOKEN

# Test connection
python -c "
import requests
token = 'YOUR_TOKEN'
url = f'https://api.telegram.org/bot{token}/getMe'
response = requests.get(url)
print(response.json())
"
```

### Gmail Errors

```bash
# Verify credentials exist
ls -la config/credentials.json
ls -la config/token.json

# Re-authenticate
rm config/token.json
python unified_bot.py  # Will prompt for Gmail auth
```

### Dashboard Not Syncing

```bash
# Verify Firebase connection
python -c "
from config.settings import settings
print('Firebase key path:', settings.FIREBASE_KEY_PATH)
import os
print('File exists:', os.path.exists(settings.FIREBASE_KEY_PATH))
"
```

---

## Performance Tips

### Reduce Resource Usage

```bash
# In config/.env
PRIMARY_LLM=gemini  # Instead of ollama (uses less RAM)
EMAIL_CHECK_INTERVAL_MINUTES=30  # Check less frequently
MAX_DAILY_APPLICATIONS=5  # Limit auto-apply
```

### Monitor CPU/Memory

```bash
# macOS
top -p $(pgrep -f unified_bot)

# Linux
htop -p $(pgrep -f unified_bot)
```

---

## Backup & Recovery

### Backup Data

```bash
# Backup data directory
tar -czf email-assistant-backup-$(date +%Y%m%d).tar.gz data/

# Save configs
tar -czf email-assistant-config-$(date +%Y%m%d).tar.gz config/

# Store safely
cp *.tar.gz ~/Backups/
```

### Restore Data

```bash
# Extract backup
tar -xzf email-assistant-backup-20260418.tar.gz

# Restart bot
pkill unified_bot
python unified_bot.py
```

---

## Uptime Monitoring

### Simple Uptime Check

```bash
# Add to crontab to check every hour
crontab -e

# Add this line:
0 * * * * ps aux | grep unified_bot | grep -v grep || mail -s "Bot down!" your-email@example.com
```

### Better: Use Healthchecks.io (Free)

```bash
# Sign up: https://healthchecks.io

# Add to bot code:
import requests
requests.get("https://hc-ping.com/YOUR_UUID", timeout=10)
```

---

## Cost

| Component | Cost |
|-----------|------|
| Local bot | **FREE** (your computer) |
| Streamlit Cloud dashboard | **FREE** |
| Firebase | **FREE tier** |
| Optional: Ollama LLM | **FREE** |
| **TOTAL** | **$0** ✅ |

---

## Summary

✅ **Telegram bot**: Runs 24/7 on your local machine
✅ **Email processing**: Happens locally  
✅ **Dashboard**: Free on Streamlit Cloud
✅ **Data sync**: Via Firebase (free tier)
✅ **Cost**: Completely FREE

The only requirement: Your computer/laptop needs to stay on or have reliable uptime.

---

**Happy automating! 🚀**
