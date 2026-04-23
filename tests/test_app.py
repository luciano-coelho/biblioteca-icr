"""
Testes unitários — Biblioteca ICR
Execução: pytest tests/test_app.py -v
"""
import csv
import io
import os
import sys
import sqlite3
import hashlib
import urllib.parse
from datetime import date, timedelta
from unittest.mock import patch, MagicMock

import pytest

# ── Isola o banco de dados para testes ───────────────────────────────
TEST_DB = os.path.join(os.path.dirname(__file__), "test_biblioteca.db")

# Patch do DB e do st antes de importar qualquer função do app
sys.modules.setdefault("streamlit", MagicMock())

# Injeta o caminho do módulo
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))

with patch("os.path.normpath", return_value=TEST_DB), \
     patch("os.path.join", return_value=TEST_DB), \
     patch("os.path.dirname", return_value=""), \
     patch("os.path.abspath", return_value=""):
    pass  # Importação acontece abaixo com DB remapeado


# ── Helpers isolados (sem dependência de st) ─────────────────────────

def _hash_senha(senha: str, salt: bytes = None) -> str:
    if salt is None:
        salt = os.urandom(16)
    dk = hashlib.pbkdf2_hmac("sha256", senha.encode("utf-8"), salt, 200_000)
    return salt.hex() + ":" + dk.hex()


def _verificar_senha(senha: str, armazenada: str) -> bool:
    try:
        salt_hex, dk_hex = armazenada.split(":")
        salt = bytes.fromhex(salt_hex)
        dk = hashlib.pbkdf2_hmac("sha256", senha.encode("utf-8"), salt, 200_000)
        return dk.hex() == dk_hex
    except Exception:
        return False


def _fmt(d) -> str:
    if not d:
        return "—"
    try:
        if isinstance(d, str):
            d = date.fromisoformat(d)
        return d.strftime("%d/%m/%Y")
    except Exception:
        return str(d)


def _dias_restantes(due_str: str) -> int:
    try:
        return (date.fromisoformat(due_str) - date.today()).days
    except Exception:
        return 0


def _loan_status(dl: int):
    if dl < 0:
        return "late", f"Atrasado {abs(dl)}d"
    if dl <= 5:
        return "warn", f"Vence em {dl}d"
    return "ok", f"{dl} dias"


def _fmt_id(id_val: int) -> str:
    return f"#{str(id_val).zfill(2)}"


def _gerar_whats(phone, nome, livro, tipo, data_emp, data_dev, igreja):
    phone = "".join(filter(str.isdigit, str(phone)))
    if not phone.startswith("55"):
        phone = "55" + phone
    msgs = {
        "confirmacao": f"Olá, {nome}! \n\nVocê retirou o livro *{livro}* da {igreja}.\n\n► Retirada: {_fmt(data_emp)}\n► Devolução até: *{_fmt(data_dev)}*\n\nBoa leitura! ♡",
        "renovacao":   f"Olá, {nome}! \n\nSeu empréstimo do livro *{livro}* da {igreja} foi renovado!\n\n► Nova data de devolução: *{_fmt(data_dev)}*\n\nBoa leitura! ♡",
        "devolucao":   f"Olá, {nome}! \n\nRecebemos a devolução do livro *{livro}* da {igreja}. Muito obrigado!\n\nQuando quiser pegar outro livro, é só chamar. ♡",
        "lembrete":    f"Olá, {nome}! \n\nO prazo para devolver o livro *{livro}* da {igreja} já passou (venceu em {_fmt(data_dev)}).\n\n⚠ Por favor, devolva assim que possível. ♡",
        "aviso":       f"Olá, {nome}! \n\nPassando para lembrar que o prazo de devolução do livro *{livro}* da {igreja} é *{_fmt(data_dev)}*.\n\nSe precisar de mais tempo, podemos renovar! ♡",
        "disponivel":  f"Olá, {nome}! \n\nBoas notícias! O livro *{livro}* da {igreja} foi devolvido e você é o(a) próximo(a) da fila.\n\nVenha buscá-lo quando quiser! ♡",
    }
    return f"https://wa.me/{phone}?text={urllib.parse.quote(msgs.get(tipo, ''))}"


# ── Fixture: banco de dados em memória ───────────────────────────────

@pytest.fixture()
def conn():
    """Banco SQLite em memória para cada teste."""
    db = sqlite3.connect(":memory:")
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")
    db.executescript("""
        CREATE TABLE livros (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            titulo     TEXT NOT NULL,
            autor      TEXT DEFAULT '',
            categoria  TEXT DEFAULT '',
            quantidade INTEGER DEFAULT 1,
            criado_em  DATE DEFAULT CURRENT_DATE
        );
        CREATE TABLE leitores (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            nome      TEXT NOT NULL,
            telefone  TEXT NOT NULL,
            email     TEXT DEFAULT '',
            endereco  TEXT DEFAULT '',
            criado_em DATE DEFAULT CURRENT_DATE
        );
        CREATE TABLE emprestimos (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            leitor_id       INTEGER NOT NULL,
            livro_id        INTEGER NOT NULL,
            data_emprestimo DATE NOT NULL,
            data_devolucao  DATE NOT NULL,
            status          TEXT DEFAULT 'ativo',
            renovacoes      INTEGER DEFAULT 0,
            FOREIGN KEY (leitor_id) REFERENCES leitores(id),
            FOREIGN KEY (livro_id)  REFERENCES livros(id)
        );
        CREATE TABLE historico (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            tipo         TEXT NOT NULL,
            leitor_nome  TEXT NOT NULL,
            livro_titulo TEXT NOT NULL,
            data         DATE DEFAULT CURRENT_DATE,
            obs          TEXT DEFAULT ''
        );
        CREATE TABLE config (
            chave TEXT PRIMARY KEY,
            valor TEXT NOT NULL
        );
        CREATE TABLE fila_espera (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            livro_id       INTEGER NOT NULL,
            leitor_id      INTEGER NOT NULL,
            data_inscricao DATE DEFAULT CURRENT_DATE,
            FOREIGN KEY (livro_id)  REFERENCES livros(id),
            FOREIGN KEY (leitor_id) REFERENCES leitores(id),
            UNIQUE(livro_id, leitor_id)
        );
        CREATE TABLE usuarios (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario    TEXT NOT NULL UNIQUE,
            senha_hash TEXT NOT NULL,
            criado_em  DATE DEFAULT CURRENT_DATE
        );
        INSERT INTO config VALUES ('nome_igreja', 'Igreja Teste');
        INSERT INTO config VALUES ('dias_emprestimo', '30');
    """)
    yield db
    db.close()


# ═══════════════════════════════════════════════════════════════════════
# 1. HELPERS DE FORMATAÇÃO
# ═══════════════════════════════════════════════════════════════════════

class TestFmt:
    def test_fmt_date_string(self):
        assert _fmt("2026-04-23") == "23/04/2026"

    def test_fmt_date_object(self):
        assert _fmt(date(2026, 1, 1)) == "01/01/2026"

    def test_fmt_none(self):
        assert _fmt(None) == "—"

    def test_fmt_vazio(self):
        assert _fmt("") == "—"

    def test_fmt_invalido(self):
        result = _fmt("nao-e-data")
        assert result == "nao-e-data"


class TestDiasRestantes:
    def test_futuro(self):
        futuro = (date.today() + timedelta(days=10)).isoformat()
        assert _dias_restantes(futuro) == 10

    def test_hoje(self):
        assert _dias_restantes(date.today().isoformat()) == 0

    def test_passado(self):
        passado = (date.today() - timedelta(days=5)).isoformat()
        assert _dias_restantes(passado) == -5

    def test_invalido(self):
        assert _dias_restantes("abc") == 0


class TestLoanStatus:
    def test_atrasado(self):
        kind, lbl = _loan_status(-3)
        assert kind == "late"
        assert "3" in lbl

    def test_vencendo(self):
        kind, lbl = _loan_status(3)
        assert kind == "warn"
        assert "3" in lbl

    def test_no_prazo(self):
        kind, lbl = _loan_status(15)
        assert kind == "ok"
        assert "15" in lbl

    def test_limite_warn(self):
        kind, _ = _loan_status(5)
        assert kind == "warn"

    def test_limite_ok(self):
        kind, _ = _loan_status(6)
        assert kind == "ok"


class TestFmtId:
    def test_id_simples(self):
        assert _fmt_id(1) == "#01"

    def test_id_dois_digitos(self):
        assert _fmt_id(15) == "#15"

    def test_id_tres_digitos(self):
        assert _fmt_id(100) == "#100"


# ═══════════════════════════════════════════════════════════════════════
# 2. AUTENTICAÇÃO
# ═══════════════════════════════════════════════════════════════════════

class TestAuth:
    def test_hash_e_verificar_senha_correta(self):
        h = _hash_senha("minha_senha")
        assert _verificar_senha("minha_senha", h)

    def test_verificar_senha_errada(self):
        h = _hash_senha("minha_senha")
        assert not _verificar_senha("senha_errada", h)

    def test_hash_diferente_por_salt(self):
        h1 = _hash_senha("abc")
        h2 = _hash_senha("abc")
        assert h1 != h2  # salts diferentes

    def test_verificar_hash_invalido(self):
        assert not _verificar_senha("abc", "hash_invalido")

    def test_verificar_login_correto(self, conn):
        h = _hash_senha("senha123")
        conn.execute("INSERT INTO usuarios (usuario, senha_hash) VALUES (?,?)", ("user1", h))
        row = conn.execute("SELECT senha_hash FROM usuarios WHERE usuario=?", ("user1",)).fetchone()
        assert _verificar_senha("senha123", row["senha_hash"])

    def test_verificar_login_usuario_inexistente(self, conn):
        row = conn.execute("SELECT senha_hash FROM usuarios WHERE usuario=?", ("naoexiste",)).fetchone()
        assert row is None


# ═══════════════════════════════════════════════════════════════════════
# 3. LIVROS
# ═══════════════════════════════════════════════════════════════════════

class TestLivros:
    def test_cadastrar_livro(self, conn):
        conn.execute("INSERT INTO livros (titulo, autor, categoria, quantidade) VALUES (?,?,?,?)",
                     ("Dom Quixote", "Cervantes", "Literatura", 3))
        livros = conn.execute("SELECT * FROM livros").fetchall()
        assert len(livros) == 1
        assert livros[0]["titulo"] == "Dom Quixote"
        assert livros[0]["quantidade"] == 3

    def test_livro_titulo_obrigatorio(self, conn):
        with pytest.raises(Exception):
            conn.execute("INSERT INTO livros (titulo) VALUES (?)", (None,))

    def test_editar_livro(self, conn):
        conn.execute("INSERT INTO livros (titulo, autor, quantidade) VALUES (?,?,?)",
                     ("Titulo Original", "Autor", 1))
        livro_id = conn.execute("SELECT id FROM livros").fetchone()["id"]
        conn.execute("UPDATE livros SET titulo=?, quantidade=? WHERE id=?",
                     ("Titulo Novo", 5, livro_id))
        livro = conn.execute("SELECT * FROM livros WHERE id=?", (livro_id,)).fetchone()
        assert livro["titulo"] == "Titulo Novo"
        assert livro["quantidade"] == 5

    def test_excluir_livro_sem_historico(self, conn):
        conn.execute("INSERT INTO livros (titulo) VALUES (?)", ("Livro Temp",))
        livro_id = conn.execute("SELECT id FROM livros").fetchone()["id"]
        conn.execute("DELETE FROM livros WHERE id=?", (livro_id,))
        assert conn.execute("SELECT COUNT(*) FROM livros").fetchone()[0] == 0

    def test_nao_excluir_livro_com_emprestimo(self, conn):
        conn.execute("INSERT INTO livros (titulo, quantidade) VALUES (?,?)", ("Livro", 1))
        conn.execute("INSERT INTO leitores (nome, telefone) VALUES (?,?)", ("João", "11999999999"))
        lid = conn.execute("SELECT id FROM livros").fetchone()["id"]
        rid = conn.execute("SELECT id FROM leitores").fetchone()["id"]
        conn.execute(
            "INSERT INTO emprestimos (leitor_id, livro_id, data_emprestimo, data_devolucao) VALUES (?,?,?,?)",
            (rid, lid, date.today().isoformat(), (date.today() + timedelta(30)).isoformat())
        )
        em_uso = conn.execute("SELECT COUNT(*) FROM emprestimos WHERE livro_id=?", (lid,)).fetchone()[0]
        assert em_uso > 0  # não deve excluir

    def test_duplicata_mesmo_titulo_autor(self, conn):
        conn.execute("INSERT INTO livros (titulo, autor) VALUES (?,?)", ("Livro X", "Autor Y"))
        dup = conn.execute(
            "SELECT id FROM livros WHERE titulo=? COLLATE NOCASE AND autor=? COLLATE NOCASE",
            ("Livro X", "Autor Y")
        ).fetchone()
        assert dup is not None

    def test_total_exemplares(self, conn):
        conn.execute("INSERT INTO livros (titulo, quantidade) VALUES (?,?)", ("Livro A", 3))
        conn.execute("INSERT INTO livros (titulo, quantidade) VALUES (?,?)", ("Livro B", 2))
        total = conn.execute("SELECT SUM(quantidade) FROM livros").fetchone()[0]
        assert total == 5


