"""`GitHubClient.fetch_file`: o conteúdo do arquivo no commit, que a etapa `semantics` extrai."""

from __future__ import annotations


def test_fetch_file_devolve_o_conteudo():
    from eict.adapters.github import GitHubClient

    class _Resposta:
        status_code = 200
        text = "def build(): pass"

    class _Sessao:
        def get(self, url, **kwargs):
            self.url = url
            self.kwargs = kwargs
            return _Resposta()

    sessao = _Sessao()
    conteudo = GitHubClient(repo="acme/eict", session=sessao).fetch_file("src/a.py", "abc123")

    assert conteudo == "def build(): pass"
    assert "contents/src/a.py" in sessao.url
    assert sessao.kwargs["params"] == {"ref": "abc123"}


def test_at16_arquivo_inexistente_devolve_vazio_sem_excecao():
    from eict.adapters.github import GitHubClient

    class _Resposta:
        status_code = 404
        text = ""

    class _Sessao:
        def get(self, url, **kwargs):
            return _Resposta()

    assert GitHubClient(repo="acme/eict", session=_Sessao()).fetch_file("sumiu.py") == ""


def test_erro_do_github_sobe_como_erro_proprio():
    import pytest

    from eict.adapters.github import GitHubClient, GitHubError

    class _Resposta:
        status_code = 500
        text = ""

    class _Sessao:
        def get(self, url, **kwargs):
            return _Resposta()

    with pytest.raises(GitHubError):
        GitHubClient(repo="acme/eict", session=_Sessao()).fetch_file("a.py")
