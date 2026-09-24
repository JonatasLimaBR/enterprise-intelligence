"""Trilha de auditoria com cadeia de hash.

Cada linha carrega o hash da anterior. A tabela é `delta.appendOnly` — o Delta recusa UPDATE e
DELETE —, e a cadeia denuncia o que o Delta não impede: a tabela recriada ou editada por fora.

Não há trava na escrita. Dois cliques simultâneos leem o mesmo último hash e geram duas linhas
com o mesmo pai. Isso é **bifurcação**, não adulteração: as duas linhas são íntegras. O
verificador separa os dois casos.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

GENESIS = "0" * 64

INTEGRA = "integra"
BIFURCADA = "bifurcada"
ADULTERADA = "adulterada"

_CAMPOS = ("at", "actor", "identity_source", "roles", "action", "target", "decision", "reason")


def canonical_time(at: datetime) -> str:
    """Instante em UTC com segundos — a mesma forma ao gravar e ao verificar.

    Instante sem fuso é UTC (é como o banco o devolve). `astimezone` o trataria como horário
    local do servidor, deslocaria o valor e toda a trilha pareceria adulterada.
    """
    if at.tzinfo is None:
        at = at.replace(tzinfo=UTC)
    return at.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def row_hash(row: dict, prev_hash: str) -> str:
    """sha256 do JSON canônico (chaves ordenadas) dos campos da linha e do hash anterior."""
    corpo = {campo: row.get(campo) for campo in _CAMPOS}
    corpo["at"] = canonical_time(row["at"]) if isinstance(row.get("at"), datetime) else row.get("at")
    corpo["prev_hash"] = prev_hash
    return hashlib.sha256(json.dumps(corpo, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def entry(
    last: dict | None,
    at: datetime,
    actor: str,
    roles: frozenset[str],
    action: str,
    target: str,
    decision: str,
    reason: str,
    identity_source: str = "forwarded_header",
) -> dict:
    """A próxima linha da trilha, encadeada à última gravada (ou à gênese)."""
    anterior = last["hash"] if last else GENESIS
    linha = {
        "seq": (int(last["seq"]) + 1) if last else 1,
        "audit_id": str(uuid.uuid4()),
        "at": at.astimezone(UTC).replace(microsecond=0),
        "actor": actor,
        "identity_source": identity_source,
        "roles": ",".join(sorted(roles)),
        "action": action,
        "target": target,
        "decision": decision,
        "reason": reason,
        "prev_hash": anterior,
    }
    linha["hash"] = row_hash(linha, anterior)
    return linha


@dataclass(frozen=True)
class Verdict:
    status: str
    first_bad_seq: int | None = None
    detail: str = ""
    forks: tuple[int, ...] = ()


def verify(rows: list[dict]) -> Verdict:
    """Percorre em ordem de `seq` e aponta a primeira linha adulterada.

    Adulteração: o hash não confere (linha editada) ou o pai não existe entre as anteriores
    (linha apagada). Bifurcação: pais repetidos com linhas íntegras — escrita concorrente.
    """
    vistos = {GENESIS}
    filhos_por_pai: dict[str, list[int]] = {}
    for row in sorted(rows, key=lambda item: (int(item["seq"]), str(item.get("audit_id")))):
        seq = int(row["seq"])
        if row_hash(row, row["prev_hash"]) != row["hash"]:
            return Verdict(ADULTERADA, seq, f"linha {seq}: hash não confere com o conteúdo")
        if row["prev_hash"] not in vistos:
            return Verdict(ADULTERADA, seq, f"linha {seq}: aponta para uma linha que não existe (apagada?)")
        filhos_por_pai.setdefault(row["prev_hash"], []).append(seq)
        vistos.add(row["hash"])
    forks = tuple(sorted(seq for filhos in filhos_por_pai.values() if len(filhos) > 1 for seq in filhos))
    if forks:
        return Verdict(BIFURCADA, detail="escritas concorrentes com o mesmo pai; linhas íntegras", forks=forks)
    return Verdict(INTEGRA)