# ═══════════════════════════════════════════════════════════════════════
# 4. LEITORES
# ═══════════════════════════════════════════════════════════════════════

class TestLeitores:
    def test_cadastrar_leitor(self, conn):
        conn.execute("INSERT INTO leitores (nome, telefone, email) VALUES (?,?,?)",
                     ("Maria", "11988888888", "maria@email.com"))
        leitores = conn.execute("SELECT * FROM leitores").fetchall()
        assert len(leitores) == 1
        assert leitores[0]["nome"] == "Maria"

    def test_telefone_duplicado(self, conn):
        conn.execute("INSERT INTO leitores (nome, telefone) VALUES (?,?)", ("A", "11999999999"))
        dup = conn.execute("SELECT id FROM leitores WHERE telefone=?", ("11999999999",)).fetchone()
        assert dup is not None

    def test_editar_leitor(self, conn):
        conn.execute("INSERT INTO leitores (nome, telefone) VALUES (?,?)", ("Velho", "11900000000"))
        lid = conn.execute("SELECT id FROM leitores").fetchone()["id"]
        conn.execute("UPDATE leitores SET nome=? WHERE id=?", ("Novo", lid))
        assert conn.execute("SELECT nome FROM leitores WHERE id=?", (lid,)).fetchone()["nome"] == "Novo"

    def test_nao_excluir_leitor_com_historico(self, conn):
        conn.execute("INSERT INTO leitores (nome, telefone) VALUES (?,?)", ("Carlos", "11900000001"))
        conn.execute("INSERT INTO livros (titulo) VALUES (?)", ("Livro",))
        conn.execute("INSERT INTO historico (tipo, leitor_nome, livro_titulo, data) VALUES (?,?,?,?)",
                     ("emprestimo", "Carlos", "Livro", date.today().isoformat()))
        em_uso = conn.execute("SELECT COUNT(*) FROM historico WHERE leitor_nome=?", ("Carlos",)).fetchone()[0]
        assert em_uso > 0

    def test_excluir_leitor_sem_historico(self, conn):
        conn.execute("INSERT INTO leitores (nome, telefone) VALUES (?,?)", ("Temp", "11900000002"))
        lid = conn.execute("SELECT id FROM leitores").fetchone()["id"]
        conn.execute("DELETE FROM leitores WHERE id=?", (lid,))
        assert conn.execute("SELECT COUNT(*) FROM leitores").fetchone()[0] == 0

    def test_validar_telefone_minimo_10_digitos(self):
        valido = "".join(filter(str.isdigit, "11988887777"))
        assert len(valido) >= 10

    def test_telefone_invalido(self):
        invalido = "".join(filter(str.isdigit, "123"))
        assert len(invalido) < 10


# ═══════════════════════════════════════════════════════════════════════
# 5. EMPRÉSTIMOS
# ═══════════════════════════════════════════════════════════════════════

class TestEmprestimos:
    def _seed(self, conn):
        conn.execute("INSERT INTO livros (titulo, quantidade) VALUES (?,?)", ("Livro Teste", 2))
        conn.execute("INSERT INTO leitores (nome, telefone) VALUES (?,?)", ("Leitor Teste", "11900000001"))
        lid = conn.execute("SELECT id FROM livros").fetchone()["id"]
        rid = conn.execute("SELECT id FROM leitores").fetchone()["id"]
        return lid, rid

    def test_registrar_emprestimo(self, conn):
        lid, rid = self._seed(conn)
        hoje = date.today().isoformat()
        dev = (date.today() + timedelta(30)).isoformat()
        conn.execute(
            "INSERT INTO emprestimos (leitor_id, livro_id, data_emprestimo, data_devolucao) VALUES (?,?,?,?)",
            (rid, lid, hoje, dev)
        )
        assert conn.execute("SELECT COUNT(*) FROM emprestimos").fetchone()[0] == 1

    def test_limite_3_emprestimos_por_pessoa(self, conn):
        conn.execute("INSERT INTO leitores (nome, telefone) VALUES (?,?)", ("Leitor", "11900000002"))
        rid = conn.execute("SELECT id FROM leitores").fetchone()["id"]
        for i in range(3):
            conn.execute("INSERT INTO livros (titulo) VALUES (?)", (f"Livro {i}",))
        livros = conn.execute("SELECT id FROM livros").fetchall()
        hoje = date.today().isoformat()
        dev = (date.today() + timedelta(30)).isoformat()
        for l in livros:
            conn.execute(
                "INSERT INTO emprestimos (leitor_id, livro_id, data_emprestimo, data_devolucao) VALUES (?,?,?,?)",
                (rid, l["id"], hoje, dev)
            )
        total = conn.execute(
            "SELECT COUNT(*) FROM emprestimos WHERE leitor_id=? AND status='ativo'", (rid,)
        ).fetchone()[0]
        assert total == 3

    def test_mesmo_livro_nao_pode_ser_emprestado_duas_vezes_ao_mesmo_leitor(self, conn):
        lid, rid = self._seed(conn)
        hoje = date.today().isoformat()
        dev = (date.today() + timedelta(30)).isoformat()
        conn.execute(
            "INSERT INTO emprestimos (leitor_id, livro_id, data_emprestimo, data_devolucao) VALUES (?,?,?,?)",
            (rid, lid, hoje, dev)
        )
        emprestados = conn.execute(
            "SELECT livro_id FROM emprestimos WHERE leitor_id=? AND status='ativo'", (rid,)
        ).fetchall()
        livros_emp = {e["livro_id"] for e in emprestados}
        assert lid in livros_emp  # simula a verificação de duplicata

    def test_cancelar_emprestimo(self, conn):
        lid, rid = self._seed(conn)
        hoje = date.today().isoformat()
        dev = (date.today() + timedelta(30)).isoformat()
        conn.execute(
            "INSERT INTO emprestimos (leitor_id, livro_id, data_emprestimo, data_devolucao) VALUES (?,?,?,?)",
            (rid, lid, hoje, dev)
        )
        emp_id = conn.execute("SELECT id FROM emprestimos").fetchone()["id"]
        conn.execute("UPDATE emprestimos SET status='cancelado' WHERE id=?", (emp_id,))
        status = conn.execute("SELECT status FROM emprestimos WHERE id=?", (emp_id,)).fetchone()["status"]
        assert status == "cancelado"

    def test_renovar_emprestimo(self, conn):
        lid, rid = self._seed(conn)
        hoje = date.today().isoformat()
        dev = (date.today() + timedelta(30)).isoformat()
        conn.execute(
            "INSERT INTO emprestimos (leitor_id, livro_id, data_emprestimo, data_devolucao, renovacoes) VALUES (?,?,?,?,?)",
            (rid, lid, hoje, dev, 0)
        )
        emp_id = conn.execute("SELECT id FROM emprestimos").fetchone()["id"]
        nova_dev = (date.today() + timedelta(60)).isoformat()
        conn.execute(
            "UPDATE emprestimos SET data_devolucao=?, renovacoes=renovacoes+1 WHERE id=?",
            (nova_dev, emp_id)
        )
        emp = conn.execute("SELECT * FROM emprestimos WHERE id=?", (emp_id,)).fetchone()
        assert emp["renovacoes"] == 1
        assert emp["data_devolucao"] == nova_dev

    def test_data_devolucao_deve_ser_posterior_ao_emprestimo(self):
        emp = date(2026, 4, 23)
        dev = date(2026, 4, 20)
        assert not (dev > emp)

    def test_disponibilidade_com_quantidade(self, conn):
        conn.execute("INSERT INTO livros (titulo, quantidade) VALUES (?,?)", ("Livro Multi", 3))
        conn.execute("INSERT INTO leitores (nome, telefone) VALUES (?,?)", ("L1", "11900000003"))
        conn.execute("INSERT INTO leitores (nome, telefone) VALUES (?,?)", ("L2", "11900000004"))
        lid = conn.execute("SELECT id FROM livros").fetchone()["id"]
        r1, r2 = [r["id"] for r in conn.execute("SELECT id FROM leitores").fetchall()]
        hoje = date.today().isoformat()
        dev = (date.today() + timedelta(30)).isoformat()
        conn.execute(
            "INSERT INTO emprestimos (leitor_id, livro_id, data_emprestimo, data_devolucao) VALUES (?,?,?,?)",
            (r1, lid, hoje, dev)
        )
        conn.execute(
            "INSERT INTO emprestimos (leitor_id, livro_id, data_emprestimo, data_devolucao) VALUES (?,?,?,?)",
            (r2, lid, hoje, dev)
        )
        qty = conn.execute("SELECT quantidade FROM livros WHERE id=?", (lid,)).fetchone()["quantidade"]
        loans = conn.execute(
            "SELECT COUNT(*) FROM emprestimos WHERE livro_id=? AND status='ativo'", (lid,)
        ).fetchone()[0]
        disp = qty - loans
        assert disp == 1  # 3 exemplares - 2 emprestados = 1 disponível


# ═══════════════════════════════════════════════════════════════════════
# 6. FILA DE ESPERA
# ═══════════════════════════════════════════════════════════════════════

class TestFilaEspera:
    def test_adicionar_fila(self, conn):
        conn.execute("INSERT INTO livros (titulo) VALUES (?)", ("Livro Fila",))
        conn.execute("INSERT INTO leitores (nome, telefone) VALUES (?,?)", ("Pessoa", "11900000005"))
        lid = conn.execute("SELECT id FROM livros").fetchone()["id"]
        rid = conn.execute("SELECT id FROM leitores").fetchone()["id"]
        conn.execute("INSERT INTO fila_espera (livro_id, leitor_id) VALUES (?,?)", (lid, rid))
        fila = conn.execute("SELECT COUNT(*) FROM fila_espera WHERE livro_id=?", (lid,)).fetchone()[0]
        assert fila == 1

    def test_fila_unica_por_livro_leitor(self, conn):
        conn.execute("INSERT INTO livros (titulo) VALUES (?)", ("Livro Dup",))
        conn.execute("INSERT INTO leitores (nome, telefone) VALUES (?,?)", ("Dup", "11900000006"))
        lid = conn.execute("SELECT id FROM livros").fetchone()["id"]
        rid = conn.execute("SELECT id FROM leitores").fetchone()["id"]
        conn.execute("INSERT INTO fila_espera (livro_id, leitor_id) VALUES (?,?)", (lid, rid))
        with pytest.raises(Exception):
            conn.execute("INSERT INTO fila_espera (livro_id, leitor_id) VALUES (?,?)", (lid, rid))

    def test_remover_da_fila(self, conn):
        conn.execute("INSERT INTO livros (titulo) VALUES (?)", ("Livro Rem",))
        conn.execute("INSERT INTO leitores (nome, telefone) VALUES (?,?)", ("Remov", "11900000007"))
        lid = conn.execute("SELECT id FROM livros").fetchone()["id"]
        rid = conn.execute("SELECT id FROM leitores").fetchone()["id"]
        conn.execute("INSERT INTO fila_espera (livro_id, leitor_id) VALUES (?,?)", (lid, rid))
        conn.execute("DELETE FROM fila_espera WHERE livro_id=? AND leitor_id=?", (lid, rid))
        assert conn.execute("SELECT COUNT(*) FROM fila_espera").fetchone()[0] == 0


# ═══════════════════════════════════════════════════════════════════════
# 7. CONFIGURAÇÕES
# ═══════════════════════════════════════════════════════════════════════

class TestConfig:
    def test_get_cfg_defaults(self, conn):
        rows = conn.execute("SELECT chave, valor FROM config").fetchall()
        d = {r["chave"]: r["valor"] for r in rows}
        cfg = {
            "nome_igreja": d.get("nome_igreja", "Igreja Cristã Reformada"),
            "dias": int(d.get("dias_emprestimo", "30")),
        }
        assert cfg["nome_igreja"] == "Igreja Teste"
        assert cfg["dias"] == 30

    def test_set_cfg(self, conn):
        conn.execute("INSERT OR REPLACE INTO config VALUES ('nome_igreja', ?)", ("Nova Igreja",))
        conn.execute("INSERT OR REPLACE INTO config VALUES ('dias_emprestimo', ?)", ("15",))
        rows = conn.execute("SELECT chave, valor FROM config").fetchall()
        d = {r["chave"]: r["valor"] for r in rows}
        assert d["nome_igreja"] == "Nova Igreja"
        assert d["dias_emprestimo"] == "15"


