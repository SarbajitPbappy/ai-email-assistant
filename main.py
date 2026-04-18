import argparse
import time
import threading
from datetime import datetime
from apscheduler.schedulers.blocking import BlockingScheduler
from rich.console import Console
from rich.panel import Panel
from config.settings import settings
from src.utils.logger import get_logger

logger = get_logger(__name__)
console = Console()


def run_once(query: str = "in:inbox", max_emails: int = 10, listen_timeout: int = 600):
    """Run email processing then listen for replies."""
    console.print(Panel(
        f"🔄 Processing emails at {datetime.now().strftime('%H:%M:%S')}",
        style="cyan"
    ))
    try:
        from src.agent.orchestrator import EmailAssistantOrchestrator
        agent = EmailAssistantOrchestrator()

        # Process emails
        stats = agent.run(max_emails=max_emails, query=query)
        console.print(f"✅ Processing done! Stats: {stats}", style="green")

        # Listen for YES/NO/EDIT replies
        if stats['replies_generated'] > 0:
            console.print(
                f"👂 Listening for your Telegram replies for {listen_timeout//60} minutes...",
                style="yellow"
            )
            agent.start_reply_listener(timeout=listen_timeout)

        return stats

    except Exception as e:
        console.print(f"❌ Error: {e}", style="red")
        logger.error(f"Pipeline error: {e}")
        import traceback
        logger.error(traceback.format_exc())


def run_scheduler(interval_minutes: int = 15):
    """Run on automatic schedule."""
    console.print(Panel(
        f"⏰ Auto-scheduler started\n"
        f"Checking emails every {interval_minutes} minutes\n"
        f"Listening 10 min for replies after each check\n"
        f"Press CTRL+C to stop",
        style="bold green"
    ))

    scheduler = BlockingScheduler()

    # Run immediately
    run_once()

    # Schedule periodic runs
    scheduler.add_job(
        run_once,
        'interval',
        minutes=interval_minutes,
        id='email_check',
        max_instances=1
    )

    try:
        scheduler.start()
    except KeyboardInterrupt:
        console.print("\n👋 Scheduler stopped.", style="yellow")
        scheduler.shutdown()


def interactive_mode():
    """Interactive command mode."""
    console.print(Panel(
        "🤖 AI Email Assistant - Interactive Mode\n"
        "Type 'help' for commands",
        style="bold magenta"
    ))

    while True:
        try:
            cmd = input("\n> ").strip().lower()

            if cmd in ['quit', 'exit', 'q']:
                console.print("👋 Goodbye!")
                break

            elif cmd == 'check':
                run_once()

            elif cmd == 'listen':
                from src.agent.orchestrator import EmailAssistantOrchestrator
                agent = EmailAssistantOrchestrator()
                console.print("👂 Listening for Telegram replies (5 min)...")
                agent.start_reply_listener(timeout=300)

            elif cmd == 'status':
                from src.utils.database import Database
                db = Database()
                stats = db.get_daily_stats()
                console.print(f"📊 Today's Stats:")
                for k, v in stats.items():
                    console.print(f"  {k}: {v}")

            elif cmd == 'help':
                console.print("""
Commands:
  check    - Process emails now + listen for replies
  listen   - Listen for Telegram YES/NO/EDIT replies
  status   - Show today's stats
  quit     - Exit
""")
            else:
                console.print(f"Unknown: '{cmd}'. Type 'help'")

        except KeyboardInterrupt:
            console.print("\n👋 Goodbye!")
            break
        except Exception as e:
            console.print(f"Error: {e}", style="red")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AI Email Assistant")
    parser.add_argument(
        'mode',
        choices=['run', 'schedule', 'interactive', 'listen'],
        nargs='?',
        default='interactive'
    )
    parser.add_argument('--interval', type=int, default=15)
    parser.add_argument('--max-emails', type=int, default=10)
    parser.add_argument('--query', type=str, default='in:inbox')
    parser.add_argument('--listen-timeout', type=int, default=600)

    args = parser.parse_args()

    console.print(Panel(
        f"🤖 AI Email Assistant\n"
        f"Mode: {args.mode} | User: {settings.USER_NAME}",
        style="bold blue"
    ))

    if args.mode == 'run':
        run_once(
            query=args.query,
            max_emails=args.max_emails,
            listen_timeout=args.listen_timeout
        )
    elif args.mode == 'schedule':
        run_scheduler(interval_minutes=args.interval)
    elif args.mode == 'listen':
        from src.agent.orchestrator import EmailAssistantOrchestrator
        agent = EmailAssistantOrchestrator()
        agent.start_reply_listener(timeout=args.listen_timeout)
    elif args.mode == 'interactive':
        interactive_mode()


def professor_mode():
    """
    Run in professor outreach mode.
    Listens for PHD/MASTERS commands on Telegram.
    """
    console.print(Panel(
        "🎓 Professor Outreach Mode Active\n"
        "Send to Telegram:\n"
        "PHD <google scholar URL or text>\n"
        "MASTERS <google scholar URL or text>\n"
        "Then reply YES/NO/EDIT",
        style="bold blue"
    ))

    from src.email_reader.gmail_client import GmailClient
    from src.professor_outreach.outreach_manager import ProfessorOutreachManager
    from src.utils.telegram_bot import TelegramBot
    import time

    gmail = GmailClient()
    outreach_manager = ProfessorOutreachManager(gmail.service)
    bot = TelegramBot()
    bot.pending_professor_emails = {}

    bot.send_message(
        "🎓 Professor Outreach Mode Active!\n\n"
        "Send me:\n"
        "PHD <Google Scholar URL>\n"
        "MASTERS <Google Scholar URL>\n"
        "Or paste professor summary text after PHD/MASTERS"
    )

    console.print("👂 Listening for Telegram commands...", style="green")

    while True:
        try:
            updates = bot.get_updates()
            for update in updates:
                message = update.get('message', {})
                text = message.get('text', '').strip()
                chat_id = str(message.get('chat', {}).get('id', ''))

                if chat_id == str(settings.TELEGRAM_CHAT_ID) and text:
                    console.print(f"Received: {text[:80]}", style="cyan")

                    # Try professor command first
                    result = bot.process_professor_command(
                        text, outreach_manager
                    )

                    if result:
                        bot.send_message(result)
                    else:
                        # Handle YES/NO/EDIT for regular emails too
                        def send_email_func(to, subject, body, thread_id=''):
                            return gmail.send_email(
                                to=to, subject=subject,
                                body=body, thread_id=thread_id
                            )
                        result = bot.process_reply(text, send_email_func)
                        bot.send_message(result)

            time.sleep(3)

        except KeyboardInterrupt:
            console.print("\n👋 Professor mode stopped.", style="yellow")
            break
        except Exception as e:
            console.print(f"Error: {e}", style="red")
            time.sleep(5)
