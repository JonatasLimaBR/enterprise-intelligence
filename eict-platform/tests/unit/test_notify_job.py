"""Job `notify`: enfileirar, enviar, backoff/DLQ, link no incidente e retenção."""

from __future__ import annotations

import json
from datetime import UTC, datetime

from eict.adapters.whatsapp import WhatsAppMessage, WhatsAppPermanentError, WhatsAppRetryableError
from eict.config import Settings
from eict.domain.notifications import NotificationConfig, NotificationMessage
from eict.jobs import notify

AGORA = datetime(2026, 9, 27, 12, 0, tzinfo=UTC)
CFG = NotificationConfig(
    destination="+5511999999999",
    opt_in=True,
    threshold="high",
    template_name="eict_incident_alert",
    phone_number_id="123",
)


def _entry(attempts=0):
    return notify.OutboxEntry(
        dedup_key="inc-1|aberto",
        incident_id="inc-1",
        event="aberto",
        severity="critical",
        destination=CFG.destination,
        template_name=CFG.template_name,
        variables=("ABERTO · critical", "runtime_regression", "orders", "1.68 (2 ativos)", "x", "url"),
        attempts=attempts,
        created_at=AGORA,
    )


class _ClienteOk:
    def send_template(self, to, name, lang, variables):
        return WhatsAppMessage(message_id="wamid.OK")


class _ClienteRetry:
    def send_template(self, to, name, lang, variables):
        raise WhatsAppRetryableError("503")


class _ClientePermanente:
    def send_template(self, to, name, lang, variables):
        raise WhatsAppPermanentError("400 template not approved")


class _Spark:
    def __init__(self):
        self.sqls = []

    def sql(self, statement):
        self.sqls.append(statement)


def test_enqueue_row_nasce_pendente_com_send_after():
    msg = NotificationMessage("inc-1|aberto", "inc-1", "aberto", "critical", ("a",), AGORA)
    row = notify.enqueue_row(msg, CFG, AGORA)

    assert row["status"] == "pending"
    assert row["attempts"] == 0
    assert row["next_attempt_at"] == AGORA
    assert json.loads(row["variables_json"]) == ["a"]
    assert row["channel"] == "whatsapp"


def test_envio_ok_marca_sent_com_message_id():
    row = notify.dispatch_message(_ClienteOk(), _entry(), CFG, AGORA)

    assert row["status"] == "sent"
    assert row["message_id"] == "wamid.OK"
    assert row["created_at"] == AGORA  # preserva created_at (senão o UPDATE SET * zera)


def test_falha_transitoria_reagenda_com_backoff():
    row = notify.dispatch_message(_ClienteRetry(), _entry(attempts=1), CFG, AGORA)

    assert row["status"] == "pending"
    assert row["attempts"] == 2
    assert row["next_attempt_at"] is not None and row["next_attempt_at"] > AGORA


def test_falha_transitoria_esgotada_vai_para_dlq():
    row = notify.dispatch_message(_ClienteRetry(), _entry(attempts=4), CFG, AGORA)

    assert row["status"] == "failed"
    assert row["attempts"] == 5
    assert row["next_attempt_at"] is None


def test_erro_permanente_falha_na_primeira():
    row = notify.dispatch_message(_ClientePermanente(), _entry(), CFG, AGORA)

    assert row["status"] == "failed"
    assert "template not approved" in row["last_error"]


def test_due_entries_desserializa_variaveis(monkeypatch):
    registro = {
        "dedup_key": "inc-1|aberto",
        "incident_id": "inc-1",
        "event": "aberto",
        "severity": "critical",
        "destination": "+55",
        "template_name": "t",
        "variables_json": json.dumps(["a", "b"]),
        "attempts": 2,
        "created_at": AGORA,
    }
    monkeypatch.setattr(notify.store, "query", lambda spark, sql: [registro])

    [entry] = notify.due_entries(_Spark(), Settings(), AGORA)

    assert entry.variables == ("a", "b")
    assert entry.attempts == 2


def test_link_incident_so_grava_quando_enviado():
    spark = _Spark()
    enviado = notify._sent_row(_entry(), AGORA, "wamid.OK")
    notify.link_incident(spark, Settings(), enviado)

    assert spark.sqls and "notification_refs" in spark.sqls[0]
    assert "wamid.OK" in spark.sqls[0]


def test_link_incident_ignora_falha():
    spark = _Spark()
    notify.link_incident(spark, Settings(), notify._failed_row(_entry(), AGORA, "erro"))

    assert spark.sqls == []


def test_record_dlq_so_para_falha(monkeypatch):
    capturado = []
    monkeypatch.setattr(notify.store, "append_rows", lambda spark, table, rows: capturado.extend(rows))

    notify.record_dlq(_Spark(), Settings(), notify._failed_row(_entry(), AGORA, "erro"), AGORA)
    notify.record_dlq(_Spark(), Settings(), notify._sent_row(_entry(), AGORA, "wamid"), AGORA)

    assert len(capturado) == 1
    assert capturado[0]["source"] == "whatsapp"
    assert capturado[0]["error"] == "erro"


def test_purge_expired_emite_delete():
    spark = _Spark()
    notify.purge_expired(spark, Settings(), AGORA)

    assert spark.sqls and spark.sqls[0].startswith("DELETE FROM")
