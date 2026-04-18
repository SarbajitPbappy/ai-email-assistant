import requests
from src.utils.logger import get_logger

logger = get_logger(__name__)

def send_notification(message: str, title: str = "AI Assistant"):
    """Send notification via Telegram and log it."""
    from config.settings import settings

    logger.info(f"NOTIFICATION: {message[:100]}")

    # Telegram notification
    if settings.TELEGRAM_BOT_TOKEN and settings.TELEGRAM_CHAT_ID:
        _send_telegram(message, settings)
    else:
        logger.warning("Telegram not configured - notification logged only")

def _send_telegram(message: str, settings):
    """Send message via Telegram bot."""
    try:
        url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage"

        # Telegram has 4096 char limit
        if len(message) > 4000:
            message = message[:4000] + "\n...[truncated]"

        payload = {
            'chat_id': settings.TELEGRAM_CHAT_ID,
            'text': message,
            'parse_mode': 'Markdown'
        }

        response = requests.post(url, json=payload, timeout=10)

        if response.status_code == 200:
            logger.info("Telegram notification sent ✅")
        else:
            logger.error(f"Telegram failed: {response.text}")

    except Exception as e:
        logger.error(f"Telegram error: {e}")
