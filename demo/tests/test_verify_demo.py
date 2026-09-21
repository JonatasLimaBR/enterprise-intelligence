from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import verify_demo  # noqa: E402

KIT = Path(__file__).resolve().parents[1]

NUMBERS = {
    "collected_at": "2026-09-21T00:00:00Z",
    "incident_id": "inc-teste",
    "facts": {
        "regression_factor": {"value": 5.7, "label": "fator", "source": "derivado"},
        "confidence": {"value": 0.9, "label": "confiança", "source": "tabela"},
        "cost": {"value": 0.0682, "label": "custo", "source": "tabela"},
    },
}


@pytest.fixture
def kit(tmp_path: Path) -> Path:
    (tmp_path / "numbers.json").write_text(json.dumps(NUMBERS), encoding="utf-8")
    return tmp_path


def write(base: Path, name: str, content: str) -> Path:
    path = base / name
    path.write_text(content, encoding="utf-8")
    return path


def test_numero_sem_origem_e_apontado(kit: Path):
    document = write(kit, "ROTEIRO.md", "O fator foi de 9.9 vezes.")

    findings = verify_demo.check_numbers(document, verify_demo.known_values(NUMBERS))

    assert [finding.kind for finding in findings] == ["numero_sem_origem"]
    assert "9.9" in findings[0].detail


def test_numero_com_origem_passa(kit: Path):
    document = write(kit, "ROTEIRO.md", "O fator foi de 5.7 vezes, com 0.9 de confiança.")

    assert verify_demo.check_numbers(document, verify_demo.known_values(NUMBERS)) == []


def test_virgula_decimal_e_aceita(kit: Path):
    document = write(kit, "ROTEIRO.md", "Fator de 5,7 vezes.")

    assert verify_demo.check_numbers(document, verify_demo.known_values(NUMBERS)) == []


def test_linha_de_referencia_documental_e_ignorada(kit: Path):
    document = write(kit, "ROTEIRO.md", "Ver PRD-010 e SPEC-004 para detalhes.")

    assert verify_demo.check_numbers(document, verify_demo.known_values(NUMBERS)) == []


FAKE_SECRETS = {
    "e-mail": "contato: alguem@gmail.com",
    "token databricks": "token " + "dapi" + "0" * 32,
    "host": "host https://dbc-" + "a" * 8 + "-" + "b" * 4 + ".cloud.databricks.com",
    "warehouse": "warehouse " + "c" * 16,
}


@pytest.mark.parametrize("conteudo", FAKE_SECRETS.values(), ids=FAKE_SECRETS.keys())
def test_segredos_sao_detectados(kit: Path, conteudo: str):
    document = write(kit, "ROTEIRO.md", conteudo)

    assert [finding.kind for finding in verify_demo.check_secrets(document)] == ["segredo"]


def test_texto_limpo_nao_acusa_segredo(kit: Path):
    document = write(kit, "ROTEIRO.md", "O incidente aponta 3 ativos afetados.")

    assert verify_demo.check_secrets(document) == []


def test_roteiro_acima_do_orcamento_e_reprovado(kit: Path):
    document = write(kit, "ROTEIRO.md", "palavra " * 1500)

    findings = verify_demo.check_word_budget(document)

    assert findings and findings[0].kind == "roteiro_longo"


def test_roteiro_dentro_do_orcamento_passa(kit: Path):
    document = write(kit, "ROTEIRO.md", "palavra " * 500)

    assert verify_demo.check_word_budget(document) == []


def test_numero_de_blocos_e_conferido(kit: Path):
    document = write(kit, "ROTEIRO.md", "## 1. Um\n## 2. Dois\n")

    findings = verify_demo.check_blocks(document)

    assert findings and "2 blocos" in findings[0].detail


def test_imagem_faltando_e_apontada(kit: Path):
    document = write(kit, "README.md", "![tela](img/01-lista.png)")

    findings = verify_demo.check_images(document, kit)

    assert [finding.kind for finding in findings] == ["imagem_faltando"]


