# 🤖 AI Email Assistant

[![Streamlit App](https://img.shields.io/badge/Streamlit-Dashboard-brightgreen)](http://localhost:8503) [![Telegram Bot](https://img.shields.io/badge/Telegram-Control-blue)](https://t.me/your_bot) [![Python](https://img.shields.io/badge/Python-3.10%2B-blue)](https://python.org)

**AI-powered email automation for job hunting, auto-replies, and professor outreach.** 

Automatically processes your Gmail inbox:
- ✅ Finds job opportunities & generates cover letters
- ✅ Classifies emails & creates smart replies  
- ✅ Scrapes professors from Google Scholar for PhD/MASTERS outreach
- ✅ Telegram approval workflow (YES/NO/EDIT)
- ✅ Streamlit dashboard for review/sending
- ✅ Local LLM (Ollama) + cloud fallback

![Dashboard Screenshot](screenshots/dashboard.png)
*(Add your screenshots here)*

## 🚀 Quick Start (5 minutes)

```bash
# 1. Clone & setup environment
git clone <repo>
cd ai-email-assistant
conda create -n email-assistant python=3.10 -y
conda activate email-assistant
pip install -r requirements.txt

# 2. Setup Gmail API (one-time)
# See detailed Gmail Setup below ↓

# 3. Edit config/.env with your keys
cp config/.env.example config/.env  # if example exists
# Add: OPENAI_API_KEY, TELEGRAM_BOT_TOKEN, etc.

# 4. Upload your CV & research profile
cp /path/to/my_cv.pdf data/my_cv.pdf
# Edit data/research_profile.json for PhD interests

# 5. Start everything
./start_bot.sh      # Telegram bot + auto email processing
./start_dashboard.sh  # http://localhost:8503
```

**Telegram Commands**:
```
CHECK    - Process new emails
REPLIES  - Show pending replies (YES/NO/EDIT/SKIP)
JOBS     - Recent job matches
STATUS   - Daily stats
PHD/PROF <scholar URL>  - Professor outreach
```

## 📋 From Scratch Setup (Detailed)

### 1. Prerequisites
```
• Python 3.10+ + conda
• Gmail account (for API access)
• Telegram account + BotFather bot
• Ollama (local AI): https://ollama.com
• Google AI Studio key (Gemini fallback)
• OpenAI key (optional)
```

### 2. Install Dependencies
```bash
conda create -n email-assistant python=3.10 -y
conda activate email-assistant
pip install -r requirements.txt
```

**Production** (lighter): `pip install -r requirements_deploy.txt`

### 3. Gmail API Setup (Critical)
1. [Google Cloud Console](https://console.cloud.google.com)
2. Create project → Enable Gmail API
3. Credentials → **OAuth 2.0 Client ID** → Desktop app
4. Download `credentials.json` → `config/credentials.json`
5. **First run** will open browser → auth → saves `config/token.json`

**Scopes used**: read/send/modify + labels.

### 4. Configure `.env`
```bash
# config/.env
OPENAI_API_KEY=your_openai_key
GOOGLE_API_KEY=your_gemini_key
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id
USER_NAME="Your Name"
USER_EMAIL="you@gmail.com"
EMAIL_SIGNATURE="Best,\nYour Name"

# LLM (local first)
PRIMARY_LLM=ollama
LLM_MODEL=llama3
OLLAMA_BASE_URL=http://localhost:11434
```

### 5. Telegram Bot Setup
1. [@BotFather](https://t.me/botfather) → `/newbot`
2. Save `BOT_TOKEN` to `.env`
3. Message your bot → Get `CHAT_ID` → add to `.env`
4. Test: `python -c "from src.utils.telegram_bot import TelegramBot; TelegramBot().send_message('Test')"`

### 6. Data Files
```
data/my_cv.pdf              # Your CV (required for cover letters)
data/research_profile.json  # PhD interests:
{
  "phd_topics": ["AI", "ML", "NLP"],
  "masters_topics": ["CS", "Data Science"],
  "dream_unis": ["MIT", "Stanford"]
}
```

### 7. Local LLM (Ollama - Recommended)
```bash
# Install: https://ollama.com
ollama pull llama3        # ~4GB, fast local inference
ollama pull llama3:8b      # Smaller/faster
ollama serve              # Keep running
```

## 🎯 Usage Modes

### A. Full Bot (Recommended)
```bash
./start_bot.sh
```
- Auto-checks inbox every 15min
- Queues replies → Telegram approval
- All commands: CHECK, REPLIES, JOBS, STATUS

### B. Core Email Processing
```bash
# One-time run
python main.py run --max-emails 20

# Auto scheduler
python main.py schedule --interval 10

# Interactive CLI
python main.py interactive
```

### C. Dashboard Only
```bash
./start_dashboard.sh
# Open http://localhost:8503
```
- View emails/jobs
- Edit/approve cover letters
- Send drafts

### D. Professor Outreach Only
```bash
python professor_mode.py
```
**Telegram**: `PHD <scholar URL>` or `MASTERS <text>`

## 📊 Features

| Feature | Status | Telegram Cmd |
|---------|--------|--------------|
| Auto-classify emails | ✅ | CHECK |
| Job matching + cover letters | ✅ | JOBS |
| Auto-reply generation | ✅ | REPLIES |
| Professor scraping/outreach | ✅ | PHD/MASTERS |
| Telegram approval workflow | ✅ | YES/NO/EDIT |
| Daily stats | ✅ | STATUS |
| Cover letter editing | ✅ | Dashboard |
| Gmail labels | ✅ | auto-labels |

## 🛠 Project Structure
```
ai-email-assistant/
├── main.py                 # Core CLI
├── unified_bot.py          # Full Telegram bot
├── professor_mode.py       # Outreach mode
├── start_bot.sh           # One-click bot
├── start_dashboard.sh     # One-click dashboard
├── config/
│   ├── .env               # Secrets
│   ├── settings.py        # Config
│   └── credentials.json   # Gmail
├── src/
│   ├── agent/orchestrator.py     # Main pipeline
│   ├── email_reader/gmail_client.py
│   ├── auto_replier/
│   ├── job_matcher/
│   ├── professor_outreach/
│   ├── dashboard/app.py   # Streamlit
│   └── utils/
├── data/                  # CV, profiles, DB
├── logs/                  # Logs
├── requirements.txt
└── tests/
```

## 🔧 Troubleshooting

| Issue | Fix |
|-------|-----|
| `No module 'src'` | `cd` to project root |
| Gmail auth fails | Delete `config/token.json`, re-run |
| Ollama error | `ollama serve &` in another terminal |
| Telegram silent | Check BOT_TOKEN + CHAT_ID |
| No replies generated | Check `logs/assistant.log`, lower MIN_MATCH_SCORE |
| Dashboard 404 | Port 8503 free? `lsof -i :8503` |

**Logs**: `tail -f logs/assistant.log`

## 🤝 Contributing
```
# Install dev deps
pip install -r requirements.txt pytest

# Tests
pytest tests/

# Logs
tail -f logs/assistant.log
```

## 📄 License
MIT - Use freely!

---

**⭐ Star if useful! Questions? Check Telegram bot → HELP**

