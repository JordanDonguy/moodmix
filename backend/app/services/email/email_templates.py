"""HTML and plain-text builders for transactional emails.

Kept separate from AuthService (and any other future sender) so the layout
lives in one place — adding a new transactional email is "write a body
function and call `_wrap` around it." Inline styles + table layout are
deliberate: real-world email clients (Outlook in particular) do not render
flexbox/grid or external stylesheets reliably.
"""

from __future__ import annotations

import html
from datetime import datetime, timezone

from app.config import settings

# Palette — kept neutral so it reads well in both light and dark email clients.
_BG = "#edf0f5"
_CARD_BG = "#ffffff"
_FOOTER_BORDER = "#dae1ed"
_TEXT_PRIMARY = "#111827"
_TEXT_SECONDARY = "#374151"
_TEXT_MUTED = "#6b7280"
_TEXT_FOOTER = "#9ca3af"
_CODE_BG = "#f3f4f6"
_HR = "#e5e7eb"


def format_sender(email: str) -> str:
    """Format a From header as `AppName <email@domain>` so inboxes show the
    friendly name instead of the raw `noreply@…` address.

    Used by every transactional sender — keeps the sender presentation in one
    place alongside the rest of the email shell.
    """
    return f"{settings.APP_NAME} <{email}>"


def signin_code_subject() -> str:
    return f"{settings.APP_NAME}: Your sign-in code"


def signin_code_text_body(code: str) -> str:
    return (
        f"Your {settings.APP_NAME} sign-in code is: {code}\n"
        f"\n"
        f"Enter the code on your device to sign in. It expires in 10 minutes.\n"
        f"\n"
        f"If you didn't make this request, you can safely ignore this email.\n"
        f"For security reasons, never share this code with anyone.\n"
        f"\n"
        f"— The {settings.APP_NAME} Team\n"
    )


def signin_code_html_body(code: str) -> str:
    body = f"""
        <p style="font-size:16px; text-align: center; color:{_TEXT_PRIMARY}; margin:0 0 8px;">
          Enter this code to sign in
        </p>

        <table align="center" cellpadding="0" cellspacing="0" border="0" style="margin:24px auto;">
          <tr>
            <td style="padding:16px 32px; background-color:{_CODE_BG}; border-radius:8px; text-align:center;
                       font-size:32px; font-weight:400; letter-spacing:8px; color:{_TEXT_PRIMARY};">
              {html.escape(code)}
            </td>
          </tr>
        </table>

        <p style="font-size:14px; color:{_TEXT_SECONDARY}; margin:0 0 12px;">
          Enter the code above on your device to sign in to {html.escape(settings.APP_NAME)}.
          This code expires in 10 minutes.
        </p>

        <p style="font-size:14px; color:{_TEXT_MUTED}; margin:0 0 12px;">
          If you didn&rsquo;t make this request, you can safely ignore this email.
        </p>

        <p style="font-size:13px; color:{_TEXT_MUTED}; margin:0;">
          For security reasons, never share this code with anyone.
        </p>

        <hr style="border:none; border-top:1px solid {_HR}; margin:24px 0;" />

        <p style="font-size:13px; color:{_TEXT_FOOTER}; margin:0;">
          The {html.escape(settings.APP_NAME)} Team
        </p>
    """
    return _wrap(title="Sign-in code", heading="Your Sign-in Code", body=body)


def _wrap(title: str, heading: str, body: str) -> str:
    """Wrap content in the standard email shell — logo, heading, footer.

    Inline styles + nested tables are intentional. Use the `body` argument for
    everything that varies per email type; everything outside it (header,
    footer, page styling) stays consistent across emails.
    """
    safe_title = html.escape(title)
    safe_heading = html.escape(heading)
    safe_app = html.escape(settings.APP_NAME)
    year = datetime.now(timezone.utc).year

    logo = ""
    if settings.APP_LOGO_URL:
        logo = (
            f'<img src="{html.escape(settings.APP_LOGO_URL)}" alt="{safe_app}" '
            f'style="height:48px; margin-bottom:12px;" />'
        )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <title>{safe_title}</title>
</head>
<body style="margin:0; padding:0; background-color:{_BG}; font-family: Arial, sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" border="0">
    <tr>
      <td align="center">
        <table width="600" cellpadding="0" cellspacing="0" border="0"
          style="background-color:{_CARD_BG}; overflow:hidden;">
          <tr>
            <td align="center" style="padding:32px 32px 16px 32px;">
              {logo}
              <h1 style="margin:0; font-size:32px; font-weight:700; color:{_TEXT_PRIMARY};">
                {safe_heading}
              </h1>
            </td>
          </tr>

          <tr>
            <td style="padding:0 32px 24px; font-size:16px; line-height:1.6; color:{_TEXT_PRIMARY};">
              {body}
            </td>
          </tr>

          <tr>
            <td style="border-top:1px solid {_FOOTER_BORDER}; text-align:center;
                       font-size:12px; color:{_TEXT_FOOTER}; padding:16px;">
              &copy; {year} {safe_app}. All rights reserved.
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>
"""
