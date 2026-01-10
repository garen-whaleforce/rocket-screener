"""Alerting system (v10).

Handles failure notifications via Slack/Email.
"""

import json
import logging
import os
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

import requests

logger = logging.getLogger(__name__)


@dataclass
class Alert:
    """Alert to send."""

    title: str
    message: str
    severity: str  # error, warning, info
    timestamp: datetime
    details: Optional[dict] = None


def send_slack_alert(
    alert: Alert,
    webhook_url: Optional[str] = None,
) -> bool:
    """Send alert to Slack.

    Args:
        alert: Alert to send
        webhook_url: Slack webhook URL (or from env)

    Returns:
        True if sent successfully
    """
    url = webhook_url or os.environ.get("SLACK_WEBHOOK_URL")
    if not url:
        logger.warning("Slack webhook URL not configured")
        return False

    # Build Slack message
    color = {
        "error": "#dc3545",
        "warning": "#ffc107",
        "info": "#17a2b8",
    }.get(alert.severity, "#6c757d")

    payload = {
        "attachments": [
            {
                "color": color,
                "title": f"[Rocket Screener] {alert.title}",
                "text": alert.message,
                "fields": [
                    {
                        "title": "Severity",
                        "value": alert.severity.upper(),
                        "short": True,
                    },
                    {
                        "title": "Time",
                        "value": alert.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                        "short": True,
                    },
                ],
                "footer": "Rocket Screener Alert System",
            }
        ]
    }

    if alert.details:
        payload["attachments"][0]["fields"].append({
            "title": "Details",
            "value": json.dumps(alert.details, ensure_ascii=False)[:1000],
            "short": False,
        })

    try:
        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()
        logger.info(f"Slack alert sent: {alert.title}")
        return True
    except Exception as e:
        logger.error(f"Failed to send Slack alert: {e}")
        return False


def send_email_alert(
    alert: Alert,
    to_email: Optional[str] = None,
) -> bool:
    """Send alert via email.

    Note: Simplified implementation. In production, would use
    SendGrid, AWS SES, or similar.

    Args:
        alert: Alert to send
        to_email: Recipient email (or from env)

    Returns:
        True if sent successfully
    """
    email = to_email or os.environ.get("ALERT_EMAIL")
    if not email:
        logger.warning("Alert email not configured")
        return False

    # In production, would implement actual email sending
    logger.info(f"Email alert would be sent to {email}: {alert.title}")
    return True


def alert_on_failure(
    error_message: str,
    details: Optional[dict] = None,
):
    """Send alert on pipeline failure.

    Args:
        error_message: Error description
        details: Additional details
    """
    alert = Alert(
        title="Pipeline Failure",
        message=error_message,
        severity="error",
        timestamp=datetime.now(),
        details=details,
    )

    # Try Slack first
    sent = send_slack_alert(alert)

    # Fallback to email
    if not sent:
        send_email_alert(alert)


def alert_on_qa_fail(qa_report: dict):
    """Send alert when QA gate fails.

    Args:
        qa_report: QA report dict
    """
    errors = qa_report.get("errors", [])
    error_count = len(errors)

    message = f"QA gate failed with {error_count} error(s)"
    if errors:
        message += "\n\n" + "\n".join([
            f"- [{e['code']}] Article {e['article_num']}: {e['message']}"
            for e in errors[:5]
        ])

    alert = Alert(
        title="QA Gate Failed",
        message=message,
        severity="error",
        timestamp=datetime.now(),
        details={"date": qa_report.get("date")},
    )

    send_slack_alert(alert)


def alert_on_success():
    """Send success notification (optional)."""
    alert = Alert(
        title="Daily Run Completed",
        message="All 3 articles published successfully.",
        severity="info",
        timestamp=datetime.now(),
    )

    # Only send if configured
    if os.environ.get("ALERT_ON_SUCCESS"):
        send_slack_alert(alert)