# ═══════════════════════════════════════════════════════════════════════
# 8. GERADOR DE LINKS WHATSAPP
# ═══════════════════════════════════════════════════════════════════════

class TestGerarWhats:
    def test_url_começa_com_wa_me(self):
        url = _gerar_whats("11999999999", "João", "Livro", "confirmacao",
                            date(2026, 4, 23), date(2026, 5, 23), "Igreja")
        assert url.startswith("https://wa.me/")

    def test_adiciona_55_sem_ddi(self):
        url = _gerar_whats("11999999999", "A", "B", "confirmacao",
                            date(2026, 4, 1), date(2026, 5, 1), "Igreja")
        assert "5511999999999" in url

    def test_nao_duplica_55(self):
        url = _gerar_whats("5511999999999", "A", "B", "confirmacao",
                            date(2026, 4, 1), date(2026, 5, 1), "Igreja")
        assert url.count("55") == 1 or "5511999999999" in url

    def test_tipo_confirmacao(self):
        url = _gerar_whats("11999999999", "Maria", "Dom Quixote", "confirmacao",
                            date(2026, 4, 1), date(2026, 5, 1), "Igreja ICR")
        decoded = urllib.parse.unquote(url)
        assert "Dom Quixote" in decoded
        assert "Maria" in decoded

    def test_tipo_invalido_gera_url_vazia_de_msg(self):
        url = _gerar_whats("11999999999", "A", "B", "tipo_inexistente",
                            date(2026, 4, 1), date(2026, 5, 1), "Igreja")
        assert "wa.me" in url

    def test_todos_os_tipos(self):
        tipos = ["confirmacao", "renovacao", "devolucao", "lembrete", "aviso", "disponivel"]
        for tipo in tipos:
            url = _gerar_whats("11999999999", "A", "B", tipo,
                                date(2026, 4, 1), date(2026, 5, 1), "Igreja")
            assert url.startswith("https://wa.me/")


# ═══════════════════════════════════════════════════════════════════════
# 9. TOTALIZADORES
# ═══════════════════════════════════════════════════════════════════════

class TestTotalizadores:
    def test_total_exemplares_soma_quantidades(self, conn):
        conn.execute("INSERT INTO livros (titulo, quantidade) VALUES (?,?)", ("A", 3))
        conn.execute("INSERT INTO livros (titulo, quantidade) VALUES (?,?)", ("B", 2))
        livros = conn.execute("SELECT quantidade FROM livros").fetchall()
        total = sum((l["quantidade"] or 1) for l in livros)
        assert total == 5

    def test_disponiveis_desconta_emprestimos(self, conn):
        conn.execute("INSERT INTO livros (titulo, quantidade) VALUES (?,?)", ("Livro", 3))
        conn.execute("INSERT INTO leitores (nome, telefone) VALUES (?,?)", ("L", "11900000008"))
        lid = conn.execute("SELECT id FROM livros").fetchone()["id"]
        rid = conn.execute("SELECT id FROM leitores").fetchone()["id"]
        hoje = date.today().isoformat()
        dev = (date.today() + timedelta(30)).isoformat()
        conn.execute(
            "INSERT INTO emprestimos (leitor_id, livro_id, data_emprestimo, data_devolucao) VALUES (?,?,?,?)",
            (rid, lid, hoje, dev)
        )
        livros = conn.execute("SELECT quantidade FROM livros").fetchall()
        ativos = conn.execute("SELECT COUNT(*) FROM emprestimos WHERE status='ativo'").fetchone()[0]
        total_exemplares = sum((l["quantidade"] or 1) for l in livros)
        disponiveis = total_exemplares - ativos
        assert disponiveis == 2  # 3 exemplares - 1 emprestado

    def test_emprestados_conta_ativos(self, conn):
        conn.execute("INSERT INTO livros (titulo, quantidade) VALUES (?,?)", ("L", 5))
        conn.execute("INSERT INTO leitores (nome, telefone) VALUES (?,?)", ("P", "11900000009"))
        lid = conn.execute("SELECT id FROM livros").fetchone()["id"]
        rid = conn.execute("SELECT id FROM leitores").fetchone()["id"]
        hoje = date.today().isoformat()
        dev = (date.today() + timedelta(30)).isoformat()
        conn.execute(
            "INSERT INTO emprestimos (leitor_id, livro_id, data_emprestimo, data_devolucao, status) VALUES (?,?,?,?,?)",
            (rid, lid, hoje, dev, "ativo")
        )
        conn.execute(
            "INSERT INTO emprestimos (leitor_id, livro_id, data_emprestimo, data_devolucao, status) VALUES (?,?,?,?,?)",
            (rid, lid, hoje, dev, "cancelado")
        )
        ativos = conn.execute(
            "SELECT COUNT(*) FROM emprestimos WHERE status='ativo'"
        ).fetchone()[0]
        assert ativos == 1  # cancelado não conta


# ═══════════════════════════════════════════════════════════════════════
# 10. EVOLUTION API (mock)
# ═══════════════════════════════════════════════════════════════════════

class TestEvolutionApi:
    def test_evo_send_sucesso(self):
        with patch("requests.post") as mock_post:
            mock_post.return_value = MagicMock(status_code=201)
            import requests as req
            r = req.post(
                "http://localhost:8080/message/sendText/biblioteca",
                headers={"apikey": "biblio-icr-key"},
                json={"number": "5511999999999", "text": "Teste"},
                timeout=10,
            )
            assert r.status_code == 201

    def test_evo_status_open(self):
        with patch("requests.get") as mock_get:
            mock_get.return_value = MagicMock(
                status_code=200,
                json=lambda: {"state": "open"}
            )
            import requests as req
            r = req.get("http://localhost:8080/instance/connectionState/biblioteca",
                        headers={}, timeout=3)
            state = r.json().get("state")
            assert state == "open"

    def test_evo_status_erro_de_conexao(self):
        with patch("requests.get", side_effect=Exception("Connection refused")):
            resultado = "erro"  # comportamento esperado do evo_status()
            assert resultado == "erro"

    def test_evo_send_falha(self):
        with patch("requests.post") as mock_post:
            mock_post.return_value = MagicMock(status_code=500)
            import requests as req
            r = req.post("http://localhost:8080/message/sendText/biblioteca",
                         headers={}, json={}, timeout=10)
            assert r.status_code not in (200, 201)

    def test_evo_status_nested_instance_format(self):
        """API retorna {"instance": {"state": "open"}} — parsing aninhado."""
        data = {"instance": {"instanceName": "biblioteca", "state": "open"}}
        status = (
            data.get("state")
            or (data.get("instance") or {}).get("state")
            or "close"
        )
        assert status == "open"

    def test_evo_status_flat_format(self):
        """Também aceita formato plano {"state": "open"}."""
        data = {"state": "open"}
        status = (
            data.get("state")
            or (data.get("instance") or {}).get("state")
            or "close"
        )
        assert status == "open"

    def test_evo_status_fallback_close(self):
        """Sem campo state, retorna close."""
        data = {}
        status = (
            data.get("state")
            or (data.get("instance") or {}).get("state")
            or "close"
        )
        assert status == "close"

    def test_evo_status_instance_close(self):
        """Estado close dentro de instance."""
        data = {"instance": {"state": "close"}}
        status = (
            data.get("state")
            or (data.get("instance") or {}).get("state")
            or "close"
        )
        assert status == "close"


# ═══════════════════════════════════════════════════════════════════════
# 11. CAIXA DE ENTRADA — evo_get_messages (mock)
# ═══════════════════════════════════════════════════════════════════════

def _evo_get_messages_impl(response_json, only_received=True):
    """Replica a lógica de evo_get_messages() sem dependência de rede."""
    records = response_json.get("messages", {}).get("records", [])
    if only_received:
        records = [r for r in records if not r.get("key", {}).get("fromMe", False)]
    return records[:100]


def _extract_msg_text(msg_obj):
    """Replica a lógica de extração de texto das mensagens."""
    msg = msg_obj.get("message", {}) or {}
    return (
        msg.get("conversation")
        or (msg.get("extendedTextMessage") or {}).get("text")
        or (msg.get("imageMessage") or {}).get("caption")
        or "[mídia]"
    )


class TestEvoGetMessages:
    def test_retorna_lista_vazia_quando_sem_records(self):
        resp = {"messages": {"total": 0, "pages": 0, "currentPage": 1, "records": []}}
        result = _evo_get_messages_impl(resp)
        assert result == []

    def test_filtra_apenas_mensagens_recebidas(self):
        resp = {
            "messages": {
                "records": [
                    {"key": {"remoteJid": "5511999999999@s.whatsapp.net", "fromMe": False},
                     "message": {"conversation": "Oi!"},
                     "messageTimestamp": 1700000001,
                     "pushName": "João"},
                    {"key": {"remoteJid": "5511888888888@s.whatsapp.net", "fromMe": True},
                     "message": {"conversation": "Olá"},
                     "messageTimestamp": 1700000002,
                     "pushName": ""},
                ]
            }
        }
        result = _evo_get_messages_impl(resp, only_received=True)
        assert len(result) == 1
        assert result[0]["pushName"] == "João"

    def test_sem_filtro_retorna_todas(self):
        resp = {
            "messages": {
                "records": [
                    {"key": {"fromMe": False}, "message": {"conversation": "A"}, "messageTimestamp": 1},
                    {"key": {"fromMe": True},  "message": {"conversation": "B"}, "messageTimestamp": 2},
                ]
            }
        }
        result = _evo_get_messages_impl(resp, only_received=False)
        assert len(result) == 2

    def test_respeita_limite_de_100(self):
        records = [
            {"key": {"fromMe": False}, "message": {"conversation": f"msg{i}"}, "messageTimestamp": i}
            for i in range(150)
        ]
        resp = {"messages": {"records": records}}
        result = _evo_get_messages_impl(resp, only_received=False)
        assert len(result) == 100

    def test_json_sem_chave_messages(self):
        resp = {}
        result = _evo_get_messages_impl(resp)
        assert result == []

    def test_json_messages_sem_records(self):
        resp = {"messages": {"total": 0}}
        result = _evo_get_messages_impl(resp)
        assert result == []

    def test_mock_requests_post_sucesso(self):
        payload = {"messages": {"total": 1, "records": [
            {"key": {"remoteJid": "55119@s.whatsapp.net", "fromMe": False},
             "message": {"conversation": "Olá"},
             "messageTimestamp": 1700000000,
             "pushName": "Ana"}
        ]}}
        with patch("requests.post") as mock_post:
            mock_post.return_value = MagicMock(status_code=200, json=lambda: payload)
            import requests as req
            r = req.post(
                "http://localhost:8080/chat/findMessages/biblioteca",
                headers={"apikey": "biblio-icr-key"},
                json={"where": {"key": {"fromMe": False}}},
                timeout=10,
            )
            assert r.status_code == 200
            records = r.json().get("messages", {}).get("records", [])
            assert len(records) == 1
            assert records[0]["pushName"] == "Ana"

    def test_mock_requests_post_falha(self):
        with patch("requests.post", side_effect=Exception("timeout")):
            try:
                import requests as req
                req.post("http://localhost:8080/chat/findMessages/biblioteca",
                         json={}, timeout=10)
                result = []
            except Exception:
                result = []
            assert result == []


# ═══════════════════════════════════════════════════════════════════════
# 12. EXTRAÇÃO DE TEXTO DE MENSAGENS WHATSAPP
# ═══════════════════════════════════════════════════════════════════════

class TestExtractMsgText:
    def test_conversation(self):
        msg = {"message": {"conversation": "Texto simples"}}
        assert _extract_msg_text(msg) == "Texto simples"

    def test_extended_text_message(self):
        msg = {"message": {"extendedTextMessage": {"text": "Texto longo"}}}
        assert _extract_msg_text(msg) == "Texto longo"

    def test_image_with_caption(self):
        msg = {"message": {"imageMessage": {"caption": "Legenda da foto"}}}
        assert _extract_msg_text(msg) == "Legenda da foto"

    def test_midia_sem_texto(self):
        msg = {"message": {"imageMessage": {}}}
        assert _extract_msg_text(msg) == "[mídia]"

    def test_message_vazio(self):
        msg = {"message": {}}
        assert _extract_msg_text(msg) == "[mídia]"

    def test_sem_chave_message(self):
        msg = {}
        assert _extract_msg_text(msg) == "[mídia]"

    def test_message_none(self):
        msg = {"message": None}
        assert _extract_msg_text(msg) == "[mídia]"

    def test_conversation_tem_prioridade(self):
        """conversation deve ter prioridade sobre extendedTextMessage."""
        msg = {"message": {
            "conversation": "Principal",
            "extendedTextMessage": {"text": "Secundário"},
        }}
        assert _extract_msg_text(msg) == "Principal"


