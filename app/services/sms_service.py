"""SMS notification service – sends attendance confirmations via SMS.
Supports Africa's Talking and Twilio. Configure via environment variables:

  SMS_PROVIDER=africastalking|twilio
  
  # Africa's Talking
  AT_USERNAME=sandbox  (or your username)
  AT_API_KEY=your_api_key
  AT_SENDER_ID=  (optional short code)
  
  # Twilio
  TWILIO_ACCOUNT_SID=your_sid
  TWILIO_AUTH_TOKEN=your_token
  TWILIO_FROM_NUMBER=+1234567890
"""

import os
import logging
from typing import Optional

logger = logging.getLogger(__name__)

SMS_PROVIDER = os.getenv("SMS_PROVIDER", "").lower()


def _get_at_client():
    """Get Africa's Talking SMS client."""
    try:
        import africastalking
        username = os.getenv("AT_USERNAME", "sandbox")
        api_key = os.getenv("AT_API_KEY", "")
        if not api_key:
            return None
        africastalking.initialize(username, api_key)
        return africastalking.SMS
    except ImportError:
        logger.warning("africastalking package not installed. Run: pip install africastalking")
        return None


def _get_twilio_client():
    """Get Twilio SMS client."""
    try:
        from twilio.rest import Client
        sid = os.getenv("TWILIO_ACCOUNT_SID", "")
        token = os.getenv("TWILIO_AUTH_TOKEN", "")
        if not sid or not token:
            return None
        return Client(sid, token)
    except ImportError:
        logger.warning("twilio package not installed. Run: pip install twilio")
        return None


def is_sms_configured() -> bool:
    """Check if SMS sending is properly configured."""
    if SMS_PROVIDER == "africastalking":
        return bool(os.getenv("AT_API_KEY"))
    elif SMS_PROVIDER == "twilio":
        return bool(os.getenv("TWILIO_ACCOUNT_SID") and os.getenv("TWILIO_AUTH_TOKEN"))
    return False


def send_sms(phone: str, message: str) -> dict:
    """Send an SMS message. Returns {"success": bool, "detail": str}."""
    if not phone:
        return {"success": False, "detail": "No phone number provided"}

    if not is_sms_configured():
        return {"success": False, "detail": "SMS not configured"}

    # Normalize phone number
    phone = phone.strip()
    if not phone.startswith("+"):
        phone = "+" + phone

    try:
        if SMS_PROVIDER == "africastalking":
            sms = _get_at_client()
            if not sms:
                return {"success": False, "detail": "Africa's Talking not configured"}
            sender = os.getenv("AT_SENDER_ID", None)
            kwargs = {"message": message, "recipients": [phone]}
            if sender:
                kwargs["sender_id"] = sender
            response = sms.send(**kwargs)
            logger.info(f"AT SMS response: {response}")
            return {"success": True, "detail": "SMS sent via Africa's Talking"}

        elif SMS_PROVIDER == "twilio":
            client = _get_twilio_client()
            if not client:
                return {"success": False, "detail": "Twilio not configured"}
            from_number = os.getenv("TWILIO_FROM_NUMBER", "")
            msg = client.messages.create(
                body=message,
                from_=from_number,
                to=phone,
            )
            logger.info(f"Twilio SMS SID: {msg.sid}")
            return {"success": True, "detail": f"SMS sent via Twilio (SID: {msg.sid})"}

        else:
            return {"success": False, "detail": f"Unknown SMS provider: {SMS_PROVIDER}"}

    except Exception as e:
        logger.error(f"SMS send failed: {e}")
        return {"success": False, "detail": str(e)}


def send_attendance_sms(phone: str, member_name: str, meeting_name: Optional[str] = None, org_name: Optional[str] = None):
    """Send attendance confirmation SMS."""
    parts = [f"Hi {member_name}, your attendance has been recorded"]
    if meeting_name:
        parts[0] += f" for {meeting_name}"
    if org_name:
        parts[0] += f" at {org_name}"
    parts[0] += "."
    message = parts[0]
    return send_sms(phone, message)
