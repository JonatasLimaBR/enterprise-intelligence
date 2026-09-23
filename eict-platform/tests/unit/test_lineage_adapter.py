"""O adapter que acumula o grafo e guarda a impressão digital anterior."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from eict.adapters import lineage
from eict.config import Settings
from eict.domain.impact import Edge

NOW = datetime(2026, 9, 22, 14, tzinfo=UTC)
ONTEM = NOW - timedelta(days=1)
SETTINGS = Settings()
ORDERS = "workspace.eict_workload.orders"
SALES = "workspace.eict_workload.sales_daily"


class _SparkFalso:
    """Devolve linhas por trecho de consulta e registra o que foi executado."""

    def __init__(self, por_trecho: dict[str, list[dict]] | None = None):
        self.por_trecho = por_trecho or {}
        self.consultas: list[str] = []
        self._atual: list[dict] = []
        self.catalog = self

    def sql(self, statement: str):
        self.consultas.append(statement)
        self._atual = []
        for trecho, linhas in self.por_trecho.items():
            if trecho in statement:
                self._atual = linhas
                break
        return self

    def collect(self):
        return [_LinhaFalsa(linha) for linha in self._atual]

    def createOrReplaceTempView(self, name: str) -> None:
        return None

    def dropTempView(self, name: str) -> None:
        return None

    def createDataFrame(self, rows, schema=None):
        self.gravadas = rows
        return self


class _LinhaFalsa:
    def __init__(self, dados: dict):
        self._dados = dados

    def asDict(self, recursive: bool = False) -> dict:
        return dict(self._dados)


def aresta(source: str = ORDERS, target: str = SALES, dias: int = 0) -> Edge:
    return Edge(
        source=source,
        target=target,
        entity_type="JOB",
        entity_id="job-1",
        last_seen=NOW - timedelta(days=dias),
    )


def test_at08_sem_capability_nao_consulta_nada():
    spark = _SparkFalso()

    assert lineage.fetch_edges(spark, SETTINGS, available=False) == ()
    assert spark.consultas == []


def test_consulta_que_falha_devolve_vazio_e_nao_propaga():
    class _Quebrado:
        def sql(self, statement: str):
            raise RuntimeError("system table indisponível")

    assert lineage.fetch_edges(_Quebrado(), SETTINGS, available=True) == ()
    assert lineage.load_graph(_Quebrado(), SETTINGS) == ()
    assert lineage.changed_assets(_Quebrado(), SETTINGS) == frozenset()


def test_arestas_vem_com_tipo_vazio_preservado():
    spark = _SparkFalso(
        {
            "table_lineage": [
                {
                    "source": ORDERS,
                    "target": SALES,
                    "entity_type": "",
                    "entity_id": "",
                    "last_seen": NOW,
                }
            ]
        }
    )

    arestas = lineage.fetch_edges(spark, SETTINGS, available=True)

    assert len(arestas) == 1
    assert arestas[0].is_uncertain


def test_at10_first_seen_do_ciclo_anterior_e_preservado():
    anterior = {"first_seen": ONTEM, "observed_cycles": 3, "schema_fingerprint": "abc"}

    linha = lineage._graph_row(aresta(), anterior, "abc", NOW)

    assert linha["first_seen"] == ONTEM
    assert linha["last_seen"] == NOW
    assert linha["observed_cycles"] == 4


def test_aresta_nova_estreia_com_first_seen_igual_a_last_seen():
    linha = lineage._graph_row(aresta(), {}, "abc", NOW)

    assert linha["first_seen"] == linha["last_seen"] == NOW
    assert linha["observed_cycles"] == 1


def test_d2_impressao_digital_anterior_e_guardada_quando_muda():
    """O MERGE sobrescreve a atual; sem guardar a anterior a mudança some."""
    anterior = {"schema_fingerprint": "hash-antigo", "first_seen": ONTEM}

    linha = lineage._graph_row(aresta(), anterior, "hash-novo", NOW)

    assert linha["schema_fingerprint"] == "hash-novo"
    assert linha["previous_fingerprint"] == "hash-antigo"
    assert linha["fingerprint_changed_at"] == NOW


def test_impressao_digital_igual_nao_marca_mudanca():
    anterior = {"schema_fingerprint": "mesmo", "first_seen": ONTEM}

    linha = lineage._graph_row(aresta(), anterior, "mesmo", NOW)

    assert linha["previous_fingerprint"] == ""
    assert linha["fingerprint_changed_at"] is None


def test_primeira_observacao_nao_conta_como_mudanca():
    """Nunca vista antes não é mudança — seria falso positivo em todo ativo novo."""
    linha = lineage._graph_row(aresta(), {}, "hash", NOW)

    assert linha["previous_fingerprint"] == ""
    assert linha["fingerprint_changed_at"] is None


def test_leitura_de_schema_vazia_nao_apaga_a_digital_guardada():
    """Se a consulta de schema falhar, manter o que se sabia é melhor que zerar."""
    anterior = {"schema_fingerprint": "guardada", "first_seen": ONTEM}

    linha = lineage._graph_row(aresta(), anterior, "", NOW)

    assert linha["schema_fingerprint"] == "guardada"
    assert linha["fingerprint_changed_at"] is None


def test_digital_de_schema_ignora_ordem_das_colunas():
    spark = _SparkFalso(
        {
            "information_schema.columns": [
                {
                    "table_catalog": "workspace",
                    "table_schema": "eict_workload",
                    "table_name": "orders",
                    "column_name": "b",
                    "data_type": "string",
                },
                {
                    "table_catalog": "workspace",
                    "table_schema": "eict_workload",
                    "table_name": "orders",
                    "column_name": "a",
                    "data_type": "int",
                },
            ]
        }
    )

    digitais = lineage.schema_fingerprints(spark, SETTINGS)

    assert set(digitais) == {ORDERS}
    assert digitais[ORDERS]


def test_merge_sem_observacoes_nao_toca_a_tabela():
    spark = _SparkFalso()

    assert lineage.merge_graph(spark, SETTINGS, (), {}, NOW) == 0
    assert spark.consultas == []
