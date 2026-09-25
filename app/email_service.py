from app import state
from app.config import BREVO_API_KEY, FROM_EMAIL, MAIL_DEFAULT_SENDER, MAIL_REPLY_TO, RESEND_API_KEY


def send_ticket_email(to_email: str, name: str, ticket_url: str, quantity: int, category: str) -> dict:
    if BREVO_API_KEY:
        try:
            import sib_api_v3_sdk
            from sib_api_v3_sdk.rest import ApiException

            configuration = sib_api_v3_sdk.Configuration()
            configuration.api_key["api-key"] = BREVO_API_KEY
            api_instance = sib_api_v3_sdk.TransactionalEmailsApi(sib_api_v3_sdk.ApiClient(configuration))

            flyer_url = f"{state.current_base_url}/static/images/BFISS.jpg" if state.current_base_url else "/static/images/BFISS.jpg"
            html_body = f"""
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Your Ticket – Big Fat Indian Scam Sangeet</title>
</head>
<body style="margin:0; padding:0; background:#eeece7; font-family:'Google Sans', Arial, Helvetica, sans-serif;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#eeece7; padding:32px 16px;">
  <tr>
    <td align="center">
      <table role="presentation" width="520" cellpadding="0" cellspacing="0" style="max-width:520px; width:100%; background:#ffffff; border-radius:16px; overflow:hidden; box-shadow:0 6px 24px rgba(10,10,10,0.07);">

        <tr>
          <td style="padding:18px 28px; border-bottom:1px solid #f0f0f0;">
            <span style="display:inline-block; width:8px; height:8px; border-radius:50%; background:#e3544a; margin-right:8px; vertical-align:middle;"></span>
            <span style="font-size:0.82rem; font-weight:700; color:#0a0a0a; letter-spacing:0.01em; vertical-align:middle;">SortMyEntries</span>
          </td>
        </tr>

        <tr>
          <td>
            <img src="{flyer_url}" alt="Event Flyer" width="520" style="display:block; width:100%; max-width:520px; height:220px; object-fit:cover;">
          </td>
        </tr>

        <tr>
          <td style="background:#0a0a0a; padding:22px 28px 20px; color:#ffffff;">
            <table role="presentation" cellpadding="0" cellspacing="0"><tr>
            </tr></table>
            <h1 style="margin:12px 0 4px; font-size:1.45rem; font-weight:600; line-height:1.3;">Big Fat Indian Scam Sangeet</h1>
            <p style="margin:0; color:#9aa0a6; font-size:0.85rem;">27 Sep 2026 &middot; 6:00 PM &middot; Eumsik Garden Restaurant</p>
          </td>
        </tr>

        <tr>
          <td style="padding:28px 28px 8px;">
            <p style="margin:0 0 6px; font-size:1.08rem; font-weight:600; color:#0a0a0a;">Hey {name}, you're all set! 🎉</p>
            <p style="margin:0 0 22px; font-size:0.9rem; color:#5f6368; line-height:1.6;">
              Your ticket for <strong>Big Fat Indian Scam Sangeet</strong> is confirmed. Here's everything you need for the door.
            </p>

            <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="font-size:0.88rem; margin-bottom:8px; background:#faf9f7; border-radius:10px;">
              <tr>
                <td style="padding:13px 16px; border-bottom:1px solid #eeece7; color:#5f6368;">Attendee</td>
                <td style="padding:13px 16px; border-bottom:1px solid #eeece7; text-align:right; font-weight:600; color:#0a0a0a;">{name}</td>
              </tr>
              <tr>
                <td style="padding:13px 16px; border-bottom:1px solid #eeece7; color:#5f6368;">Category</td>
                <td style="padding:13px 16px; border-bottom:1px solid #eeece7; text-align:right; font-weight:600; color:#0a0a0a;">{category}</td>
              </tr>
              <tr>
                <td style="padding:13px 16px; border-bottom:1px solid #eeece7; color:#5f6368;">Quantity</td>
                <td style="padding:13px 16px; border-bottom:1px solid #eeece7; text-align:right; font-weight:600; color:#0a0a0a;">{quantity}</td>
              </tr>
              <tr>
                <td style="padding:13px 16px; color:#5f6368;">Venue</td>
                <td style="padding:13px 16px; text-align:right; font-weight:600; color:#0a0a0a;">Eumsik Garden Restaurant</td>
              </tr>
            </table>
          </td>
        </tr>

        <tr>
          <td style="padding:8px 28px 4px;">
            <p style="margin:0 0 14px; font-size:0.75rem; font-weight:700; letter-spacing:0.04em; text-transform:uppercase; color:#9aa0a6;">How check-in works</p>
            <table role="presentation" width="100%" cellpadding="0" cellspacing="0">
              <tr>
                <td width="28" valign="top" style="padding:0 0 16px;">
                  <span style="display:inline-block; width:22px; height:22px; line-height:22px; border-radius:50%; background:#e3544a; color:#fff; font-size:0.72rem; font-weight:700; text-align:center;">1</span>
                </td>
                <td valign="top" style="padding:0 0 16px 12px; font-size:0.86rem; background:#000000; color:#3c4043;">Open your ticket on your phone using the button below.</td>
              </tr>
              <tr>
                <td width="28" valign="top" style="padding:0 0 16px;">
                  <span style="display:inline-block; width:22px; height:22px; line-height:22px; border-radius:50%; background:#e3544a; color:#fff; font-size:0.72rem; font-weight:700; text-align:center;">2</span>
                </td>
                <td valign="top" style="padding:0 0 16px 12px; font-size:0.86rem; background:#000000; color:#3c4043;">Head to the check-in point at the entrance.</td>
              </tr>
              <tr>
                <td width="28" valign="top" style="padding:0;">
                  <span style="display:inline-block; width:22px; height:22px; line-height:22px; border-radius:50%; background:#e3544a; color:#fff; font-size:0.72rem; font-weight:700; text-align:center;">3</span>
                </td>
                <td valign="top" style="padding:0 0 0 12px; font-size:0.86rem; background:#000000; color:#3c4043;">Scan the QR code yourself — you're checked in instantly.</td>
              </tr>
            </table>
          </td>
        </tr>

        <tr>
          <td style="padding:26px 28px 28px;">
            <table role="presentation" width="100%" cellpadding="0" cellspacing="0">
              <tr>
                <td align="center">
                  <a href="{ticket_url}" style="display:block; background:#e3544a; color:#ffffff; text-decoration:none; padding:15px 36px; border-radius:10px; font-weight:700; font-size:0.96rem;">Open My Ticket →</a>
                </td>
              </tr>
            </table>
          </td>
        </tr>

        <tr>
          <td style="padding:18px 28px 26px; text-align:center; font-size:0.76rem; color:#9aa0a6; line-height:1.6; border-top:1px solid #f0f0f0;">
            Keep this ticket handy on your phone — you'll need it at the check-in point.<br>
            Questions? Just reply to this email.<br><br>
            Ticketing by <strong style="color:#5f6368;">SortMyEntries</strong>
          </td>
        </tr>

      </table>
    </td>
  </tr>
</table>
</body>
</html>"""
            sender_email = MAIL_DEFAULT_SENDER or FROM_EMAIL
            reply_to_email = MAIL_REPLY_TO or FROM_EMAIL
            payload = sib_api_v3_sdk.SendSmtpEmail(
                to=[{"email": to_email, "name": name}],
                sender={"name": "SortMyEntries", "email": sender_email},
                reply_to={"email": reply_to_email, "name": "SortMyEntries"},
                subject="Your Ticket – Big Fat Indian Scam Sangeet 🎟️",
                html_content=html_body,
            )
            response = api_instance.send_transac_email(payload)
            return {"ok": True, "id": getattr(response, "message_id", None) or str(response)}
        except ApiException as exc:
            return {"ok": False, "error": exc.body or str(exc)}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    if not RESEND_API_KEY:
        return {"ok": False, "error": "BREVO_API_KEY / RESEND_API_KEY not configured"}

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
