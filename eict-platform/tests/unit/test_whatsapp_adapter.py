"""`WhatsAppClient.send_template`: envio, e a distinção transitório vs permanente."""

from __future__ import annotations

import pytest


class _Resposta:
    def __init__(self, status_code, body=None, text=""):
        self.status_code = status_code
        self._body = body if body is not None else {}
        self.text = text
        self.content = b"x"

    def json(self):
        return self._body


class _Sessao:
    def __init__(self, resposta):
        self.resposta = resposta

    def post(self, url, **kwargs):
        self.url = url
        self.kwargs = kwargs
        return self.resposta


def test_envio_bem_sucedido_devolve_message_id():
    from eict.adapters.whatsapp import WhatsAppClient

    sessao = _Sessao(_Resposta(200, {"messages": [{"id": "wamid.ABC"}]}))
    client = WhatsAppClient(phone_number_id="123", token="t", session=sessao)

    msg = client.send_template("+55119", "eict_incident_alert", "pt_BR", ("a", "b"))

    assert msg.message_id == "wamid.ABC"
    assert "123/messages" in sessao.url
    template = sessao.kwargs["json"]["template"]
    assert [p["text"] for p in template["components"][0]["parameters"]] == ["a", "b"]
    assert sessao.kwargs["headers"]["Authorization"] == "Bearer t"


def test_5xx_e_retryable():
    from eict.adapters.whatsapp import WhatsAppClient, WhatsAppRetryableError

    client = WhatsAppClient(phone_number_id="1", token="t", session=_Sessao(_Resposta(503, text="down")))
    with pytest.raises(WhatsAppRetryableError):
        client.send_template("+55", "t", "pt_BR", ("a",))


def test_429_e_retryable():
    from eict.adapters.whatsapp import WhatsAppClient, WhatsAppRetryableError

    client = WhatsAppClient(phone_number_id="1", token="t", session=_Sessao(_Resposta(429)))
    with pytest.raises(WhatsAppRetryableError):
        client.send_template("+55", "t", "pt_BR", ("a",))


def test_4xx_e_permanente():
    from eict.adapters.whatsapp import WhatsAppClient, WhatsAppPermanentError

    sessao = _Sessao(_Resposta(400, text="template not approved"))
    client = WhatsAppClient(phone_number_id="1", token="t", session=sessao)
    with pytest.raises(WhatsAppPermanentError):
        client.send_template("+55", "t", "pt_BR", ("a",))


def test_200_sem_message_id_e_permanente():
    from eict.adapters.whatsapp import WhatsAppClient, WhatsAppPermanentError

    client = WhatsAppClient(phone_number_id="1", token="t", session=_Sessao(_Resposta(200, {"messages": []})))
    with pytest.raises(WhatsAppPermanentError):
        client.send_template("+55", "t", "pt_BR", ("a",))


def test_erro_de_rede_e_retryable():
    import requests

    from eict.adapters.whatsapp import WhatsAppClient, WhatsAppRetryableError

    class _SessaoQuebrada:
        def post(self, url, **kwargs):
            raise requests.ConnectionError("sem rede")

    client = WhatsAppClient(phone_number_id="1", token="t", session=_SessaoQuebrada())
    with pytest.raises(WhatsAppRetryableError):
        client.send_template("+55", "t", "pt_BR", ("a",))
