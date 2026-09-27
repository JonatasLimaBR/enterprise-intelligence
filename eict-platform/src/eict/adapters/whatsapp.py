"""Cliente da Cloud API do WhatsApp (Meta), no molde do `JiraClient`.

Distingue falha transitória (5xx/429/408/rede) de permanente (4xx: template não aprovado,
opt-in ausente) — o outbox decide backoff ou DLQ a partir dessa distinção.
"""

from __future__ import annotations

from dataclasses import dataclass

import requests

TIMEOUT_S = 30
RETRYABLE_STATUS = frozenset({408, 429, 500, 502, 503, 504})


class WhatsAppRetryableError(RuntimeError):
    pass


class WhatsAppPermanentError(RuntimeError):
    pass


@dataclass(frozen=True)
class WhatsAppMessage:
    message_id: str


@dataclass(frozen=True)
class WhatsAppClient:
    phone_number_id: str
    token: str
    api_version: str = "v21.0"
    session: requests.Session | None = None

    def send_template(self, to: str, name: str, lang: str, variables: tuple[str, ...]) -> WhatsAppMessage:
        payload = {
            "messaging_product": "whatsapp",
            "to": to,
            "type": "template",
            "template": {
                "name": name,
                "language": {"code": lang},
                "components": [
                    {"type": "body", "parameters": [{"type": "text", "text": value} for value in variables]}
                ],
            },
        }
        body = self._post(f"/{self.phone_number_id}/messages", payload)
        messages = body.get("messages") or []
        if not messages:
            raise WhatsAppPermanentError(f"whatsapp: resposta sem message id: {body}")
        return WhatsAppMessage(message_id=messages[0]["id"])

    def _post(self, path: str, payload: dict) -> dict:
        session = self.session or requests.Session()
        try:
            response = session.post(
                f"https://graph.facebook.com/{self.api_version}{path}",
                headers={"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"},
                json=payload,
                timeout=TIMEOUT_S,
            )
        except requests.RequestException as exc:
            raise WhatsAppRetryableError(f"whatsapp rede: {exc}") from exc
        if response.status_code in RETRYABLE_STATUS:
            raise WhatsAppRetryableError(f"whatsapp {response.status_code}: {response.text[:200]}")
        if response.status_code >= 400:
            raise WhatsAppPermanentError(f"whatsapp {response.status_code}: {response.text[:200]}")
        return response.json() if response.content else {}
