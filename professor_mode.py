import time
from src.email_reader.gmail_client import GmailClient
from src.professor_outreach.telegram_handler import ProfessorTelegramHandler
from src.utils.telegram_bot import TelegramBot
from config.settings import settings
from src.utils.logger import get_logger

logger = get_logger(__name__)


def run_professor_mode():
    print("🎓 Professor Outreach Mode Started")
    print("Send 'PROF <info>' in Telegram")

    gmail = GmailClient()
    handler = ProfessorTelegramHandler(gmail.service)
    bot = TelegramBot()

    bot.send_message(
        "🎓 Professor Outreach Mode Active!\n\n"
        "Send:\n"
        "PROF <info or URL>\n\n"
        "Then choose PHD or MASTERS\n\n"
        "Commands:\n"
        "PROF_HELP - show all commands\n"
        "PROF_STATUS - show history"
    )

    while True:
        try:
            updates = bot.get_updates()

            for update in updates:
                message = update.get("message", {})
                text = message.get("text", "").strip()
                chat_id = str(message.get("chat", {}).get("id", ""))

                if chat_id == str(settings.TELEGRAM_CHAT_ID) and text:
                    print(f"Received: {text[:80]}")

                    # Pass bot.send_message as the function
                    handled = handler.handle_message(
                        text,
                        send_func=bot.send_message
                    )

                    if not handled:
                        bot.send_message(
                            "Command not recognized.\n"
                            "Send PROF_HELP for all commands."
                        )

            time.sleep(3)

        except KeyboardInterrupt:
            print("\n👋 Stopped.")
            break
        except Exception as e:
            logger.error(f"Error: {e}")
            import traceback
            logger.error(traceback.format_exc())
            time.sleep(5)


if __name__ == "__main__":
    run_professor_mode()