def test_imagem_existente_passa(kit: Path):
    (kit / "img").mkdir()
    (kit / "img" / "01-lista.png").write_bytes(b"fake")
    document = write(kit, "README.md", "![tela](img/01-lista.png)")

    assert verify_demo.check_images(document, kit) == []


def test_imagem_remota_e_ignorada(kit: Path):
    document = write(kit, "README.md", "![tela](https://exemplo.com/a.png)")

    assert verify_demo.check_images(document, kit) == []


def test_perguntas_cobertas(kit: Path):
    linhas = "\n".join(f"| {index} | pergunta | destino | estado |" for index in range(1, 11))
    document = write(kit, "PERGUNTAS.md", f"| # | P | Onde | Estado |\n|---|---|---|---|\n{linhas}")

    assert verify_demo.check_questions(document) == []


def test_perguntas_incompletas_sao_apontadas(kit: Path):
    document = write(kit, "PERGUNTAS.md", "| 1 | pergunta | destino | estado |")

    findings = verify_demo.check_questions(document)

    assert findings and "1 perguntas" in findings[0].detail


def test_capturas_tem_campos(kit: Path):
    completo = write(kit, "CAPTURAS.md", "- **Arquivo:** a\n- **Tela:** b\n- **Estado:** c")
    incompleto = write(kit, "OUTRO.md", "- **Arquivo:** a")

    assert verify_demo.check_captures(completo) == []
    assert verify_demo.check_captures(incompleto)[0].kind == "capturas"


def test_paridade_pt_en(kit: Path):
    original = write(kit, "ROTEIRO.md", "Fator de 5.7 e confiança 0.9.")
    fiel = write(kit, "ROTEIRO.en.md", "Factor of 5.7 and confidence 0.9.")
    defasada = write(kit, "OUTRA.en.md", "Factor of 5.7 only.")

    assert verify_demo.check_translation_parity(original, fiel) == []
    findings = verify_demo.check_translation_parity(original, defasada)
    assert findings and "0.9" in findings[0].detail


def test_kit_real_nao_tem_erros():
    errors, _ = verify_demo.split_by_severity(verify_demo.run(KIT))

    assert [str(finding) for finding in errors] == []


def test_imagem_faltando_e_aviso_nao_erro():
    findings = [
        verify_demo.Finding("README.md", "imagem_faltando", "img/a.png"),
        verify_demo.Finding("ROTEIRO.md", "numero_sem_origem", "9.9"),
    ]

    errors, warnings = verify_demo.split_by_severity(findings)

    assert [item.kind for item in errors] == ["numero_sem_origem"]
    assert [item.kind for item in warnings] == ["imagem_faltando"]


def test_modo_estrito_reprova_captura_pendente(tmp_path, monkeypatch):
    monkeypatch.setattr(verify_demo, "run", lambda base: [
        verify_demo.Finding("README.md", "imagem_faltando", "img/a.png")
    ])

    assert verify_demo.main([f"--base={tmp_path}"]) == 0
    assert verify_demo.main([f"--base={tmp_path}", "--strict"]) == 1


def test_css_e_script_nao_viram_numeros(kit: Path):
    document = write(
        kit,
        "deck.html",
        """<style>body { font-size: 18px; line-height: 1.6; }</style>
<script>let index = 42;</script>
<section><p>O fator foi de 5.7 vezes.</p></section>""",
    )

    assert verify_demo.check_numbers(document, verify_demo.known_values(NUMBERS)) == []


def test_numero_visivel_em_html_ainda_e_conferido(kit: Path):
    document = write(kit, "deck.html", "<section><p>O fator foi de 9.9 vezes.</p></section>")

    findings = verify_demo.check_numbers(document, verify_demo.known_values(NUMBERS))

    assert [finding.kind for finding in findings] == ["numero_sem_origem"]


def test_segredo_em_atributo_html_e_detectado(kit: Path):
    host = "dbc-" + "a" * 8 + "-" + "b" * 4 + ".cloud.databricks.com"
    document = write(kit, "deck.html", f'<a href="https://{host}">x</a>')

    assert [finding.kind for finding in verify_demo.check_secrets(document)] == ["segredo"]