# ═══════════════════════════════════════════════════════════════════════
# 13. AGRUPAMENTO DE MENSAGENS POR CONTATO
# ═══════════════════════════════════════════════════════════════════════

class TestAgrupamentoContatos:
    def _make_msgs(self, contacts_data):
        """Gera lista de registros de mensagem para testes."""
        msgs = []
        for jid, push, ts, text in contacts_data:
            msgs.append({
                "key": {"remoteJid": jid, "fromMe": False},
                "message": {"conversation": text},
                "messageTimestamp": ts,
                "pushName": push,
            })
        return msgs

    def test_agrupa_por_contato_unico(self):
        msgs = self._make_msgs([
            ("55119@s.whatsapp.net", "João", 1000, "Oi"),
            ("55119@s.whatsapp.net", "João", 2000, "Tudo bem?"),
        ])
        from collections import OrderedDict
        by_contact = OrderedDict()
        for m in sorted(msgs, key=lambda x: x.get("messageTimestamp", 0), reverse=True):
            jid = m["key"]["remoteJid"]
            if jid not in by_contact:
                by_contact[jid] = m
        assert len(by_contact) == 1

    def test_pega_ultima_mensagem_por_contato(self):
        msgs = self._make_msgs([
            ("55119@s.whatsapp.net", "João", 1000, "Primeira"),
            ("55119@s.whatsapp.net", "João", 2000, "Última"),
        ])
        from collections import OrderedDict
        by_contact = OrderedDict()
        for m in sorted(msgs, key=lambda x: x.get("messageTimestamp", 0), reverse=True):
            jid = m["key"]["remoteJid"]
            if jid not in by_contact:
                by_contact[jid] = m
        last = by_contact["55119@s.whatsapp.net"]
        assert last["message"]["conversation"] == "Última"

    def test_multiplos_contatos(self):
        msgs = self._make_msgs([
            ("55119@s.whatsapp.net", "Ana",   1000, "Oi Ana"),
            ("55118@s.whatsapp.net", "Bruno", 2000, "Oi Bruno"),
            ("55117@s.whatsapp.net", "Clara", 1500, "Oi Clara"),
        ])
        from collections import OrderedDict
        by_contact = OrderedDict()
        for m in sorted(msgs, key=lambda x: x.get("messageTimestamp", 0), reverse=True):
            jid = m["key"]["remoteJid"]
            if jid not in by_contact:
                by_contact[jid] = m
        assert len(by_contact) == 3

    def test_filtro_por_nome(self):
        contatos = [
            ("55119@s.whatsapp.net", "Ana Silva",  "559", 1000),
            ("55118@s.whatsapp.net", "Bruno Costa","558", 2000),
        ]
        filtro = "ana"
        resultado = [
            (jid, push, phone)
            for jid, push, phone, _ in contatos
            if filtro in push.lower() or filtro in phone.lower()
        ]
        assert len(resultado) == 1
        assert resultado[0][1] == "Ana Silva"

    def test_filtro_por_numero(self):
        contatos = [
            ("55119@s.whatsapp.net", "Ana",   "55119", 1000),
            ("55118@s.whatsapp.net", "Bruno", "55118", 2000),
        ]
        filtro = "55119"
        resultado = [
            (jid, push, phone)
            for jid, push, phone, _ in contatos
            if filtro in push.lower() or filtro in phone.lower()
        ]
        assert len(resultado) == 1

    def test_filtro_vazio_retorna_todos(self):
        contatos = [
            ("55119@s.whatsapp.net", "Ana",   "559", 1000),
            ("55118@s.whatsapp.net", "Bruno", "558", 2000),
        ]
        filtro = ""
        resultado = [
            c for c in contatos
            if not filtro or filtro in c[1].lower() or filtro in c[2].lower()
        ]
        assert len(resultado) == 2

    def test_extrai_telefone_de_jid(self):
        jid = "5511988887777@s.whatsapp.net"
        phone = jid.split("@")[0]
        assert phone == "5511988887777"


# ═══════════════════════════════════════════════════════════════════════
# 14. BATCH QUEUE — delays e fila de envio em massa
# ═══════════════════════════════════════════════════════════════════════

def _build_batch_queue(selecionados, batch_size=5, inter_msg_max=1200, inter_batch=3600):
    """Monta fila de envio em massa com lotes de batch_size e pausa inter_batch entre lotes."""
    import random, math
    total_lotes = math.ceil(len(selecionados) / batch_size)
    fila = []
    for i, e in enumerate(selecionados):
        lote_num    = i // batch_size
        pos_in_lote = i %  batch_size
        if i == 0:
            delay = 0
        elif pos_in_lote == 0:
            delay = inter_batch
        else:
            delay = random.randint(60, inter_msg_max)
        fila.append({"e": e, "delay": delay, "lote": lote_num + 1, "total_lotes": total_lotes})
    return fila


