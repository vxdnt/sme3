from app import state
from app.config import FROM_EMAIL, RESEND_API_KEY


def send_ticket_email(to_email: str, name: str, ticket_url: str, quantity: int, category: str) -> dict:
    if not RESEND_API_KEY:
        return {"ok": False, "error": "RESEND_API_KEY not configured"}
    try:
        import resend as _resend

        _resend.api_key = RESEND_API_KEY
        flyer_url = f"{state.current_base_url}/static/images/BFISS.jpg" if state.current_base_url else "/static/images/BFISS.jpg"
        html_body = f"""
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Your Ticket – Big Fat Indian Scam Sangeet</title>
<style>
  body {{ margin: 0; padding: 0; background: #f5f5f5; font-family: 'Google Sans', Arial, sans-serif; }}
  .wrap {{ max-width: 520px; margin: 32px auto; background: #fff; border-radius: 12px; overflow: hidden; box-shadow: 0 2px 12px rgba(0,0,0,0.08); }}
  .hero {{ background: #0a0a0a; padding: 32px 28px 24px; color: #fff; }}
  .hero img {{ width: 100%; border-radius: 8px; margin-bottom: 20px; display: block; }}
  .hero h1 {{ margin: 0 0 6px; font-size: 1.4rem; font-weight: 600; }}
  .hero p {{ margin: 0; color: #9aa0a6; font-size: 0.88rem; }}
  .meta {{ display: flex; gap: 24px; margin-top: 18px; }}
  .meta-item {{ font-size: 0.8rem; }}
  .meta-label {{ color: #5f6368; text-transform: uppercase; letter-spacing: 0.04em; font-size: 0.68rem; display: block; margin-bottom: 3px; }}
  .meta-value {{ color: #fff; }}
  .body {{ padding: 28px; }}
  .greeting {{ font-size: 1.05rem; font-weight: 500; color: #0a0a0a; margin: 0 0 8px; }}
  .subtext {{ font-size: 0.9rem; color: #5f6368; line-height: 1.6; margin: 0 0 24px; }}
  .detail-row {{ display: flex; justify-content: space-between; padding: 10px 0; border-bottom: 1px solid #f0f0f0; font-size: 0.88rem; }}
  .detail-label {{ color: #5f6368; }}
  .detail-value {{ font-weight: 500; color: #0a0a0a; }}
  .btn {{ display: block; margin: 28px auto 0; background: #e3544a; color: #fff; text-decoration: none; padding: 14px 32px; border-radius: 8px; font-weight: 600; font-size: 0.95rem; text-align: center; max-width: 220px; }}
  .footer {{ text-align: center; padding: 20px 28px 28px; font-size: 0.78rem; color: #9aa0a6; line-height: 1.6; }}
</style>
</head>
<body>
<div class="wrap">
  <div class="hero">
    <img src="{flyer_url}" alt="Event Flyer">
    <h1>Big Fat Indian Scam Sangeet</h1>
    <p>Your ticket is confirmed!</p>
    <div class="meta">
      <div class="meta-item"><span class="meta-label">Date</span><span class="meta-value">27 Sep 2026</span></div>
      <div class="meta-item"><span class="meta-label">Time</span><span class="meta-value">6:00 PM</span></div>
      <div class="meta-item"><span class="meta-label">Venue</span><span class="meta-value">Eumsik Garden Restaurant</span></div>
    </div>
  </div>
  <div class="body">
    <p class="greeting">Hey {name}! 🎉</p>
    <p class="subtext">Your ticket for <strong>Big Fat Indian Scam Sangeet</strong> is confirmed. Present this ticket at the entrance and your organizer will scan you in.</p>
    <div class="detail-row"><span class="detail-label">Attendee</span><span class="detail-value">{name}</span></div>
    <div class="detail-row"><span class="detail-label">Category</span><span class="detail-value">{category}</span></div>
    <div class="detail-row"><span class="detail-label">Quantity</span><span class="detail-value">{quantity}</span></div>
    <div class="detail-row"><span class="detail-label">Date</span><span class="detail-value">27 Sep 2026 &middot; 6:00 PM</span></div>
    <div class="detail-row"><span class="detail-label">Venue</span><span class="detail-value">Eumsik Garden Restaurant</span></div>
    <a href="{ticket_url}" class="btn">Open My Ticket →</a>
  </div>
  <div class="footer">
    Open the link on your phone at the venue. The organizer's scanner will check you in instantly.<br>
    Questions? Reply to this email.
  </div>
</div>
</body>
</html>"""
        resp = _resend.Emails.send({
            "from": FROM_EMAIL,
            "to": [to_email],
            "subject": "Your Ticket – Big Fat Indian Scam Sangeet 🎟️",
            "html": html_body,
        })
        return {"ok": True, "id": getattr(resp, "id", str(resp))}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
