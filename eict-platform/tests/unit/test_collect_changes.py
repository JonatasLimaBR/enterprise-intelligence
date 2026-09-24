"""O caminho real da coleta de commits com a DLQ com estado (AT-06…09, AT-13)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from eict.adapters.github import GitHubError
from eict.adapters.store import dlq_row, to_dlq_entries
from eict.config import Settings
from eict.domain.connectors import PERMANENTE, QUARANTINED, RESOLVED, RETRYING, record_failure
from eict.jobs.collect import fetch_changes

AGORA = datetime(2026, 9, 24, 21, tzinfo=UTC)
SHA_BOM = "a" * 40
SHA_FANTASMA = "090e7938cd40d33bfb067a1e63e1a827b6d89a47"
SETTINGS = Settings()


class _GitHub:
    def __init__(self, falhas: dict[str, int]):
        self.falhas = falhas
        self.pedidos: list[str] = []

    def commit(self, sha):
        from eict.domain.models import Change

        self.pedidos.append(sha)
        if sha in self.falhas:
            raise GitHubError(f"github {self.falhas[sha]} for commit {sha}", self.falhas[sha])
        return Change(sha=sha, repo="r", author="a", committed_at=AGORA, message="m", files=(), patch="")


def _buscar(github, pendentes, dlq=None, agora=AGORA):
    return fetch_changes(github, pendentes, dlq or {}, SETTINGS, "fonte", agora)


def test_422_vai_para_a_quarentena_e_o_bom_segue():
    github = _GitHub({SHA_FANTASMA: 422})

    envelopes, alteradas, erro, sucessos = _buscar(github, [SHA_BOM, SHA_FANTASMA])

    assert sucessos == 1 and len(envelopes) == 1
    assert [item.status for item in alteradas] == [QUARANTINED]
    assert "422" in erro


def test_at06_quarentena_nao_e_buscada_de_novo():
    quarentena = record_failure(None, f"github-{SHA_FANTASMA}", "github", SHA_FANTASMA, "422", 422, AGORA)
    github = _GitHub({})

    _buscar(github, [SHA_FANTASMA], {quarentena.dlq_id: quarentena}, AGORA + timedelta(days=3))

    assert github.pedidos == []


def test_at07_retentativa_antes_da_hora_nao_busca():
    retentando = record_failure(None, f"github-{SHA_BOM}", "github", SHA_BOM, "503", 503, AGORA)
    github = _GitHub({})

    _buscar(github, [SHA_BOM], {retentando.dlq_id: retentando}, AGORA + timedelta(minutes=2))

    assert github.pedidos == []


def test_at08_fonte_voltou_resolve():
    retentando = record_failure(None, f"github-{SHA_BOM}", "github", SHA_BOM, "503", 503, AGORA)

    envelopes, alteradas, erro, _ = _buscar(
        _GitHub({}), [SHA_BOM], {retentando.dlq_id: retentando}, AGORA + timedelta(minutes=6)
    )

    assert len(envelopes) == 1
    assert [item.status for item in alteradas] == [RESOLVED]
    assert erro is None


def test_at09_segunda_falha_atualiza_a_mesma_entrada():
    primeira = record_failure(None, f"github-{SHA_BOM}", "github", SHA_BOM, "503", 503, AGORA)

    _, alteradas, _, _ = _buscar(
        _GitHub({SHA_BOM: 503}), [SHA_BOM], {primeira.dlq_id: primeira}, AGORA + timedelta(minutes=6)
    )

    assert alteradas[0].dlq_id == primeira.dlq_id
    assert alteradas[0].attempts == 2
    assert alteradas[0].status == RETRYING


def test_at13_as_7_linhas_legadas_viram_uma_em_quarentena():
    """O caso real: 7 linhas anexadas para o mesmo commit, só com o texto do erro."""
    legado = [
        {
            "dlq_id": f"github-{SHA_FANTASMA}",
            "source": "github",
            "payload": SHA_FANTASMA,
            "error": f"github 422 for commit {SHA_FANTASMA}",
            "at": AGORA - timedelta(hours=dia),
        }
        for dia in range(7)
    ]

    entradas = to_dlq_entries(legado)

    assert len(entradas) == 1
    assert entradas[0].attempts == 7
    assert entradas[0].status == QUARANTINED
    assert entradas[0].error_class == PERMANENTE
    assert entradas[0].first_at == AGORA - timedelta(hours=6)


def test_linha_com_estado_e_lida_como_esta():
    entrada = record_failure(None, "github-x", "github", "x", "503", 503, AGORA)

    relida = to_dlq_entries([dlq_row(entrada)])[0]

    assert relida == entrada
