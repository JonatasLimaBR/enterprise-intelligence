"""Adapter Jev: decide (ok/sem token/erro → None) e carga da config (egress off por padrão)."""

from __future__ import annotations


class _Resp:
    def __init__(self, status_code, body=None):
        self.status_code = status_code
        self._body = body if body is not None else {}
        self.content = b"x"

    def json(self):
        return self._body


class _Sessao:
    def __init__(self, resp):
        self.resp = resp
        self.chamou = False

    def post(self, url, **kwargs):
        self.chamou = True
        self.kwargs = kwargs
        return self.resp


def test_decide_ok_devolve_answer():
    from eict.adapters.jev import JevClient

    sessao = _Sessao(_Resp(200, {"q": {"value": "sim", "confidence": 0.82}}))
    ans = JevClient(token="t", session=sessao).decide({"a": 1}, {"type": "noul"})

    assert ans.value == "sim" and ans.confidence == 0.82
    assert sessao.kwargs["headers"]["Authorization"] == "Bearer t"


def test_decide_sem_token_nao_chama():
    from eict.adapters.jev import JevClient

    sessao = _Sessao(_Resp(200, {"q": {"value": "s", "confidence": 1.0}}))
    assert JevClient(token="", session=sessao).decide({}, {}) is None
    assert sessao.chamou is False  # egress off sem token


def test_decide_http_erro_e_none():
    from eict.adapters.jev import JevClient

    assert JevClient(token="t", session=_Sessao(_Resp(500))).decide({}, {}) is None


def test_decide_resposta_sem_campos_e_none():
    from eict.adapters.jev import JevClient

    assert JevClient(token="t", session=_Sessao(_Resp(200, {"q": {"value": "s"}}))).decide({}, {}) is None


def test_decide_erro_de_rede_e_none():
    import requests

    from eict.adapters.jev import JevClient

    class _Quebrada:
        def post(self, url, **kwargs):
            raise requests.ConnectionError("sem rede")

    assert JevClient(token="t", session=_Quebrada()).decide({}, {}) is None


def test_config_ausente_tudo_desligado(tmp_path):
    from eict.adapters.jev import load_jev_config

    assert load_jev_config(tmp_path).enabled == frozenset()
    assert load_jev_config("").enabled == frozenset()


def test_config_valida_filtra_desconhecidos(tmp_path):
    from eict.adapters.jev import load_jev_config

    (tmp_path / "advisors.yaml").write_text("enabled: [triage, xpto]\nthreshold: 0.8\n", encoding="utf-8")
    cfg = load_jev_config(tmp_path)

    assert cfg.enabled == frozenset({"triage"})  # 'xpto' descartado
    assert cfg.threshold == 0.8


def test_config_invalida_desliga(tmp_path):
    from eict.adapters.jev import load_jev_config

    (tmp_path / "advisors.yaml").write_text("enabled: [1, 2\n", encoding="utf-8")
    assert load_jev_config(tmp_path).enabled == frozenset()
