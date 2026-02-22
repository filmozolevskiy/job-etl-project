"""Send one test email using current SMTP config (e.g. SendGrid from .env).

Run from project root:
  python scripts/verify_sendgrid_email.py
  python scripts/verify_sendgrid_email.py someone@example.com

Then check the recipient inbox. No DB or Airflow required.
"""

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

# Load .env from project root
root = Path(__file__).resolve().parent.parent
load_dotenv(root / ".env")

# Add services so we can import notifier
sys.path.insert(0, str(root / "services"))

from notifier import EmailNotifier


def main() -> int:
    recipient = (
        sys.argv[1].strip()
        if len(sys.argv) > 1
        else (os.getenv("SMTP_FROM_EMAIL") or os.getenv("SMTP_USER") or "you@example.com")
    )
    subject = "SendGrid test from JustApply"
    content = "<p>If you received this, SendGrid (port 2525) is working from your local env.</p>"

    print("Sending test email...")
    print(f"  SMTP_HOST: {os.getenv('SMTP_HOST')}")
    print(f"  SMTP_PORT: {os.getenv('SMTP_PORT')}")
    print(f"  To: {recipient}")
    print()

    notifier = EmailNotifier()
    if not notifier.smtp_host:
        print("ERROR: SMTP_HOST not set. Configure SMTP_* in .env and try again.")
        return 1

    ok = notifier.send_notification(recipient=recipient, subject=subject, content=content)
    if ok:
        print("SUCCESS: Email sent. Check your inbox (and spam).")
        return 0
    print("FAILED: Check logs above for errors.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