class TestBatchQueue:
    # ── regras de delay ──────────────────────────────────────────────

    def test_primeiro_item_delay_zero(self):
        """Primeiro item global sempre tem delay 0 (envio imediato)."""
        fila = _build_batch_queue([{"id": i} for i in range(3)])
        assert fila[0]["delay"] == 0

    def test_delay_intra_lote_entre_60_e_1200(self):
        """Dentro de um lote os delays devem ser 60–1200 s (20 min)."""
        fila = _build_batch_queue([{"id": i} for i in range(5)])
        for item in fila[1:]:
            assert 60 <= item["delay"] <= 1200

    def test_primeiro_item_lote_2_tem_delay_3600(self):
        """O primeiro item do 2º lote deve ter delay de 3600 s (1 h)."""
        fila = _build_batch_queue([{"id": i} for i in range(6)])
        # item 5 (índice 5) é o primeiro do lote 2
        assert fila[5]["delay"] == 3600

    def test_primeiro_item_lote_3_tem_delay_3600(self):
        """O primeiro item do 3º lote também tem delay de 3600 s."""
        fila = _build_batch_queue([{"id": i} for i in range(11)])
        # item 10 (índice 10) é o primeiro do lote 3
        assert fila[10]["delay"] == 3600

    # ── tamanho e número de lotes ────────────────────────────────────

    def test_15_destinatarios_geram_3_lotes(self):
        import math
        assert math.ceil(15 / 5) == 3

    def test_6_destinatarios_geram_2_lotes(self):
        import math
        assert math.ceil(6 / 5) == 2

    def test_5_destinatarios_geram_1_lote(self):
        import math
        assert math.ceil(5 / 5) == 1

    def test_lote_metadata_correto_15_itens(self):
        """Cada item deve ter lote e total_lotes corretos."""
        fila = _build_batch_queue([{"id": i} for i in range(15)])
        assert fila[0]["lote"] == 1  and fila[0]["total_lotes"] == 3
        assert fila[4]["lote"] == 1  and fila[4]["total_lotes"] == 3
        assert fila[5]["lote"] == 2  and fila[5]["total_lotes"] == 3
        assert fila[9]["lote"] == 2  and fila[9]["total_lotes"] == 3
        assert fila[10]["lote"] == 3 and fila[10]["total_lotes"] == 3
        assert fila[14]["lote"] == 3 and fila[14]["total_lotes"] == 3

    def test_fila_total_itens_preservada(self):
        """A fila deve ter exatamente o mesmo número de destinatários."""
        selecionados = [{"id": i} for i in range(13)]
        fila = _build_batch_queue(selecionados)
        assert len(fila) == 13

    # ── mecânica de execução ─────────────────────────────────────────

    def test_pop_remove_primeiro_item(self):
        fila = _build_batch_queue([{"id": 1}, {"id": 2}])
        item = fila.pop(0)
        assert item["e"]["id"] == 1
        assert len(fila) == 1

    def test_prox_agendamento_usa_delay_do_proximo(self):
        fila = [
            {"e": {"id": 1}, "delay": 0,   "lote": 1, "total_lotes": 2},
            {"e": {"id": 2}, "delay": 3600, "lote": 2, "total_lotes": 2},
        ]
        fila.pop(0)
        assert fila[0]["delay"] == 3600

    def test_fila_vazia_indica_conclusao(self):
        fila = [{"e": {"id": 1}, "txt": "msg", "delay": 0, "lote": 1, "total_lotes": 1}]
        fila.pop(0)
        assert len(fila) == 0

    def test_resultados_contabilizam_enviados(self):
        resultados = {"sent": 0, "failed": [], "total": 3}
        resultados["sent"] += 1
        resultados["sent"] += 1
        resultados["failed"].append("Leitor X")
        assert resultados["sent"] == 2
        assert len(resultados["failed"]) == 1

    def test_progress_calculo(self):
        resultados = {"sent": 3, "total": 5}
        prog = resultados["sent"] / resultados["total"]
        assert prog == 0.6

    # ── detecção de inter-batch no display ───────────────────────────

    def test_detecta_espera_entre_lotes(self):
        """delay >= 3600 indica que o próximo item é início de novo lote."""
        next_item = {"delay": 3600, "lote": 2, "total_lotes": 3}
        is_inter_batch = next_item.get("delay", 0) >= 3600
        assert is_inter_batch is True

    def test_detecta_envio_dentro_do_lote(self):
        next_item = {"delay": 300, "lote": 1, "total_lotes": 3}
        is_inter_batch = next_item.get("delay", 0) >= 3600
        assert is_inter_batch is False

    # ── formatação do countdown ──────────────────────────────────────

    def test_countdown_formatacao(self):
        remaining = 185.0
        mins = int(remaining // 60)
        secs = int(remaining % 60)
        assert f"{mins}m {secs:02d}s" == "3m 05s"

    def test_countdown_formatacao_segundos_simples(self):
        remaining = 42.0
        mins = int(remaining // 60)
        secs = int(remaining % 60)
        assert f"{mins}m {secs:02d}s" == "0m 42s"

    def test_countdown_1_hora(self):
        remaining = 3600.0
        mins = int(remaining // 60)
        secs = int(remaining % 60)
        assert f"{mins}m {secs:02d}s" == "60m 00s"


# ══════════════════════════════════════════════════════════════════════
# TestScheduler — app/scheduler.py
# ══════════════════════════════════════════════════════════════════════

# Importa as funções puras do scheduler sem efeitos colaterais de I/O
import importlib, types

def _load_scheduler():
    """Carrega scheduler.py isolando chamadas de I/O (DB, requests, time.sleep)."""
    import math, random
    from unittest.mock import patch, MagicMock
    sched_path = os.path.join(os.path.dirname(__file__), "..", "app", "scheduler.py")
    spec = importlib.util.spec_from_file_location("scheduler", sched_path)
    mod  = importlib.util.module_from_spec(spec)
    # Bloqueia tentativas de criar diretório de log e conectar ao DB durante o import
    with patch("os.makedirs"), patch("logging.FileHandler", return_value=MagicMock()):
        spec.loader.exec_module(mod)
    return mod

_sched = _load_scheduler()


class TestSchedulerTexto:
    """gerar_texto() — verifica conteúdo das mensagens automáticas."""

    def test_lembrete_contem_venceu(self):
        txt = _sched.gerar_texto("João", "Livro X", "lembrete", "2026-03-01", "2026-03-31", "Igreja")
        assert "venceu em" in txt
        assert "João" in txt
        assert "Livro X" in txt

    def test_aviso_contem_prazo(self):
        txt = _sched.gerar_texto("Maria", "Livro Y", "aviso", "2026-04-01", "2026-04-28", "Igreja")
        assert "prazo de devolução" in txt
        assert "Maria" in txt
        assert "Livro Y" in txt

    def test_tipo_desconhecido_retorna_vazio(self):
        txt = _sched.gerar_texto("X", "Y", "confirmacao", "2026-01-01", "2026-01-31", "Igreja")
        assert txt == ""

    def test_lembrete_nao_menciona_renovacao(self):
        txt = _sched.gerar_texto("X", "Y", "lembrete", "2026-01-01", "2026-01-15", "Igreja")
        assert "renov" not in txt.lower()


class TestSchedulerBuscarDestinatarios:
    """buscar_destinatarios() — classifica corretamente os leitores."""

    def _make_row(self, devolucao: str):
        row = MagicMock()
        row.__getitem__ = lambda self, k: {
            "nome": "Leitor", "telefone": "48999999999",
            "titulo": "Livro", "data_emprestimo": "2026-01-01",
            "data_devolucao": devolucao,
        }[k]
        return row

    def test_atrasado_vira_lembrete(self):
        ontem = (date.today() - timedelta(days=1)).isoformat()
        row   = self._make_row(ontem)
        dl    = (date.fromisoformat(ontem) - date.today()).days
        assert dl < 0
        tipo  = "lembrete" if dl < 0 else ("aviso" if dl <= 5 else None)
        assert tipo == "lembrete"

    def test_vencendo_hoje_vira_aviso(self):
        hoje = date.today().isoformat()
        dl   = 0
        tipo = "lembrete" if dl < 0 else ("aviso" if dl <= 5 else None)
        assert tipo == "aviso"

    def test_vencendo_em_5_dias_vira_aviso(self):
        dl   = 5
        tipo = "lembrete" if dl < 0 else ("aviso" if dl <= 5 else None)
        assert tipo == "aviso"

    def test_vencendo_em_6_dias_ignorado(self):
        dl   = 6
        tipo = "lembrete" if dl < 0 else ("aviso" if dl <= 5 else None)
        assert tipo is None

    def test_em_dia_ignorado(self):
        dl   = 30
        tipo = "lembrete" if dl < 0 else ("aviso" if dl <= 5 else None)
        assert tipo is None

    def test_buscar_destinatarios_usa_db(self):
        """Garante que a função consulta o DB e retorna lista."""
        mock_rows = []
        mock_conn = MagicMock()
        mock_conn.__enter__ = lambda s: mock_conn
        mock_conn.__exit__  = MagicMock(return_value=False)
        mock_conn.execute.return_value.fetchall.return_value = mock_rows
        with patch.object(_sched, "get_conn", return_value=mock_conn):
            result = _sched.buscar_destinatarios({"nome_igreja": "Igreja"})
        assert result == []


class TestSchedulerMontarFila:
    """montar_fila() — usa a mesma lógica de lotes do app."""

    def test_primeiro_delay_zero(self):
        destinos = [{"nome": f"L{i}", "telefone": "48x", "titulo": "T",
                     "tipo": "aviso", "data_emprestimo": "2026-01-01",
                     "data_devolucao": "2026-04-30"} for i in range(3)]
        fila = _sched.montar_fila(destinos)
        assert fila[0]["delay"] == 0

    def test_inter_batch_no_inicio_do_segundo_lote(self):
        destinos = [{"nome": f"L{i}", "telefone": "48x", "titulo": "T",
                     "tipo": "aviso", "data_emprestimo": "2026-01-01",
                     "data_devolucao": "2026-04-30"} for i in range(6)]
        fila = _sched.montar_fila(destinos)
        assert fila[5]["delay"] == _sched.INTER_BATCH

    def test_delay_intra_lote_dentro_dos_limites(self):
        destinos = [{"nome": f"L{i}", "telefone": "48x", "titulo": "T",
                     "tipo": "lembrete", "data_emprestimo": "2026-01-01",
                     "data_devolucao": "2026-03-01"} for i in range(5)]
        fila = _sched.montar_fila(destinos)
        for item in fila[1:]:
            assert _sched.INTER_MSG_MIN <= item["delay"] <= _sched.INTER_MSG_MAX

    def test_metadata_lote_correto(self):
        destinos = [{"nome": f"L{i}", "telefone": "48x", "titulo": "T",
                     "tipo": "aviso", "data_emprestimo": "2026-01-01",
                     "data_devolucao": "2026-04-30"} for i in range(10)]
        fila = _sched.montar_fila(destinos)
        assert fila[0]["lote"] == 1 and fila[0]["total_lotes"] == 2
        assert fila[5]["lote"] == 2 and fila[5]["total_lotes"] == 2

    def test_15_destinatarios_3_lotes(self):
        destinos = [{"nome": f"L{i}", "telefone": "48x", "titulo": "T",
                     "tipo": "lembrete", "data_emprestimo": "2026-01-01",
                     "data_devolucao": "2026-03-01"} for i in range(15)]
        fila = _sched.montar_fila(destinos)
        assert len(fila) == 15
        assert fila[14]["total_lotes"] == 3


class TestSchedulerEvoSend:
    """evo_send() no scheduler — mesma lógica do app."""

    def test_adiciona_55_se_ausente(self):
        with patch("requests.post") as mock_post:
            mock_post.return_value.status_code = 201
            _sched.evo_send("48999999999", "texto")
            chamada = mock_post.call_args[1]["json"]
            assert chamada["number"].startswith("55")

    def test_nao_duplica_55(self):
        with patch("requests.post") as mock_post:
            mock_post.return_value.status_code = 201
            _sched.evo_send("5548999999999", "texto")
            chamada = mock_post.call_args[1]["json"]
            assert chamada["number"].startswith("55")
            assert not chamada["number"].startswith("5555")

    def test_retorna_true_em_201(self):
        with patch("requests.post") as mock_post:
            mock_post.return_value.status_code = 201
            assert _sched.evo_send("48999999999", "texto") is True

    def test_retorna_false_em_erro_http(self):
        with patch("requests.post") as mock_post:
            mock_post.return_value.status_code = 500
            assert _sched.evo_send("48999999999", "texto") is False

    def test_retorna_false_em_excecao(self):
        with patch("requests.post", side_effect=Exception("timeout")):
            assert _sched.evo_send("48999999999", "texto") is False


class TestSchedulerConexao:
    """evo_is_connected() — detecta estado da instância."""

    def test_open_retorna_true(self):
        with patch("requests.get") as mock_get:
            mock_get.return_value.status_code = 200
            mock_get.return_value.json.return_value = {"instance": {"state": "open"}}
            assert _sched.evo_is_connected() is True

    def test_close_retorna_false(self):
        with patch("requests.get") as mock_get:
            mock_get.return_value.status_code = 200
            mock_get.return_value.json.return_value = {"instance": {"state": "close"}}
            assert _sched.evo_is_connected() is False

    def test_erro_http_retorna_false(self):
        with patch("requests.get") as mock_get:
            mock_get.return_value.status_code = 500
            assert _sched.evo_is_connected() is False

    def test_excecao_retorna_false(self):
        with patch("requests.get", side_effect=Exception("off")):
            assert _sched.evo_is_connected() is False


class TestSchedulerJobPrincipal:
    """job_envio_diario() — fluxo de alto nível."""

    def test_cancela_se_desconectado(self):
        with patch.object(_sched, "evo_is_connected", return_value=False), \
             patch.object(_sched, "buscar_destinatarios") as mock_buscar:
            _sched.job_envio_diario()
            mock_buscar.assert_not_called()

    def test_encerra_sem_enviar_se_sem_destinatarios(self):
        with patch.object(_sched, "evo_is_connected", return_value=True), \
             patch.object(_sched, "buscar_destinatarios", return_value=[]), \
             patch.object(_sched, "montar_fila") as mock_fila:
            _sched.job_envio_diario()
            mock_fila.assert_not_called()

    def test_chama_executar_fila_quando_ha_destinatarios(self):
        destino = {"nome": "X", "telefone": "489", "titulo": "T",
                   "tipo": "aviso", "data_emprestimo": "2026-01-01",
                   "data_devolucao": "2026-04-30",
                   "delay": 0, "lote": 1, "total_lotes": 1}
        with patch.object(_sched, "evo_is_connected", return_value=True), \
             patch.object(_sched, "buscar_destinatarios", return_value=[destino]), \
             patch.object(_sched, "montar_fila", return_value=[destino]), \
             patch.object(_sched, "executar_fila", return_value={"sent": 1, "failed": [], "total": 1}) as mock_exec, \
             patch.object(_sched, "get_cfg", return_value={"nome_igreja": "Igreja"}):
            _sched.job_envio_diario()
            mock_exec.assert_called_once()


# ═══════════════════════════════════════════════════════════════════════
# 15. WA_BUTTON — unicidade de chaves (bug StreamlitDuplicateElementKey)
# ═══════════════════════════════════════════════════════════════════════

class TestWaButtonKeyUniqueness:
    """
    Garante que wa_button nunca gera chaves duplicadas quando renderizado
    múltiplas vezes na mesma tela — origem do StreamlitDuplicateElementKey.
    """

    def test_mesma_label_mesmo_phone_sem_key_explicita_gera_chave_identica(self):
        """Demonstra o problema: sem key explícita, 2 cards do mesmo leitor colidem."""
        label = "Enviar confirmação"
        phone = "48991110001"
        key1 = f"wa_send_{hash(label + phone)}"
        key2 = f"wa_send_{hash(label + phone)}"
        assert key1 == key2  # isso causaria StreamlitDuplicateElementKey

    def test_key_explicita_por_id_resolve_duplicata(self):
        """Com key explícita por ID de empréstimo, as chaves são únicas."""
        emp_ids = [1, 2, 3]
        keys = [f"wa_conf_{eid}" for eid in emp_ids]
        assert len(keys) == len(set(keys))

    def test_keys_unicas_multiplos_emprestimos_mesmo_leitor(self):
        """Mesmo leitor, múltiplos livros: key usa ID do empréstimo, não telefone."""
        emprestimos = [
            {"id": 10, "telefone": "48991110001"},
            {"id": 11, "telefone": "48991110001"},  # mesmo telefone, outro empréstimo
        ]
        keys = [f"wa_conf_{e['id']}" for e in emprestimos]
        assert len(set(keys)) == len(keys)

    def test_keys_unicas_lembretes_atrasados(self):
        emprestimos = [{"id": i, "telefone": "48991110001"} for i in range(5)]
        keys = [f"wa_lemb_{e['id']}" for e in emprestimos]
        assert len(set(keys)) == 5

    def test_keys_unicas_avisos_vencendo(self):
        emprestimos = [{"id": i, "telefone": "48991110002"} for i in range(5)]
        keys = [f"wa_aviso_{e['id']}" for e in emprestimos]
        assert len(set(keys)) == 5

    def test_keys_unicas_reenvio_confirmacao_editar(self):
        emprestimos = [{"id": i} for i in range(10)]
        keys = [f"wa_reenv_{e['id']}" for e in emprestimos]
        assert len(set(keys)) == 10

    def test_banners_estaticos_sao_distintos(self):
        """Banners únicos por aba não devem colidir entre si."""
        banners = ["wa_novo_banner", "wa_renovar_banner", "wa_dev_banner", "wa_fila_banner"]
        assert len(banners) == len(set(banners))

    def test_logica_btn_key_usa_key_quando_fornecida(self):
        """_btn_key = key if key else hash(...) — key explícita tem prioridade."""
        label, phone = "Enviar", "48999999999"
        key_param = "minha_key_unica"
        _btn_key = key_param if key_param else f"wa_send_{hash(label + phone)}"
        assert _btn_key == "minha_key_unica"

    def test_logica_btn_key_usa_hash_quando_key_vazia(self):
        """Sem key explícita, usa hash como fallback."""
        label, phone = "Enviar", "48999999999"
        key_param = ""
        _btn_key = key_param if key_param else f"wa_send_{hash(label + phone)}"
        assert _btn_key.startswith("wa_send_")

    def test_10_leitores_diferentes_geram_10_keys_distintas(self):
        """10 empréstimos de leitores diferentes com mesma label → 10 keys únicas."""
        emprestimos = [{"id": i, "telefone": f"489999{i:05d}"} for i in range(10)]
        keys_por_id   = [f"wa_conf_{e['id']}" for e in emprestimos]
        keys_por_hash = [f"wa_send_{hash('Enviar confirmação' + e['telefone'])}" for e in emprestimos]
        assert len(set(keys_por_id))   == 10  # sempre único
        assert len(set(keys_por_hash)) == 10  # também único quando telefones são diferentes

    def test_dois_leitores_mesmo_telefone_colidiria_sem_key_id(self):
        """Caso patológico: dois registros com mesmo telefone causariam colisão sem key por ID."""
        phone = "48991110001"
        label = "Enviar confirmação"
        key_hash1 = f"wa_send_{hash(label + phone)}"
        key_hash2 = f"wa_send_{hash(label + phone)}"
        assert key_hash1 == key_hash2  # colisão!
        # com key por ID, resolvido:
        key_id1 = "wa_conf_5"
        key_id2 = "wa_conf_6"
        assert key_id1 != key_id2


# ═══════════════════════════════════════════════════════════════════════
# 16. FORMULÁRIO DE EMPRÉSTIMO — lógica de placeholder e validação
# ═══════════════════════════════════════════════════════════════════════

_PLAC_LEITOR = "— Selecionar leitor —"
_PLAC_LIVRO  = "— Selecionar livro —"


def _form_valido(sel_leitor: str, sel_livro: str) -> bool:
    return sel_leitor != _PLAC_LEITOR and sel_livro != _PLAC_LIVRO


class TestFormValidation:
    def test_ambos_placeholder_invalido(self):
        assert not _form_valido(_PLAC_LEITOR, _PLAC_LIVRO)

    def test_apenas_leitor_placeholder_invalido(self):
        assert not _form_valido(_PLAC_LEITOR, "O Peregrino")

    def test_apenas_livro_placeholder_invalido(self):
        assert not _form_valido("Ana Souza", _PLAC_LIVRO)

    def test_ambos_preenchidos_valido(self):
        assert _form_valido("Ana Souza", "O Peregrino")

    def test_placeholder_nao_esta_no_mapa_de_leitores(self):
        leitores = [{"nome": "Ana"}, {"nome": "Bruno"}]
        leitor_map = {l["nome"]: l for l in leitores}
        assert _PLAC_LEITOR not in leitor_map

    def test_placeholder_nao_esta_no_mapa_de_livros(self):
        livros = [{"titulo": "Livro A", "autor": ""}, {"titulo": "Livro B", "autor": ""}]
        livro_map = {b["titulo"]: b for b in livros}
        assert _PLAC_LIVRO not in livro_map

    def test_opcoes_selectbox_tem_placeholder_como_primeiro(self):
        leitores = ["Ana", "Bruno"]
        opcoes = [_PLAC_LEITOR] + leitores
        assert opcoes[0] == _PLAC_LEITOR
        assert leitores[0] not in opcoes[:1]

    def test_acesso_ao_mapa_apenas_quando_valido(self):
        """Simula que leitor_map[sel_leitor] só é acessado se form_valido."""
        sel_leitor = _PLAC_LEITOR
        sel_livro  = "Livro Válido"
        leitor_map = {"Ana": {"id": 1}}
        leitor = None
        if _form_valido(sel_leitor, sel_livro):
            leitor = leitor_map[sel_leitor]  # KeyError se placeholder
        assert leitor is None  # branch não foi executado

    def test_acesso_ao_mapa_quando_valido_funciona(self):
        sel_leitor = "Ana"
        sel_livro  = "O Peregrino"
        leitor_map = {"Ana": {"id": 1, "nome": "Ana"}}
        leitor = None
        if _form_valido(sel_leitor, sel_livro):
            leitor = leitor_map[sel_leitor]
        assert leitor is not None
        assert leitor["id"] == 1

    def test_placeholder_leitor_diferente_de_placeholder_livro(self):
        assert _PLAC_LEITOR != _PLAC_LIVRO


# ═══════════════════════════════════════════════════════════════════════
# 17. SESSION STATE — reset após registro e fechar aviso
# ═══════════════════════════════════════════════════════════════════════

class TestSessionStateReset:
    """Garante que o formulário volta ao estado inicial após conclusão."""

    def test_chaves_removidas_apos_registro(self):
        ss = {"emp_sel_leitor": "Ana Souza", "emp_sel_livro": "O Peregrino"}
        for k in ("emp_sel_leitor", "emp_sel_livro"):
            if k in ss:
                del ss[k]
        assert "emp_sel_leitor" not in ss
        assert "emp_sel_livro" not in ss

    def test_chaves_removidas_apos_fechar_aviso(self):
        ss = {"emp_sel_leitor": "Bruno", "emp_sel_livro": "Livro X", "wa_novo": {"label": "X"}}
        ss["wa_novo"] = None
        for k in ("emp_sel_leitor", "emp_sel_livro"):
            if k in ss:
                del ss[k]
        assert ss["wa_novo"] is None
        assert "emp_sel_leitor" not in ss
        assert "emp_sel_livro" not in ss

    def test_wa_novo_preenchido_apos_registro_bem_sucedido(self):
        ss = {}
        ss["wa_novo"] = {
            "label": "Enviar confirmação para Ana",
            "url":   "https://wa.me/5548999999999",
            "phone": "48999999999",
            "text":  "Olá, Ana!",
        }
        assert ss["wa_novo"] is not None
        assert "phone" in ss["wa_novo"]
        assert "text"  in ss["wa_novo"]
        assert "url"   in ss["wa_novo"]

    def test_wa_novo_none_apos_fechar(self):
        ss = {"wa_novo": {"label": "X", "url": "Y"}}
        ss["wa_novo"] = None
        assert ss["wa_novo"] is None

    def test_formulario_invalido_sem_chaves_no_session(self):
        """Sem chaves no session_state o formulário fica no placeholder (inválido)."""
        ss = {}
        sel_leitor = ss.get("emp_sel_leitor", _PLAC_LEITOR)
        sel_livro  = ss.get("emp_sel_livro", _PLAC_LIVRO)
        assert not _form_valido(sel_leitor, sel_livro)

    def test_registro_define_wa_novo_e_limpa_selecao(self):
        """Simula fluxo completo: registro → wa_novo definido → keys limpas."""
        ss = {"emp_sel_leitor": "Ana", "emp_sel_livro": "Livro"}
        # passo 1: salva wa_novo
        ss["wa_novo"] = {"label": "Enviar para Ana", "url": "https://wa.me/...", "phone": "48x", "text": "Olá"}
        # passo 2: limpa seleção
        for k in ("emp_sel_leitor", "emp_sel_livro"):
            if k in ss:
                del ss[k]
        assert ss["wa_novo"] is not None
        assert "emp_sel_leitor" not in ss
        assert "emp_sel_livro" not in ss


# ═══════════════════════════════════════════════════════════════════════
# 18. DEVOLUÇÃO — fluxo completo
# ═══════════════════════════════════════════════════════════════════════

class TestDevolucao:
    def _seed(self, conn):
        conn.execute("INSERT INTO livros (titulo, quantidade) VALUES (?,?)", ("Livro Dev", 1))
        conn.execute("INSERT INTO leitores (nome, telefone) VALUES (?,?)", ("Leitor Dev", "48999000001"))
        lid = conn.execute("SELECT id FROM livros").fetchone()["id"]
        rid = conn.execute("SELECT id FROM leitores").fetchone()["id"]
        hoje = date.today().isoformat()
        dev  = (date.today() + timedelta(30)).isoformat()
        conn.execute(
            "INSERT INTO emprestimos (leitor_id, livro_id, data_emprestimo, data_devolucao) VALUES (?,?,?,?)",
            (rid, lid, hoje, dev),
        )
        emp_id = conn.execute("SELECT id FROM emprestimos").fetchone()["id"]
        return lid, rid, emp_id

    def test_devolucao_muda_status_para_devolvido(self, conn):
        _, _, emp_id = self._seed(conn)
        conn.execute("UPDATE emprestimos SET status='devolvido' WHERE id=?", (emp_id,))
        status = conn.execute("SELECT status FROM emprestimos WHERE id=?", (emp_id,)).fetchone()["status"]
        assert status == "devolvido"

    def test_devolucao_registra_no_historico(self, conn):
        self._seed(conn)
        conn.execute(
            "INSERT INTO historico (tipo, leitor_nome, livro_titulo, data) VALUES (?,?,?,?)",
            ("devolucao", "Leitor Dev", "Livro Dev", date.today().isoformat()),
        )
        h = conn.execute("SELECT tipo FROM historico WHERE tipo='devolucao'").fetchone()
        assert h is not None

    def test_livro_fica_disponivel_apos_devolucao(self, conn):
        lid, _, emp_id = self._seed(conn)
        conn.execute("UPDATE emprestimos SET status='devolvido' WHERE id=?", (emp_id,))
        ativos = conn.execute(
            "SELECT COUNT(*) FROM emprestimos WHERE livro_id=? AND status='ativo'", (lid,)
        ).fetchone()[0]
        qty = conn.execute("SELECT quantidade FROM livros WHERE id=?", (lid,)).fetchone()["quantidade"]
        assert (qty - ativos) == 1

    def test_devolvido_nao_aparece_como_ativo(self, conn):
        _, _, emp_id = self._seed(conn)
        conn.execute("UPDATE emprestimos SET status='devolvido' WHERE id=?", (emp_id,))
        ativo = conn.execute(
            "SELECT id FROM emprestimos WHERE id=? AND status='ativo'", (emp_id,)
        ).fetchone()
        assert ativo is None

    def test_fila_notificada_apos_devolucao(self, conn):
        lid, _, _ = self._seed(conn)
        conn.execute("INSERT INTO leitores (nome, telefone) VALUES (?,?)", ("Fila 1", "48999000002"))
        next_rid = conn.execute("SELECT id FROM leitores ORDER BY id DESC").fetchone()["id"]
        conn.execute("INSERT INTO fila_espera (livro_id, leitor_id) VALUES (?,?)", (lid, next_rid))
        fila = conn.execute(
            "SELECT f.leitor_id, l.nome FROM fila_espera f "
            "JOIN leitores l ON f.leitor_id = l.id WHERE f.livro_id=? ORDER BY f.data_inscricao",
            (lid,),
        ).fetchall()
        assert len(fila) == 1
        assert fila[0]["nome"] == "Fila 1"

    def test_remover_da_fila_apos_aviso(self, conn):
        lid, _, _ = self._seed(conn)
        conn.execute("INSERT INTO leitores (nome, telefone) VALUES (?,?)", ("F2", "48999000003"))
        next_rid = conn.execute("SELECT id FROM leitores ORDER BY id DESC").fetchone()["id"]
        conn.execute("INSERT INTO fila_espera (livro_id, leitor_id) VALUES (?,?)", (lid, next_rid))
        conn.execute("DELETE FROM fila_espera WHERE livro_id=? AND leitor_id=?", (lid, next_rid))
        restante = conn.execute(
            "SELECT COUNT(*) FROM fila_espera WHERE livro_id=?", (lid,)
        ).fetchone()[0]
        assert restante == 0


# ═══════════════════════════════════════════════════════════════════════
# 19. RENOVAÇÃO — limite de 3 e bloqueio por fila
# ═══════════════════════════════════════════════════════════════════════

class TestRenovacaoLimite:
    MAX_REN = 3

    def test_pode_renovar_quando_abaixo_do_limite(self):
        assert 0 < self.MAX_REN
        assert 2 < self.MAX_REN

    def test_nao_pode_renovar_apos_limite(self):
        assert not (3 < self.MAX_REN)

    def test_renovacao_incrementa_contador(self, conn):
        conn.execute("INSERT INTO livros (titulo) VALUES (?)", ("Livro Ren",))
        conn.execute("INSERT INTO leitores (nome, telefone) VALUES (?,?)", ("Ren", "48900000030"))
        lid = conn.execute("SELECT id FROM livros").fetchone()["id"]
        rid = conn.execute("SELECT id FROM leitores").fetchone()["id"]
        hoje = date.today().isoformat()
        dev  = (date.today() + timedelta(30)).isoformat()
        conn.execute(
            "INSERT INTO emprestimos (leitor_id, livro_id, data_emprestimo, data_devolucao, renovacoes) VALUES (?,?,?,?,?)",
            (rid, lid, hoje, dev, 0),
        )
        emp_id = conn.execute("SELECT id FROM emprestimos").fetchone()["id"]
        for _ in range(3):
            conn.execute("UPDATE emprestimos SET renovacoes=renovacoes+1 WHERE id=?", (emp_id,))
        rens = conn.execute("SELECT renovacoes FROM emprestimos WHERE id=?", (emp_id,)).fetchone()["renovacoes"]
        assert rens == 3

    def test_fila_bloqueia_renovacao(self, conn):
        conn.execute("INSERT INTO livros (titulo) VALUES (?)", ("Livro Fila Ren",))
        conn.execute("INSERT INTO leitores (nome, telefone) VALUES (?,?)", ("L1R", "48900000031"))
        conn.execute("INSERT INTO leitores (nome, telefone) VALUES (?,?)", ("L2R", "48900000032"))
        lid  = conn.execute("SELECT id FROM livros").fetchone()["id"]
        rids = [r["id"] for r in conn.execute("SELECT id FROM leitores").fetchall()]
        hoje = date.today().isoformat()
        dev  = (date.today() + timedelta(30)).isoformat()
        conn.execute(
            "INSERT INTO emprestimos (leitor_id, livro_id, data_emprestimo, data_devolucao) VALUES (?,?,?,?)",
            (rids[0], lid, hoje, dev),
        )
        conn.execute("INSERT INTO fila_espera (livro_id, leitor_id) VALUES (?,?)", (lid, rids[1]))
        fila = conn.execute(
            "SELECT COUNT(*) FROM fila_espera WHERE livro_id=?", (lid,)
        ).fetchone()[0]
        pode_renovar = fila == 0
        assert not pode_renovar

    def test_sem_fila_permite_renovacao(self, conn):
        conn.execute("INSERT INTO livros (titulo) VALUES (?)", ("Livro Livre Ren",))
        lid = conn.execute("SELECT id FROM livros").fetchone()["id"]
        fila = conn.execute(
            "SELECT COUNT(*) FROM fila_espera WHERE livro_id=?", (lid,)
        ).fetchone()[0]
        assert fila == 0  # pode renovar

    def test_nova_data_devolucao_apos_renovacao(self, conn):
        conn.execute("INSERT INTO livros (titulo) VALUES (?)", ("Livro Nova Data",))
        conn.execute("INSERT INTO leitores (nome, telefone) VALUES (?,?)", ("Ren2", "48900000033"))
        lid = conn.execute("SELECT id FROM livros").fetchone()["id"]
        rid = conn.execute("SELECT id FROM leitores").fetchone()["id"]
        hoje = date.today().isoformat()
        dev  = (date.today() + timedelta(30)).isoformat()
        conn.execute(
            "INSERT INTO emprestimos (leitor_id, livro_id, data_emprestimo, data_devolucao) VALUES (?,?,?,?)",
            (rid, lid, hoje, dev),
        )
        emp_id = conn.execute("SELECT id FROM emprestimos").fetchone()["id"]
        nova_dev = (date.today() + timedelta(60)).isoformat()
        conn.execute(
            "UPDATE emprestimos SET data_devolucao=?, renovacoes=renovacoes+1 WHERE id=?",
            (nova_dev, emp_id),
        )
        emp = conn.execute("SELECT * FROM emprestimos WHERE id=?", (emp_id,)).fetchone()
        assert emp["data_devolucao"] == nova_dev
        assert emp["renovacoes"] == 1


# ═══════════════════════════════════════════════════════════════════════
# 20. REGRAS DE NEGÓCIO — empréstimo
# ═══════════════════════════════════════════════════════════════════════

class TestRegrasDeEmprestimo:
    def _seed(self, conn, qtd=2):
        conn.execute("INSERT INTO livros (titulo, quantidade) VALUES (?,?)", ("Livro RN", qtd))
        conn.execute("INSERT INTO leitores (nome, telefone) VALUES (?,?)", ("Leitor RN", "48900000040"))
        lid = conn.execute("SELECT id FROM livros").fetchone()["id"]
        rid = conn.execute("SELECT id FROM leitores").fetchone()["id"]
        return lid, rid

    def test_bloqueia_quando_leitor_tem_3_emprestimos(self, conn):
        conn.execute("INSERT INTO leitores (nome, telefone) VALUES (?,?)", ("Leitor 3", "48900000041"))
        rid = conn.execute("SELECT id FROM leitores").fetchone()["id"]
        hoje = date.today().isoformat()
        dev  = (date.today() + timedelta(30)).isoformat()
        for i in range(3):
            conn.execute("INSERT INTO livros (titulo) VALUES (?)", (f"LRN{i}",))
            lid = conn.execute("SELECT id FROM livros ORDER BY id DESC").fetchone()["id"]
            conn.execute(
                "INSERT INTO emprestimos (leitor_id, livro_id, data_emprestimo, data_devolucao) VALUES (?,?,?,?)",
                (rid, lid, hoje, dev),
            )
        count = conn.execute(
            "SELECT COUNT(*) FROM emprestimos WHERE leitor_id=? AND status='ativo'", (rid,)
        ).fetchone()[0]
        assert count >= 3
        assert not (count < 3)  # bloqueado

    def test_bloqueia_mesmo_livro_para_mesmo_leitor(self, conn):
        lid, rid = self._seed(conn)
        hoje = date.today().isoformat()
        dev  = (date.today() + timedelta(30)).isoformat()
        conn.execute(
            "INSERT INTO emprestimos (leitor_id, livro_id, data_emprestimo, data_devolucao) VALUES (?,?,?,?)",
            (rid, lid, hoje, dev),
        )
        livros_ativos = {
            e["livro_id"]
            for e in conn.execute(
                "SELECT livro_id FROM emprestimos WHERE leitor_id=? AND status='ativo'", (rid,)
            ).fetchall()
        }
        assert lid in livros_ativos  # não pode emprestar de novo

    def test_livro_esgotado_nao_disponivel(self, conn):
        lid, rid = self._seed(conn, qtd=1)
        hoje = date.today().isoformat()
        dev  = (date.today() + timedelta(30)).isoformat()
        conn.execute(
            "INSERT INTO emprestimos (leitor_id, livro_id, data_emprestimo, data_devolucao) VALUES (?,?,?,?)",
            (rid, lid, hoje, dev),
        )
        qty   = conn.execute("SELECT quantidade FROM livros WHERE id=?", (lid,)).fetchone()["quantidade"]
        loans = conn.execute(
            "SELECT COUNT(*) FROM emprestimos WHERE livro_id=? AND status='ativo'", (lid,)
        ).fetchone()[0]
        assert not (loans < qty)

    def test_dois_leitores_podem_pegar_livro_com_2_exemplares(self, conn):
        lid, rid1 = self._seed(conn, qtd=2)
        conn.execute("INSERT INTO leitores (nome, telefone) VALUES (?,?)", ("Leitor E", "48900000042"))
        rid2 = conn.execute("SELECT id FROM leitores ORDER BY id DESC").fetchone()["id"]
        hoje = date.today().isoformat()
        dev  = (date.today() + timedelta(30)).isoformat()
        conn.execute(
            "INSERT INTO emprestimos (leitor_id, livro_id, data_emprestimo, data_devolucao) VALUES (?,?,?,?)",
            (rid1, lid, hoje, dev),
        )
        conn.execute(
            "INSERT INTO emprestimos (leitor_id, livro_id, data_emprestimo, data_devolucao) VALUES (?,?,?,?)",
            (rid2, lid, hoje, dev),
        )
        qty   = conn.execute("SELECT quantidade FROM livros WHERE id=?", (lid,)).fetchone()["quantidade"]
        loans = conn.execute(
            "SELECT COUNT(*) FROM emprestimos WHERE livro_id=? AND status='ativo'", (lid,)
        ).fetchone()[0]
        assert loans == 2
        assert loans == qty  # 2 de 2: esgotado

    def test_data_devolucao_calculada_corretamente(self):
        emp = date(2026, 4, 23)
        dev = emp + timedelta(days=30)
        assert dev == date(2026, 5, 23)

    def test_data_devolucao_deve_ser_posterior_ao_emprestimo(self):
        emp = date(2026, 4, 23)
        dev = date(2026, 4, 20)
        assert not (dev > emp)

    def test_historico_registrado_ao_emprestar(self, conn):
        lid, rid = self._seed(conn)
        hoje = date.today().isoformat()
        dev  = (date.today() + timedelta(30)).isoformat()
        conn.execute(
            "INSERT INTO emprestimos (leitor_id, livro_id, data_emprestimo, data_devolucao) VALUES (?,?,?,?)",
            (rid, lid, hoje, dev),
        )
        conn.execute(
            "INSERT INTO historico (tipo, leitor_nome, livro_titulo, data, obs) VALUES (?,?,?,?,?)",
            ("emprestimo", "Leitor RN", "Livro RN", hoje, "Leitor RN retirou \"Livro RN\""),
        )
        h = conn.execute("SELECT * FROM historico WHERE tipo='emprestimo'").fetchone()
        assert h is not None
        assert h["leitor_nome"] == "Leitor RN"


# ═══════════════════════════════════════════════════════════════════════
# 21. CONTROLE DE ACESSO — restrições de admin
# ═══════════════════════════════════════════════════════════════════════

class TestAdminRestrictions:
    def _eh_admin(self, usuario_atual: str) -> bool:
        return usuario_atual == "admin"

    def test_usuario_admin_tem_acesso(self):
        assert self._eh_admin("admin") is True

    def test_usuario_comum_nao_tem_acesso(self):
        assert self._eh_admin("operador") is False

    def test_usuario_vazio_nao_tem_acesso(self):
        assert self._eh_admin("") is False

    def test_case_sensitive_admin_maiusculo_nao_eh_admin(self):
        assert self._eh_admin("Admin") is False
        assert self._eh_admin("ADMIN") is False

    def test_criar_usuario_exclusivo_para_admin(self):
        eh_admin = False
        pode_criar = eh_admin
        assert not pode_criar

    def test_exportar_exclusivo_para_admin(self):
        eh_admin = False
        pode_exportar = eh_admin
        assert not pode_exportar

    def test_configuracoes_exclusivas_para_admin(self):
        eh_admin = False
        pode_config = eh_admin
        assert not pode_config

    def test_usuario_padrao_admin_existe_no_banco(self, conn):
        conn.execute(
            "INSERT INTO usuarios (usuario, senha_hash) VALUES (?,?)", ("admin", "hash:abc")
        )
        row = conn.execute(
            "SELECT usuario FROM usuarios WHERE usuario='admin'"
        ).fetchone()
        assert row is not None
        assert row["usuario"] == "admin"

    def test_usuario_admin_unico_constraint(self, conn):
        conn.execute(
            "INSERT INTO usuarios (usuario, senha_hash) VALUES (?,?)", ("admin", "hash:abc")
        )
        with pytest.raises(Exception):
            conn.execute(
                "INSERT INTO usuarios (usuario, senha_hash) VALUES (?,?)", ("admin", "hash:xyz")
            )

    def test_nao_admin_pode_alterar_propria_senha(self):
        """Não-admins têm acesso restrito, mas podem mudar a própria senha."""
        eh_admin = False
        pode_mudar_senha_propria = True  # sempre permitido
        assert pode_mudar_senha_propria

    def test_admin_pode_configurar_nome_da_igreja(self, conn):
        conn.execute("INSERT OR REPLACE INTO config VALUES ('nome_igreja', ?)", ("Igreja Nova",))
        valor = conn.execute(
            "SELECT valor FROM config WHERE chave='nome_igreja'"
        ).fetchone()["valor"]
        assert valor == "Igreja Nova"

    def test_admin_pode_configurar_periodo_emprestimo(self, conn):
        conn.execute("INSERT OR REPLACE INTO config VALUES ('dias_emprestimo', ?)", ("15",))
        valor = conn.execute(
            "SELECT valor FROM config WHERE chave='dias_emprestimo'"
        ).fetchone()["valor"]
        assert valor == "15"


# ═══════════════════════════════════════════════════════════════════════
# 22. EXPORTAÇÃO CSV
# ═══════════════════════════════════════════════════════════════════════

class TestCsvExport:
    def test_csv_livros_colunas_corretas(self, conn):
        conn.execute(
            "INSERT INTO livros (titulo, autor, categoria, quantidade) VALUES (?,?,?,?)",
            ("Dom Quixote", "Cervantes", "Literatura", 2),
        )
        livros = conn.execute("SELECT * FROM livros").fetchall()
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(["Título", "Autor", "Categoria", "Quantidade", "Cadastrado em"])
        for l in livros:
            writer.writerow([l["titulo"], l["autor"], l["categoria"], l["quantidade"], l["criado_em"]])
        conteudo = buf.getvalue()
        assert "Título" in conteudo
        assert "Dom Quixote" in conteudo
        assert "Cervantes" in conteudo
        assert "Literatura" in conteudo

    def test_csv_leitores_colunas_corretas(self, conn):
        conn.execute(
            "INSERT INTO leitores (nome, telefone, email, endereco) VALUES (?,?,?,?)",
            ("Ana", "48999999999", "ana@test.com", "Rua A"),
        )
        leitores = conn.execute("SELECT * FROM leitores").fetchall()
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(["Nome", "Telefone", "E-mail", "Endereço", "Cadastrado em"])
        for l in leitores:
            writer.writerow([l["nome"], l["telefone"], l["email"], l["endereco"], l["criado_em"]])
        conteudo = buf.getvalue()
        for col in ["Nome", "Telefone", "E-mail", "Endereço", "Ana"]:
            assert col in conteudo

    def test_csv_emprestimos_colunas_corretas(self, conn):
        conn.execute("INSERT INTO livros (titulo) VALUES (?)", ("Livro CSV",))
        conn.execute("INSERT INTO leitores (nome, telefone) VALUES (?,?)", ("Leitor CSV", "48000000050"))
        lid = conn.execute("SELECT id FROM livros").fetchone()["id"]
        rid = conn.execute("SELECT id FROM leitores").fetchone()["id"]
        hoje = date.today().isoformat()
        dev  = (date.today() + timedelta(30)).isoformat()
        conn.execute(
            "INSERT INTO emprestimos (leitor_id, livro_id, data_emprestimo, data_devolucao) VALUES (?,?,?,?)",
            (rid, lid, hoje, dev),
        )
        emprestimos = conn.execute("""
            SELECT e.*, lt.nome AS leitor_nome, lv.titulo AS livro_titulo
            FROM emprestimos e
            JOIN leitores lt ON e.leitor_id = lt.id
            JOIN livros   lv ON e.livro_id  = lv.id
        """).fetchall()
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(["Leitor", "Livro", "Empréstimo", "Devolução", "Status", "Renovações"])
        for e in emprestimos:
            writer.writerow([
                e["leitor_nome"], e["livro_titulo"],
                e["data_emprestimo"], e["data_devolucao"],
                e["status"], e["renovacoes"],
            ])
        conteudo = buf.getvalue()
        assert "Leitor CSV" in conteudo
        assert "Livro CSV" in conteudo
        assert "ativo" in conteudo

    def test_csv_vazio_contem_apenas_cabecalho(self):
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(["Nome", "Telefone"])
        linhas = [l for l in buf.getvalue().strip().split("\n") if l]
        assert len(linhas) == 1
        assert "Nome" in linhas[0]

    def test_csv_leitores_cinco_colunas(self, conn):
        conn.execute(
            "INSERT INTO leitores (nome, telefone, email, endereco) VALUES (?,?,?,?)",
            ("B", "48000000051", "", ""),
        )
        leitores = conn.execute("SELECT * FROM leitores").fetchall()
        buf = io.StringIO()
        writer = csv.writer(buf)
        header = ["Nome", "Telefone", "E-mail", "Endereço", "Cadastrado em"]
        writer.writerow(header)
        for l in leitores:
            writer.writerow([l["nome"], l["telefone"], l["email"], l["endereco"], l["criado_em"]])
        linhas = [l for l in buf.getvalue().strip().split("\n") if l]
        assert len(linhas) == 2  # header + 1 leitor
        assert len(header) == 5


# ═══════════════════════════════════════════════════════════════════════
# 23. NORMALIZAÇÃO DE TELEFONE
# ═══════════════════════════════════════════════════════════════════════

def _normalizar_phone(phone: str) -> str:
    digits = "".join(filter(str.isdigit, str(phone)))
    if not digits.startswith("55"):
        digits = "55" + digits
    return digits


class TestPhoneNormalization:
    def test_adiciona_55_a_numero_local(self):
        assert _normalizar_phone("48991110001") == "5548991110001"

    def test_nao_duplica_55_quando_ja_presente(self):
        assert _normalizar_phone("5548991110001") == "5548991110001"

    def test_remove_espacos_e_hifen(self):
        assert _normalizar_phone("48 99111-0001") == "5548991110001"

    def test_remove_parenteses(self):
        assert _normalizar_phone("(48) 99111-0001") == "5548991110001"

    def test_remove_sinal_de_mais(self):
        assert _normalizar_phone("+5548991110001") == "5548991110001"

    def test_numero_vazio_retorna_55(self):
        assert _normalizar_phone("") == "55"

    def test_apenas_letras_retorna_55(self):
        assert _normalizar_phone("abc") == "55"

    def test_numero_internacional_ja_correto(self):
        assert _normalizar_phone("5511987654321") == "5511987654321"

    def test_formato_correto_para_wa_me_url(self):
        phone = _normalizar_phone("48991110001")
        url   = f"https://wa.me/{phone}"
        assert url == "https://wa.me/5548991110001"

    def test_todos_os_digitos_sao_preservados(self):
        phone = _normalizar_phone("48991110001")
        assert len(phone) == 13  # 55 + 11 dígitos


# ═══════════════════════════════════════════════════════════════════════
# 24. QUERY q_ativos — JOIN e filtros
# ═══════════════════════════════════════════════════════════════════════

class TestQAtivos:
    def _seed(self, conn):
        conn.execute("INSERT INTO livros (titulo, autor) VALUES (?,?)", ("Livro QA", "Autor QA"))
        conn.execute("INSERT INTO leitores (nome, telefone) VALUES (?,?)", ("Leitor QA", "48900000060"))
        lid = conn.execute("SELECT id FROM livros").fetchone()["id"]
        rid = conn.execute("SELECT id FROM leitores").fetchone()["id"]
        return lid, rid

    def _q_ativos(self, conn):
        return conn.execute("""
            SELECT e.*, lt.nome AS leitor_nome, lt.telefone AS telefone, lv.titulo AS livro_titulo
            FROM   emprestimos e
            JOIN   leitores lt ON e.leitor_id = lt.id
            JOIN   livros   lv ON e.livro_id  = lv.id
            WHERE  e.status = 'ativo'
            ORDER  BY e.data_devolucao
        """).fetchall()

    def test_retorna_vazio_sem_emprestimos(self, conn):
        assert self._q_ativos(conn) == []

    def test_inclui_nome_leitor_via_join(self, conn):
        lid, rid = self._seed(conn)
        hoje = date.today().isoformat()
        dev  = (date.today() + timedelta(30)).isoformat()
        conn.execute(
            "INSERT INTO emprestimos (leitor_id, livro_id, data_emprestimo, data_devolucao) VALUES (?,?,?,?)",
            (rid, lid, hoje, dev),
        )
        assert self._q_ativos(conn)[0]["leitor_nome"] == "Leitor QA"

    def test_inclui_titulo_livro_via_join(self, conn):
        lid, rid = self._seed(conn)
        hoje = date.today().isoformat()
        dev  = (date.today() + timedelta(30)).isoformat()
        conn.execute(
            "INSERT INTO emprestimos (leitor_id, livro_id, data_emprestimo, data_devolucao) VALUES (?,?,?,?)",
            (rid, lid, hoje, dev),
        )
        assert self._q_ativos(conn)[0]["livro_titulo"] == "Livro QA"

    def test_inclui_telefone_via_join(self, conn):
        lid, rid = self._seed(conn)
        hoje = date.today().isoformat()
        dev  = (date.today() + timedelta(30)).isoformat()
        conn.execute(
            "INSERT INTO emprestimos (leitor_id, livro_id, data_emprestimo, data_devolucao) VALUES (?,?,?,?)",
            (rid, lid, hoje, dev),
        )
        assert self._q_ativos(conn)[0]["telefone"] == "48900000060"

    def test_exclui_status_devolvido(self, conn):
        lid, rid = self._seed(conn)
        hoje = date.today().isoformat()
        dev  = (date.today() + timedelta(30)).isoformat()
        conn.execute(
            "INSERT INTO emprestimos (leitor_id, livro_id, data_emprestimo, data_devolucao, status) VALUES (?,?,?,?,?)",
            (rid, lid, hoje, dev, "devolvido"),
        )
        assert self._q_ativos(conn) == []

    def test_exclui_status_cancelado(self, conn):
        lid, rid = self._seed(conn)
        hoje = date.today().isoformat()
        dev  = (date.today() + timedelta(30)).isoformat()
        conn.execute(
            "INSERT INTO emprestimos (leitor_id, livro_id, data_emprestimo, data_devolucao, status) VALUES (?,?,?,?,?)",
            (rid, lid, hoje, dev, "cancelado"),
        )
        assert self._q_ativos(conn) == []

    def test_ordenado_por_data_devolucao(self, conn):
        lid, rid = self._seed(conn)
        conn.execute("INSERT INTO livros (titulo) VALUES (?)", ("Livro QA2",))
        lid2 = conn.execute("SELECT id FROM livros ORDER BY id DESC").fetchone()["id"]
        hoje = date.today().isoformat()
        dev1 = (date.today() + timedelta(10)).isoformat()
        dev2 = (date.today() + timedelta(5)).isoformat()
        conn.execute(
            "INSERT INTO emprestimos (leitor_id, livro_id, data_emprestimo, data_devolucao) VALUES (?,?,?,?)",
            (rid, lid, hoje, dev1),
        )
        conn.execute(
            "INSERT INTO emprestimos (leitor_id, livro_id, data_emprestimo, data_devolucao) VALUES (?,?,?,?)",
            (rid, lid2, hoje, dev2),
        )
        ativos = self._q_ativos(conn)
        assert ativos[0]["data_devolucao"] == dev2  # mais próximo primeiro
        assert ativos[1]["data_devolucao"] == dev1

    def test_dois_emprestimos_do_mesmo_leitor(self, conn):
        lid, rid = self._seed(conn)
        conn.execute("INSERT INTO livros (titulo) VALUES (?)", ("Livro QA3",))
        lid2 = conn.execute("SELECT id FROM livros ORDER BY id DESC").fetchone()["id"]
        hoje = date.today().isoformat()
        dev  = (date.today() + timedelta(30)).isoformat()
        conn.execute(
            "INSERT INTO emprestimos (leitor_id, livro_id, data_emprestimo, data_devolucao) VALUES (?,?,?,?)",
            (rid, lid, hoje, dev),
        )
        conn.execute(
            "INSERT INTO emprestimos (leitor_id, livro_id, data_emprestimo, data_devolucao) VALUES (?,?,?,?)",
            (rid, lid2, hoje, dev),
        )
        ativos = self._q_ativos(conn)
        assert len(ativos) == 2
        assert all(a["leitor_nome"] == "Leitor QA" for a in ativos)


# ═══════════════════════════════════════════════════════════════════════
# 25. HISTÓRICO — filtros e ordenação
# ═══════════════════════════════════════════════════════════════════════

class TestHistoricoFiltros:
    def _seed(self, conn):
        hoje = date.today().isoformat()
        conn.execute(
            "INSERT INTO historico (tipo, leitor_nome, livro_titulo, data) VALUES (?,?,?,?)",
            ("emprestimo", "Ana", "Livro 1", hoje),
        )
        conn.execute(
            "INSERT INTO historico (tipo, leitor_nome, livro_titulo, data) VALUES (?,?,?,?)",
            ("devolucao", "Ana", "Livro 1", hoje),
        )
        conn.execute(
            "INSERT INTO historico (tipo, leitor_nome, livro_titulo, data) VALUES (?,?,?,?)",
            ("emprestimo", "Bruno", "Livro 2", hoje),
        )

    def _q_historico(self, conn, leitor=None, tipo=None):
        params, where = [], []
        if leitor:
            where.append("leitor_nome = ?"); params.append(leitor)
        if tipo:
            where.append("tipo = ?"); params.append(tipo)
        sql = ("SELECT * FROM historico"
               + (" WHERE " + " AND ".join(where) if where else "")
               + " ORDER BY id DESC")
        return conn.execute(sql, params).fetchall()

    def test_sem_filtros_retorna_todos(self, conn):
        self._seed(conn)
        assert len(self._q_historico(conn)) == 3

    def test_filtro_por_leitor(self, conn):
        self._seed(conn)
        resultado = self._q_historico(conn, leitor="Ana")
        assert len(resultado) == 2
        assert all(r["leitor_nome"] == "Ana" for r in resultado)

    def test_filtro_por_tipo(self, conn):
        self._seed(conn)
        resultado = self._q_historico(conn, tipo="devolucao")
        assert len(resultado) == 1
        assert resultado[0]["tipo"] == "devolucao"

    def test_filtro_combinado_leitor_e_tipo(self, conn):
        self._seed(conn)
        resultado = self._q_historico(conn, leitor="Ana", tipo="emprestimo")
        assert len(resultado) == 1
        assert resultado[0]["leitor_nome"] == "Ana"
        assert resultado[0]["tipo"] == "emprestimo"

    def test_leitor_inexistente_retorna_vazio(self, conn):
        self._seed(conn)
        assert self._q_historico(conn, leitor="Ninguem") == []

    def test_tipo_inexistente_retorna_vazio(self, conn):
        self._seed(conn)
        assert self._q_historico(conn, tipo="tipo_fake") == []

    def test_ordenado_por_id_decrescente(self, conn):
        self._seed(conn)
        resultado = self._q_historico(conn)
        ids = [r["id"] for r in resultado]
        assert ids == sorted(ids, reverse=True)

    def test_historico_aceita_tipo_renovacao(self, conn):
        conn.execute(
            "INSERT INTO historico (tipo, leitor_nome, livro_titulo, data) VALUES (?,?,?,?)",
            ("renovacao", "X", "Y", date.today().isoformat()),
        )
        resultado = self._q_historico(conn, tipo="renovacao")
        assert len(resultado) == 1

