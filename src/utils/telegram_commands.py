START_MESSAGE = """🤖 AI PERSONAL ASSISTANT ONLINE

Welcome Sarbajit! I'm your AI assistant.

Choose what to do:

📧 EMAIL COMMANDS:
CHECK - Process new emails now
JOBS - Show recent job matches
REPLIES - Show pending reply drafts
STATUS - Today's stats

🎓 PROFESSOR OUTREACH:
PROF <info> - Start professor outreach
  Send: name, university, email, research
  Or: university profile URL
  Or: personal website URL
PHD - Apply for PhD
MASTERS - Apply for Masters
PROF_STATUS - Outreach history
PROF_HELP - All professor commands

✉️ REPLY COMMANDS:
YES - Send pending reply/email
NO - Discard
EDIT: <text> - Edit body and send
SUBJECT: <text> - Change subject line
PROF_EMAIL: <email> - Set professor email

📊 GENERAL:
START - Show this menu
HELP - Show all commands
STATUS - Today's stats

All emails include your signature automatically.
CV + Transcript attached for professor emails."""

HELP_MESSAGE = """📋 ALL COMMANDS:

EMAIL ASSISTANT:
  CHECK          Process unread emails
  JOBS           Recent job matches
  REPLIES        Pending reply drafts
  STATUS         Today's statistics

REPLY CONTROLS:
  YES            Send pending reply
  NO             Discard reply
  EDIT: <text>   Edit body and send

PROFESSOR OUTREACH:
  PROF <info>          Start outreach
  PROF <URL>           Scrape professor page
  PHD                  Select PhD application
  MASTERS              Select Masters application
  SUBJECT: <text>      Change email subject
  PROF_EMAIL: <email>  Set professor email
  PROF_STATUS          Outreach history
  PROF_HELP            Professor commands

GENERAL:
  START          Show welcome menu
  HELP           This help message
  STATUS         Today's stats"""
