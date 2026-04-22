import streamlit as st
import sqlite3
import csv
import io
import os
import hashlib
import urllib.parse
from datetime import date, timedelta

# ══════════════════════════════════════════════════════════════════════
# CONFIG
# ══════════════════════════════════════════════════════════════════════

DB = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'biblioteca.db')
)

st.set_page_config(
    page_title="Biblioteca ICR",
    page_icon="📚",
    layout="centered",
    initial_sidebar_state="collapsed",
)

# ══════════════════════════════════════════════════════════════════════
# DESIGN SYSTEM
# ══════════════════════════════════════════════════════════════════════

st.markdown("""
<style>
/* ═══ Tokens ═══════════════════════════════════════ */
:root {
  --blue:      #2563eb;
  --blue-dk:   #1d4ed8;
  --green:     #16a34a;
  --amber:     #d97706;
  --red:       #dc2626;
  --muted:     #6b7280;
  --border:    #e5e7eb;
  --bg:        #f1f5f9;
  --card:      #ffffff;
  --text:      #0f172a;
  --text2:     #475569;
  --r:         16px;
  --sh:        0 1px 3px rgba(0,0,0,.06), 0 4px 16px rgba(0,0,0,.06);
  --sh-lg:     0 4px 24px rgba(0,0,0,.1);
}

/* ═══ Page canvas ══════════════════════════════════ */
[data-testid="stAppViewContainer"] { background: var(--bg) !important; }
.main .block-container {
  max-width: 520px !important;
  padding: 0 14px 100px !important;
  margin: 0 auto !important;
}

/* ═══ Branded header bar ═══════════════════════════ */
.lib-header {
  background: linear-gradient(135deg, #1e3a5f 0%, #2563eb 100%);
  margin: 0 -14px;
  padding: 24px 20px 20px;
  display: flex;
  align-items: center;
  gap: 16px;
  margin-bottom: 2px;
}
.lib-header-icon {
  width: 56px; height: 56px;
  background: rgba(255,255,255,.18);
  border-radius: 16px;
  display: flex; align-items: center; justify-content: center;
  font-size: 1.9rem;
  flex-shrink: 0;
  box-shadow: 0 2px 8px rgba(0,0,0,.2);
}
.lib-header-name {
  font-size: 1.4rem;
  font-weight: 900;
  color: white;
  letter-spacing: -.02em;
  line-height: 1.1;
}
.lib-header-sub {
  font-size: .82rem;
  color: rgba(255,255,255,.72);
  margin-top: 3px;
}

/* ═══ TABS — horizontal scroll (fix truncation) ═══ */
[data-testid="stTabs"] > div:first-child {
  overflow-x: auto !important;
  -webkit-overflow-scrolling: touch !important;
  scrollbar-width: none !important;
  background: var(--card) !important;
  margin: 0 -14px !important;
  padding: 0 6px !important;
  border-bottom: 2px solid var(--border) !important;
  box-shadow: 0 2px 8px rgba(0,0,0,.06) !important;
  position: sticky !important;
  top: 0 !important;
  z-index: 200 !important;
}
[data-testid="stTabs"] > div:first-child::-webkit-scrollbar { display: none !important; }
[data-testid="stTabs"] > div:first-child > div {
  flex-wrap: nowrap !important;
  min-width: max-content !important;
  border-bottom: none !important;
  gap: 0 !important;
}
button[role="tab"] {
  white-space: nowrap !important;
  flex-shrink: 0 !important;
  font-size: .84rem !important;
  font-weight: 600 !important;
  min-height: 48px !important;
  padding: 12px 16px !important;
  color: var(--muted) !important;
  background: transparent !important;
  border: none !important;
  border-bottom: 3px solid transparent !important;
  border-radius: 0 !important;
  transition: color .2s, border-color .2s !important;
}
button[role="tab"][aria-selected="true"] {
  color: var(--blue) !important;
  border-bottom-color: var(--blue) !important;
  font-weight: 700 !important;
}
button[role="tab"]:hover:not([aria-selected="true"]) {
  color: var(--text) !important;
  background: #f8fafc !important;
}

/* ═══ Sub-tabs (inside Empréstimo) ═══════════════ */
[data-testid="stTabs"] [data-testid="stTabs"] > div:first-child {
  position: relative !important;
  top: auto !important;
  z-index: auto !important;
  box-shadow: none !important;
  border-radius: 12px !important;
  margin: 14px 0 8px !important;
  background: #f1f5f9 !important;
  padding: 4px !important;
  border-bottom: none !important;
}
[data-testid="stTabs"] [data-testid="stTabs"] > div:first-child > div {
  min-width: unset !important;
  gap: 4px !important;
}
[data-testid="stTabs"] [data-testid="stTabs"] button[role="tab"] {
  border-radius: 10px !important;
  min-height: 40px !important;
  padding: 8px 14px !important;
  font-size: .83rem !important;
  color: var(--muted) !important;
  border-bottom: none !important;
  flex: 1 !important;
}
[data-testid="stTabs"] [data-testid="stTabs"] button[role="tab"][aria-selected="true"] {
  background: white !important;
  color: var(--blue) !important;
  box-shadow: 0 1px 4px rgba(0,0,0,.1) !important;
  border-bottom: none !important;
}

/* ═══ Metric grid ═══════════════════════════════ */
.mg {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
  margin: 20px 0 18px;
}
.mc {
  background: var(--card);
  border-radius: var(--r);
  border: 1px solid var(--border);
  box-shadow: var(--sh);
  padding: 20px 10px 16px;
  text-align: center;
}
.mc .v {
  font-size: 2.6rem;
  font-weight: 900;
  line-height: 1;
  letter-spacing: -.03em;
}
.mc .l {
  font-size: .7rem;
  font-weight: 700;
  color: var(--muted);
  margin-top: 6px;
  text-transform: uppercase;
  letter-spacing: .07em;
}

/* ═══ Status pill ═══════════════════════════════ */
.sp {
  display: inline-block;
  font-size: .72rem;
  font-weight: 700;
  padding: 4px 12px;
  border-radius: 99px;
  letter-spacing: .02em;
}
.sp-ok   { background: #dcfce7; color: #15803d; }
.sp-warn { background: #fef3c7; color: #92400e; }
.sp-late { background: #fee2e2; color: #b91c1c; }
.sp-blue { background: #dbeafe; color: #1e40af; }
.sp-gray { background: #f1f5f9; color: #475569; }

/* ═══ Alert cards ═══════════════════════════════ */
.al {
  border-left: 4px solid;
  border-radius: var(--r);
  padding: 16px 18px;
  margin-bottom: 10px;
  box-shadow: var(--sh);
}
.al-ok   { background: #f0fdf4; border-color: #22c55e; }
.al-warn { background: #fffbeb; border-color: #f59e0b; }
.al-err  { background: #fef2f2; border-color: #ef4444; }
.al .at  { font-weight: 700; font-size: 1rem; color: var(--text); }
.al .ab  { font-size: .85rem; color: #374151; margin-top: 5px; line-height: 1.5; }

/* ═══ Section label ═════════════════════════════ */
.sl {
  font-size: .68rem;
  font-weight: 800;
  text-transform: uppercase;
  letter-spacing: .1em;
  color: var(--muted);
  margin: 22px 0 10px;
}

/* ═══ Loan card ═════════════════════════════════ */
.lc {
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: var(--r);
  box-shadow: var(--sh);
  padding: 16px;
  margin-bottom: 10px;
  overflow: hidden;
}
.lc-hdr  { display: flex; justify-content: space-between; align-items: flex-start; gap: 8px; }
.lc-book { font-size: 1.05rem; font-weight: 800; color: var(--text); line-height: 1.25; flex: 1; }
.lc-who  { font-size: .85rem; color: var(--text2); margin-top: 4px; }
.lc-date { font-size: .78rem; color: var(--muted); margin-top: 10px; padding-top: 10px; border-top: 1px solid var(--border); }
.lc-rens { font-size: .72rem; color: var(--muted); margin-top: 5px; }

/* ═══ Book card ═════════════════════════════════ */
.bc {
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: var(--r);
  box-shadow: var(--sh);
  padding: 16px;
  margin-bottom: 10px;
}
.bc-title  { font-size: 1.05rem; font-weight: 800; color: var(--text); }
.bc-author { font-size: .85rem; color: var(--text2); margin-top: 3px; }
.bc-cat    { font-size: .75rem; font-weight: 600; color: var(--blue); margin-top: 6px; text-transform: uppercase; letter-spacing: .04em; }
.bc-info   { font-size: .78rem; color: var(--muted); margin-top: 8px; padding-top: 8px; border-top: 1px solid var(--border); }

/* ═══ Reader card ════════════════════════════════ */
.rc {
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: var(--r);
  box-shadow: var(--sh);
  padding: 16px;
  margin-bottom: 10px;
}
.rc-name  { font-size: 1.05rem; font-weight: 800; color: var(--text); }
.rc-phone { font-size: .87rem; color: var(--text2); margin-top: 3px; }
.rc-extra { font-size: .78rem; color: var(--muted); margin-top: 3px; }

/* ═══ History item ══════════════════════════════ */
.hi {
  border-left: 4px solid;
  border-radius: 0 14px 14px 0;
  padding: 13px 16px;
  margin-bottom: 9px;
  background: var(--card);
  box-shadow: 0 1px 4px rgba(0,0,0,.06);
  overflow: hidden;
}
.hi-hdr { display: flex; justify-content: space-between; align-items: center; margin-bottom: 5px; }
.hi .ht { font-size: .68rem; font-weight: 800; text-transform: uppercase; letter-spacing: .07em; }
.hi .hd { font-size: .68rem; color: var(--muted); }
.hi .ho { font-size: .88rem; color: #1f2937; line-height: 1.45; }

/* ═══ ID tag ════════════════════════════════════ */
.id-tag {
  font-size: .67rem;
  font-weight: 700;
  color: var(--muted);
  background: #f1f5f9;
  border: 1px solid var(--border);
  padding: 1px 6px;
  border-radius: 4px;
  font-family: monospace;
  letter-spacing: .02em;
  vertical-align: middle;
}

/* ═══ WhatsApp button ════════════════════════════ */
.wa {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  background: #25D366;
  color: white !important;
  border-radius: 12px;
  padding: 15px;
  margin-top: 12px;
  font-weight: 700;
  font-size: .97rem;
  text-decoration: none !important;
  cursor: pointer;
  transition: background .15s, transform .1s;
}
.wa:hover  { background: #22c55e; }
.wa:active { background: #16a34a; transform: scale(.98); }

/* ═══ Native Streamlit overrides ════════════════ */

/* Buttons */
button[kind="primary"], button[kind="primaryFormSubmit"] {
  min-height: 52px !important;
  font-size: .97rem !important;
  font-weight: 700 !important;
  border-radius: 12px !important;
  letter-spacing: -.01em !important;
  background-color: #16a34a !important;
  border-color: #16a34a !important;
  color: #ffffff !important;
}
button[kind="primary"]:hover, button[kind="primaryFormSubmit"]:hover {
  background-color: #15803d !important;
  border-color: #15803d !important;
}
button[kind="primary"]:active, button[kind="primaryFormSubmit"]:active {
  background-color: #14532d !important;
  border-color: #14532d !important;
}
button[kind="secondary"] {
  min-height: 46px !important;
  font-size: .9rem !important;
  font-weight: 600 !important;
  border-radius: 12px !important;
}
[data-testid="stLinkButton"] a {
  min-height: 50px !important;
  border-radius: 12px !important;
  font-weight: 600 !important;
  font-size: .93rem !important;
  display: flex !important;
  align-items: center !important;
  justify-content: center !important;
}

/* Inputs — prevent iOS zoom (min 16px) */
[data-testid="stTextInput"] input,
[data-testid="stDateInput"] input,
[data-testid="stNumberInput"] input {
  min-height: 50px !important;
  font-size: 1rem !important;
  border-radius: 10px !important;
  padding: 0 14px !important;
}
[data-testid="stSelectbox"] > div > div {
  min-height: 50px !important;
  border-radius: 10px !important;
  font-size: 1rem !important;
}

/* Labels */
[data-testid="stTextInput"] label,
[data-testid="stSelectbox"] label,
[data-testid="stDateInput"] label,
[data-testid="stNumberInput"] label,
[data-testid="stTextArea"] label {
  font-size: .87rem !important;
  font-weight: 700 !important;
  color: var(--text2) !important;
  margin-bottom: 3px !important;
}

/* Bordered containers */
[data-testid="stVerticalBlockBorderWrapper"] {
  border-radius: var(--r) !important;
  border: 1px solid var(--border) !important;
  box-shadow: var(--sh) !important;
  margin-bottom: 10px !important;
  background: var(--card) !important;
  overflow: hidden !important;
}

/* Expander */
[data-testid="stExpander"] details {
  border-radius: var(--r) !important;
  border: 1px solid var(--border) !important;
  box-shadow: var(--sh) !important;
  margin-bottom: 10px !important;
  overflow: hidden !important;
  background: var(--card) !important;
}
[data-testid="stExpander"] summary {
  font-size: .92rem !important;
  font-weight: 700 !important;
  min-height: 54px !important;
  display: flex !important;
  align-items: center !important;
  background: var(--card) !important;
}

/* Alert */
[data-testid="stAlert"] { border-radius: var(--r) !important; font-size: .9rem !important; }

/* Info/success/warning */
[data-testid="stNotification"] { border-radius: var(--r) !important; }

/* Metric */
[data-testid="stMetricValue"] { font-size: 2rem !important; }

/* Hide Streamlit chrome */
#MainMenu, footer, header      { visibility: hidden !important; }
[data-testid="stDecoration"]   { display: none !important; }
[data-testid="stToolbar"]      { display: none !important; }
</style>
""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════
# BANCO DE DADOS
# ══════════════════════════════════════════════════════════════════════

def get_conn():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    with get_conn() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS livros (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            titulo      TEXT NOT NULL,
            autor       TEXT DEFAULT '',
            categoria   TEXT DEFAULT '',
            quantidade  INTEGER DEFAULT 1,
            criado_em   DATE DEFAULT CURRENT_DATE
        );
        CREATE TABLE IF NOT EXISTS leitores (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            nome        TEXT NOT NULL,
            telefone    TEXT NOT NULL,
            email       TEXT DEFAULT '',
            endereco    TEXT DEFAULT '',
            criado_em   DATE DEFAULT CURRENT_DATE
        );
        CREATE TABLE IF NOT EXISTS emprestimos (
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
        CREATE TABLE IF NOT EXISTS historico (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            tipo          TEXT NOT NULL,
            leitor_nome   TEXT NOT NULL,
            livro_titulo  TEXT NOT NULL,
            data          DATE DEFAULT CURRENT_DATE,
            obs           TEXT DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS config (
            chave TEXT PRIMARY KEY,
            valor TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS fila_espera (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            livro_id        INTEGER NOT NULL,
            leitor_id       INTEGER NOT NULL,
            data_inscricao  DATE DEFAULT CURRENT_DATE,
            FOREIGN KEY (livro_id)  REFERENCES livros(id),
            FOREIGN KEY (leitor_id) REFERENCES leitores(id),
            UNIQUE(livro_id, leitor_id)
        );
        CREATE TABLE IF NOT EXISTS usuarios (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario    TEXT NOT NULL UNIQUE,
            senha_hash TEXT NOT NULL,
            criado_em  DATE DEFAULT CURRENT_DATE
        );
        """)


init_db()

# ── Migrações de colunas ────────────────────────────────────────────
_MIGRATE = [
    ("leitores", "email",    "ALTER TABLE leitores ADD COLUMN email    TEXT DEFAULT ''"),
    ("leitores", "endereco", "ALTER TABLE leitores ADD COLUMN endereco TEXT DEFAULT ''"),
]
with get_conn() as _mc:
    _cols = {r[1] for r in _mc.execute("PRAGMA table_info(leitores)")}
    for _tbl, _col, _sql in _MIGRATE:
        if _col not in _cols:
            _mc.execute(_sql)

with get_conn() as _mc:
    _livros_cols = {r[1] for r in _mc.execute("PRAGMA table_info(livros)")}
    if "quantidade" not in _livros_cols:
        _mc.execute("ALTER TABLE livros ADD COLUMN quantidade INTEGER DEFAULT 1")

# ── Usuário admin padrão ─────────────────────────────────────────────
def _hash_senha(senha: str, salt: bytes = None) -> str:
    if salt is None:
        salt = os.urandom(16)
    dk = hashlib.pbkdf2_hmac('sha256', senha.encode('utf-8'), salt, 200_000)
    return salt.hex() + ':' + dk.hex()

with get_conn() as _uc:
    _existe = _uc.execute("SELECT COUNT(*) FROM usuarios WHERE usuario='admin'").fetchone()[0]
    if not _existe:
        _uc.execute("INSERT INTO usuarios (usuario, senha_hash) VALUES (?,?)",
                    ('admin', _hash_senha('2310')))


# ══════════════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════════════

def get_cfg() -> dict:
    with get_conn() as conn:
        rows = conn.execute("SELECT chave, valor FROM config").fetchall()
    d = {r["chave"]: r["valor"] for r in rows}
    return {
        "nome_igreja": d.get("nome_igreja", "Igreja Cristã Reformada"),
        "dias": int(d.get("dias_emprestimo", "30")),
    }


def set_cfg(nome: str, dias: int):
    with get_conn() as conn:
        conn.execute("INSERT OR REPLACE INTO config VALUES ('nome_igreja', ?)", (nome,))
        conn.execute("INSERT OR REPLACE INTO config VALUES ('dias_emprestimo', ?)", (str(dias),))


def fmt(d) -> str:
    if not d:
        return "—"
    try:
        if isinstance(d, str):
            d = date.fromisoformat(d)
        return d.strftime("%d/%m/%Y")
    except Exception:
        return str(d)


def dias_restantes(due_str: str) -> int:
    try:
        return (date.fromisoformat(due_str) - date.today()).days
    except Exception:
        return 0


# ── Auth ─────────────────────────────────────────────────────────────

def hash_senha(senha: str) -> str:
    return _hash_senha(senha)


def verificar_senha(senha: str, armazenada: str) -> bool:
    try:
        salt_hex, dk_hex = armazenada.split(':')
        salt = bytes.fromhex(salt_hex)
        dk   = hashlib.pbkdf2_hmac('sha256', senha.encode('utf-8'), salt, 200_000)
        return dk.hex() == dk_hex
    except Exception:
        return False


def verificar_login(usuario: str, senha: str) -> bool:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT senha_hash FROM usuarios WHERE usuario = ?", (usuario,)
        ).fetchone()
    return bool(row) and verificar_senha(senha, row[0])


def q_usuarios():
    with get_conn() as conn:
        return conn.execute(
            "SELECT id, usuario, criado_em FROM usuarios ORDER BY usuario"
        ).fetchall()


def gerar_whats(phone: str, nome: str, livro: str, tipo: str,
                data_emp, data_dev, igreja: str) -> str:
    phone = "".join(filter(str.isdigit, str(phone)))
    if not phone.startswith("55"):
        phone = "55" + phone
    msgs = {
        "confirmacao": (
            f"Olá, {nome}! \n\n"
            f"Você retirou o livro *{livro}* da {igreja}.\n\n"
            f"► Retirada: {fmt(data_emp)}\n"
            f"► Devolução até: *{fmt(data_dev)}*\n\n"
            f"Boa leitura! Se precisar renovar, é só chamar. ♡"
        ),
        "lembrete": (
            f"Olá, {nome}! \n\n"
            f"O prazo para devolver o livro *{livro}* da {igreja} já passou "
            f"(venceu em {fmt(data_dev)}).\n\n"
            f"⚠ Por favor, devolva assim que possível para que outros irmãos possam ler. Obrigado! ♡"
        ),
        "aviso": (
            f"Olá, {nome}! \n\n"
            f"Passando para lembrar que o prazo de devolução do livro *{livro}* "
            f"da {igreja} é *{fmt(data_dev)}*.\n\n"
            f"Se precisar de mais tempo, podemos renovar! ♡"
        ),
        "renovacao": (
            f"Olá, {nome}! \n\n"
            f"Seu empréstimo do livro *{livro}* da {igreja} foi renovado!\n\n"
            f"► Nova data de devolução: *{fmt(data_dev)}*\n\n"
            f"Boa leitura! ♡"
        ),
        "disponivel": (
            f"Olá, {nome}! \n\n"
            f"Boas notícias! O livro *{livro}* da {igreja} foi devolvido "
            f"e você é o(a) próximo(a) da fila de espera.\n\n"
            f"Venha buscá-lo quando quiser! ♡"
        ),
        "devolucao": (
            f"Olá, {nome}! \n\n"
            f"Recebemos a devolução do livro *{livro}* da {igreja}. Muito obrigado!\n\n"
            f"Quando quiser pegar outro livro, é só chamar. ♡"
        ),
    }
    return f"https://wa.me/{phone}?text={urllib.parse.quote(msgs.get(tipo, ''))}"


def wa_button(label: str, url: str):
    """Renders a green WhatsApp branded link button."""
    st.markdown(
        f'<a href="{url}" target="_blank" rel="noopener noreferrer" class="wa">'
        f'💬 {label}</a>',
        unsafe_allow_html=True,
    )


def pill(label: str, kind: str = "blue") -> str:
    return f"<span class='sp sp-{kind}'>{label}</span>"


def loan_status(dl: int):
    if dl < 0:
        return "late", f"Atrasado {abs(dl)}d"
    if dl <= 5:
        return "warn", f"Vence em {dl}d"
    return "ok", f"{dl} dias"


def fmt_id(id_val: int) -> str:
    """Format an ID with minimum 2 digits, e.g. 01, 02, 33, 100."""
    return f"#{str(id_val).zfill(2)}"


# ── Queries ──────────────────────────────────────────────────────────

def q_livros():
    with get_conn() as c:
        return c.execute("SELECT * FROM livros ORDER BY titulo COLLATE NOCASE").fetchall()


def q_leitores():
    with get_conn() as c:
        return c.execute("SELECT * FROM leitores ORDER BY nome COLLATE NOCASE").fetchall()


def q_ativos():
    with get_conn() as c:
        return c.execute("""
            SELECT e.*, lt.nome AS leitor_nome, lt.telefone AS telefone, lv.titulo AS livro_titulo
            FROM   emprestimos e
            JOIN   leitores lt ON e.leitor_id = lt.id
            JOIN   livros   lv ON e.livro_id  = lv.id
            WHERE  e.status = 'ativo'
            ORDER  BY e.data_devolucao
        """).fetchall()


def q_historico(leitor=None, tipo=None):
    params, where = [], []
    if leitor:
        where.append("leitor_nome = ?"); params.append(leitor)
    if tipo:
        where.append("tipo = ?"); params.append(tipo)
    sql = ("SELECT * FROM historico"
           + (" WHERE " + " AND ".join(where) if where else "")
           + " ORDER BY id DESC")
    with get_conn() as c:
        return c.execute(sql, params).fetchall()


def q_fila(livro_id=None):
    with get_conn() as c:
        if livro_id is not None:
            return c.execute(
                """SELECT f.id, f.livro_id, f.leitor_id, f.data_inscricao, l.nome, l.telefone
                   FROM   fila_espera f JOIN leitores l ON f.leitor_id = l.id
                   WHERE  f.livro_id = ? ORDER BY f.data_inscricao""",
                (livro_id,),
            ).fetchall()
        return c.execute(
            """SELECT f.id, f.livro_id, f.leitor_id, f.data_inscricao,
                      l.nome, l.telefone, lv.titulo AS livro_titulo
               FROM   fila_espera f
               JOIN   leitores l  ON f.leitor_id = l.id
               JOIN   livros   lv ON f.livro_id  = lv.id
               ORDER  BY f.livro_id, f.data_inscricao"""
        ).fetchall()


# ══════════════════════════════════════════════════════════════════════
# SESSION STATE
# ══════════════════════════════════════════════════════════════════════
for _k in ("edit_livro", "edit_leitor", "edit_emp", "edit_usuario"):
    if _k not in st.session_state:
        st.session_state[_k] = None
if "devolveu_livro" not in st.session_state:
    st.session_state.devolveu_livro = None
if "wa_novo" not in st.session_state:
    st.session_state.wa_novo = None
if "wa_renovar" not in st.session_state:
    st.session_state.wa_renovar = None
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "usuario_atual" not in st.session_state:
    st.session_state.usuario_atual = ""

# ══════════════════════════════════════════════════════════════════════
# 🔐 LOGIN SCREEN
# ══════════════════════════════════════════════════════════════════════
if not st.session_state.logged_in:
    st.markdown(
        """
        <style>
        /* ── Login page layout ── */
        [data-testid="stAppViewContainer"] { background: #e8edf4 !important; }
        .main .block-container {
            max-width: 400px !important;
            padding: 48px 0 0 !important;
        }

        /* Header card (pure HTML, above the form) */
        .login-hdr {
            background: linear-gradient(135deg, #1e3a5f 0%, #2563eb 100%);
            border-radius: 20px 20px 0 0;
            padding: 40px 32px 32px;
            text-align: center;
        }
        .login-icon  { font-size: 3rem; line-height: 1; }
        .login-title { font-size: 1.55rem; font-weight: 900; color: white; margin-top: 12px; letter-spacing: -.02em; }
        .login-sub   { font-size: .86rem; color: rgba(255,255,255,.72); margin-top: 5px; }

        /* Form area — connects visually to the header card */
        [data-testid="stForm"] {
            background: white !important;
            border-radius: 0 0 20px 20px !important;
            border: none !important;
            box-shadow: 0 8px 32px rgba(0,0,0,.13) !important;
            padding: 28px 28px 32px !important;
            margin: 0 !important;
        }
        </style>
        <div class="login-hdr">
            <div class="login-icon">📚</div>
            <div class="login-title">Biblioteca ICR</div>
            <div class="login-sub">Sistema de Biblioteca</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    with st.form("form_login"):
        _usuario = st.text_input("Usuário", placeholder="seu usuário")
        _senha   = st.text_input("Senha", type="password", placeholder="••••••")
        _entrar  = st.form_submit_button("Entrar", type="primary", use_container_width=True)

    if _entrar:
        if verificar_login(_usuario.strip(), _senha):
            st.session_state.logged_in     = True
            st.session_state.usuario_atual = _usuario.strip()
            st.rerun()
        else:
            st.error("Usuário ou senha inválidos.")
    st.stop()


# ══════════════════════════════════════════════════════════════════════
# HEADER
# ══════════════════════════════════════════════════════════════════════
cfg = get_cfg()
st.markdown(
    f"""<div class="lib-header">
      <div class="lib-header-icon">📚</div>
      <div style="flex:1">
        <div class="lib-header-name">Biblioteca ICR</div>
        <div class="lib-header-sub">{cfg['nome_igreja']}</div>
      </div>
      <div style="font-size:.78rem;color:rgba(255,255,255,.72);text-align:right;line-height:1.4">
        👤 {st.session_state.usuario_atual}
      </div>
    </div>""",
    unsafe_allow_html=True,
)

if st.button("Sair", key="btn_logout", help="Encerrar sessão"):
    st.session_state.logged_in    = False
    st.session_state.usuario_atual = ""
    st.rerun()

tab_home, tab_emp, tab_livros, tab_leitores, tab_hist, tab_cfg = st.tabs([
    "🏠 Início", "📖 Empréstimo", "📚 Livros", "👥 Leitores", "🕐 Histórico", "⚙️ Config"
])


# ══════════════════════════════════════════════════════════════════════
# 🏠 INÍCIO
# ══════════════════════════════════════════════════════════════════════
with tab_home:
    ativos   = q_ativos()
    livros   = q_livros()
    leitores = q_leitores()
    ids_emp  = {e["livro_id"] for e in ativos}
    total_exemplares = sum((l["quantidade"] or 1) for l in livros)
    n_disp   = total_exemplares - len(ativos)

    # ── Metrics 2×2 ──────────────────────────────────────────────────
    st.markdown(
        f"""<div class="mg">
          <div class="mc">
            <div class="v" style="color:#2563eb">{total_exemplares}</div>
            <div class="l">Total livros</div>
          </div>
          <div class="mc">
            <div class="v" style="color:#16a34a">{n_disp}</div>
            <div class="l">Disponíveis</div>
          </div>
          <div class="mc">
            <div class="v" style="color:#dc2626">{len(ativos)}</div>
            <div class="l">Emprestados</div>
          </div>
          <div class="mc">
            <div class="v" style="color:#6b7280">{len(leitores)}</div>
            <div class="l">Leitores</div>
          </div>
        </div>""",
        unsafe_allow_html=True,
    )

    # ── Alertas ───────────────────────────────────────────────────────
    atrasados = [e for e in ativos if dias_restantes(e["data_devolucao"]) < 0]
    avisos    = [e for e in ativos if 0 <= dias_restantes(e["data_devolucao"]) <= 5]

    if not atrasados and not avisos:
        st.markdown(
            "<div class='al al-ok'>"
            "<div class='at'>Tudo em dia!</div>"
            "<div class='ab'>Nenhum empréstimo atrasado ou vencendo nos próximos 5 dias.</div>"
            "</div>",
            unsafe_allow_html=True,
        )

    if atrasados:
        st.markdown("<div class='sl'>Atrasados</div>", unsafe_allow_html=True)
        for e in atrasados:
            d = abs(dias_restantes(e["data_devolucao"]))
            st.markdown(
                f"<div class='al al-err'>"
                f"<div class='at'>{e['livro_titulo']}</div>"
                f"<div class='ab'>{e['leitor_nome']}<br>"
                f"Atrasado <strong>{d} dia(s)</strong> — venceu {fmt(e['data_devolucao'])}</div>"
                f"</div>",
                unsafe_allow_html=True,
            )
            url = gerar_whats(e["telefone"], e["leitor_nome"], e["livro_titulo"],
                              "lembrete", e["data_emprestimo"], e["data_devolucao"], cfg["nome_igreja"])
            wa_button(f"Lembrete para {e['leitor_nome']}", url)

    if avisos:
        st.markdown("<div class='sl'>Vencendo em breve</div>", unsafe_allow_html=True)
        for e in avisos:
            d = dias_restantes(e["data_devolucao"])
            st.markdown(
                f"<div class='al al-warn'>"
                f"<div class='at'>{e['livro_titulo']}</div>"
                f"<div class='ab'>{e['leitor_nome']}<br>"
                f"Vence em <strong>{d} dia(s)</strong> — {fmt(e['data_devolucao'])}</div>"
                f"</div>",
                unsafe_allow_html=True,
            )
            url = gerar_whats(e["telefone"], e["leitor_nome"], e["livro_titulo"],
                              "aviso", e["data_emprestimo"], e["data_devolucao"], cfg["nome_igreja"])
            wa_button(f"Avisar {e['leitor_nome']}", url)

    # ── Empréstimos ativos ────────────────────────────────────────────
    if ativos:
        st.markdown("<div class='sl'>Empréstimos ativos</div>", unsafe_allow_html=True)
        for e in ativos:
            dl        = dias_restantes(e["data_devolucao"])
            kind, lbl = loan_status(dl)
            with st.expander(f"{e['livro_titulo']}  ·  {e['leitor_nome']}"):
                st.markdown(
                    f"<div class='lc-hdr'>"
                    f"<div><div class='lc-book'>{e['livro_titulo']}</div>"
                    f"<div class='lc-who'>{e['leitor_nome']}</div></div>"
                    f"{pill(lbl, kind)}"
                    f"</div>"
                    f"<div class='lc-date'>"
                    f"<span class='id-tag'>{fmt_id(e['id'])}</span>&nbsp;&nbsp;"
                    f"Retirada: <strong>{fmt(e['data_emprestimo'])}</strong>&nbsp;&nbsp;·&nbsp;&nbsp;"
                    f"Devolução: <strong>{fmt(e['data_devolucao'])}</strong>"
                    f"</div>",
                    unsafe_allow_html=True,
                )
                url = gerar_whats(e["telefone"], e["leitor_nome"], e["livro_titulo"],
                                  "confirmacao", e["data_emprestimo"], e["data_devolucao"], cfg["nome_igreja"])
                wa_button("Enviar confirmação", url)
    else:
        st.markdown(
            "<div class='al al-ok'><div class='ab'>Nenhum empréstimo ativo no momento.</div></div>",
            unsafe_allow_html=True,
        )


# ══════════════════════════════════════════════════════════════════════
# 📖 EMPRÉSTIMO
# ══════════════════════════════════════════════════════════════════════
with tab_emp:
    sub_novo, sub_renovar, sub_devolver, sub_editar = st.tabs([
        "➕ Novo", "🔄 Renovar", "✅ Devolver", "✏️ Editar"
    ])

    # ── NOVO ─────────────────────────────────────────────────────────
    with sub_novo:
        if st.session_state.wa_novo:
            wa_button(st.session_state.wa_novo["label"], st.session_state.wa_novo["url"])
            if st.button("Fechar aviso", key="fechar_wa_novo", use_container_width=True):
                st.session_state.wa_novo = None
                st.rerun()
            st.divider()

        cfg      = get_cfg()
        leitores = q_leitores()
        livros   = q_livros()
        ativos   = q_ativos()
        _loans_count = {}
        for _e in ativos:
            _loans_count[_e["livro_id"]] = _loans_count.get(_e["livro_id"], 0) + 1
        disponiveis = [l for l in livros if _loans_count.get(l["id"], 0) < (l["quantidade"] or 1)]

        if not leitores:
            st.warning("Cadastre um leitor na aba Leitores primeiro.")
        elif not disponiveis:
            st.warning("Todos os livros estão emprestados no momento.")
        else:
            leitor_map = {f"{l['nome']}": l for l in leitores}
            livro_map  = {f"{b['titulo']}" + (f" — {b['autor']}" if b["autor"] else ""): b
                          for b in disponiveis}

            sel_leitor = st.selectbox("Leitor", list(leitor_map.keys()))
            sel_livro  = st.selectbox("Livro disponível", list(livro_map.keys()))
            data_emp   = st.date_input("Data do empréstimo", value=date.today())
            leitor     = leitor_map[sel_leitor]
            livro      = livro_map[sel_livro]
            data_dev   = data_emp + timedelta(days=cfg["dias"])

            st.markdown(
                f"<div class='al al-ok'><div class='ab'>"
                f"Devolução prevista: <strong>{fmt(data_dev)}</strong> ({cfg['dias']} dias)"
                f"</div></div>",
                unsafe_allow_html=True,
            )

            if st.button("Registrar empréstimo", type="primary", use_container_width=True):
                with get_conn() as conn:
                    conn.execute(
                        "INSERT INTO emprestimos (leitor_id, livro_id, data_emprestimo, data_devolucao) VALUES (?,?,?,?)",
                        (leitor["id"], livro["id"], data_emp.isoformat(), data_dev.isoformat()),
                    )
                    conn.execute(
                        "INSERT INTO historico (tipo, leitor_nome, livro_titulo, data, obs) VALUES (?,?,?,?,?)",
                        ("emprestimo", leitor["nome"], livro["titulo"], data_emp.isoformat(),
                         f"{leitor['nome']} retirou \"{livro['titulo']}\""),
                    )
                st.toast("Empréstimo registrado!")
                st.session_state.wa_novo = {
                    "label": f"Enviar confirmação para {leitor['nome']}",
                    "url": gerar_whats(leitor["telefone"], leitor["nome"], livro["titulo"],
                                       "confirmacao", data_emp, data_dev, cfg["nome_igreja"]),
                }
                st.rerun()

    # ── RENOVAR ──────────────────────────────────────────────────────
    with sub_renovar:
        if st.session_state.wa_renovar:
            wa_button(st.session_state.wa_renovar["label"], st.session_state.wa_renovar["url"])
            if st.button("Fechar aviso", key="fechar_wa_renovar", use_container_width=True):
                st.session_state.wa_renovar = None
                st.rerun()
            st.divider()

        cfg     = get_cfg()
        ativos  = q_ativos()
        MAX_REN = 3

        if not ativos:
            st.info("Nenhum empréstimo ativo para renovar.")
        else:
            for e in ativos:
                dl        = dias_restantes(e["data_devolucao"])
                kind, lbl = loan_status(dl)
                fila      = q_fila(e["livro_id"])
                rens      = e["renovacoes"]

                st.markdown(
                    f"<div class='lc'>"
                    f"<div class='lc-hdr'>"
                    f"<div><div class='lc-book'>{e['livro_titulo']}</div>"
                    f"<div class='lc-who'>{e['leitor_nome']}</div></div>"
                    f"{pill(lbl, kind)}"
                    f"</div>"
                    f"<div class='lc-date'><span class='id-tag'>{fmt_id(e['id'])}</span>&nbsp;&nbsp;Devolução: {fmt(e['data_devolucao'])}</div>"
                    f"<div class='lc-rens'>Renovações usadas: <strong>{rens}/{MAX_REN}</strong>"
                    + (' &nbsp;·&nbsp; <span style="color:#d97706">⏳ ' + str(len(fila)) + ' na fila</span>' if fila else '')
                    + "</div>"
                    f"</div>",
                    unsafe_allow_html=True,
                )

                if rens >= MAX_REN:
                    st.error(f"Limite de {MAX_REN} renovações atingido. O livro deve ser devolvido.")
                elif fila:
                    prox = fila[0]
                    st.warning(
                        f"Renovação bloqueada — há leitores aguardando.  \n"
                        f"Próximo(a): **{prox['nome']}** · {prox['telefone']}"
                    )
                else:
                    if st.button("Renovar empréstimo", key=f"ren_{e['id']}", use_container_width=True):
                        nova = (date.fromisoformat(e["data_devolucao"]) + timedelta(days=cfg["dias"])).isoformat()
                        with get_conn() as conn:
                            conn.execute(
                                "UPDATE emprestimos SET data_devolucao=?, renovacoes=renovacoes+1 WHERE id=?",
                                (nova, e["id"]),
                            )
                            conn.execute(
                                "INSERT INTO historico (tipo, leitor_nome, livro_titulo, data, obs) VALUES (?,?,?,?,?)",
                                ("renovacao", e["leitor_nome"], e["livro_titulo"], date.today().isoformat(),
                                 f"{e['leitor_nome']} renovou \"{e['livro_titulo']}\" até {fmt(nova)}"),
                            )
                        st.toast(f"Renovado até {fmt(nova)}!")
                        st.session_state.wa_renovar = {
                            "label": f"Avisar renovação para {e['leitor_nome']}",
                            "url": gerar_whats(e["telefone"], e["leitor_nome"], e["livro_titulo"],
                                               "renovacao", e["data_emprestimo"], nova, cfg["nome_igreja"]),
                        }
                        st.rerun()

    # ── DEVOLVER ─────────────────────────────────────────────────────
    with sub_devolver:
        if st.session_state.devolveu_livro:
            info     = st.session_state.devolveu_livro
            fila_pos = info.get("fila", [])
            _cfg_d   = get_cfg()
            st.success(f"**{info['titulo']}** foi devolvido!")
            _url_dev = gerar_whats(info["telefone"], info["leitor_nome"], info["titulo"],
                                   "devolucao", info["data_emp"], date.today(), _cfg_d["nome_igreja"])
            wa_button(f"Confirmar devolução para {info['leitor_nome']}", _url_dev)
            if fila_pos:
                prox = fila_pos[0]
                st.markdown(
                    f"<div class='al al-warn'>"
                    f"<div class='at'>{len(fila_pos)} leitor(es) aguardam este livro</div>"
                    f"<div class='ab'>Próximo(a): <strong>{prox['nome']}</strong> — {prox['telefone']}</div>"
                    f"</div>",
                    unsafe_allow_html=True,
                )
                _cfg_n = get_cfg()
                url_n  = gerar_whats(prox["telefone"], prox["nome"], info["titulo"],
                                     "disponivel", date.today(), date.today(), _cfg_n["nome_igreja"])
                wa_button(f"Avisar {prox['nome']} (próximo da fila)", url_n)
                if st.button("Confirmar aviso e remover da fila", use_container_width=True):
                    with get_conn() as conn:
                        conn.execute(
                            "DELETE FROM fila_espera WHERE livro_id=? AND leitor_id=?",
                            (info["livro_id"], prox["leitor_id"]),
                        )
                    st.session_state.devolveu_livro = None
                    st.rerun()
            if st.button("Fechar aviso", use_container_width=True):
                st.session_state.devolveu_livro = None
                st.rerun()
            st.divider()

        ativos = q_ativos()
        if not ativos:
            st.info("Nenhum empréstimo ativo para devolver.")
        else:
            for e in ativos:
                dl        = dias_restantes(e["data_devolucao"])
                kind, lbl = loan_status(dl)
                fila      = q_fila(e["livro_id"])
                fila_txt  = (f" &nbsp;·&nbsp; <span style='color:#d97706'>⏳ {len(fila)} na fila</span>"
                             if fila else "")

                st.markdown(
                    f"<div class='lc'>"
                    f"<div class='lc-hdr'>"
                    f"<div><div class='lc-book'>{e['livro_titulo']}</div>"
                    f"<div class='lc-who'>{e['leitor_nome']}</div></div>"
                    f"{pill(lbl, kind)}"
                    f"</div>"
                    f"<div class='lc-date'><span class='id-tag'>{fmt_id(e['id'])}</span>&nbsp;&nbsp;Prevista: {fmt(e['data_devolucao'])}{fila_txt}</div>"
                    f"</div>",
                    unsafe_allow_html=True,
                )
                if st.button("Registrar devolução", key=f"dev_{e['id']}", use_container_width=True):
                    fila_atual = q_fila(e["livro_id"])
                    with get_conn() as conn:
                        conn.execute("UPDATE emprestimos SET status='devolvido' WHERE id=?", (e["id"],))
                        conn.execute(
                            "INSERT INTO historico (tipo, leitor_nome, livro_titulo, data, obs) VALUES (?,?,?,?,?)",
                            ("devolucao", e["leitor_nome"], e["livro_titulo"], date.today().isoformat(),
                             f"{e['leitor_nome']} devolveu \"{e['livro_titulo']}\""),
                        )
                    st.session_state.devolveu_livro = {
                        "livro_id": e["livro_id"],
                        "titulo": e["livro_titulo"],
                        "leitor_nome": e["leitor_nome"],
                        "telefone": e["telefone"],
                        "data_emp": e["data_emprestimo"],
                        "fila": [dict(f) for f in fila_atual],
                    }
                    st.toast(f"\"{e['livro_titulo']}\" devolvido!")
                    st.rerun()

    # ── EDITAR ────────────────────────────────────────────────────────
    with sub_editar:
        ativos   = q_ativos()
        leitores = q_leitores()
        livros   = q_livros()
        cfg      = get_cfg()

        if not ativos:
            st.info("Nenhum empréstimo ativo para editar.")
        else:
            st.caption("Corrija datas, transfira para outro leitor ou cancele.")
            for e in ativos:
                dl        = dias_restantes(e["data_devolucao"])
                kind, lbl = loan_status(dl)
                editing   = st.session_state.edit_emp == e["id"]

                with st.container(border=True):
                    if editing:
                        st.markdown(
                            f"<span class='id-tag'>{fmt_id(e['id'])}</span> **Editando empréstimo de: {e['livro_titulo']}**",
                            unsafe_allow_html=True,
                        )
                        leitor_map = {l["nome"]: l for l in leitores}
                        nomes      = list(leitor_map.keys())
                        idx_l      = nomes.index(e["leitor_nome"]) if e["leitor_nome"] in nomes else 0
                        sel_l      = st.selectbox("Leitor", nomes, index=idx_l, key=f"ee_l_{e['id']}")

                        ids_outros  = {x["livro_id"] for x in ativos if x["id"] != e["id"]}
                        livros_disp = [b for b in livros if b["id"] not in ids_outros]
                        livro_map_e = {b["titulo"]: b for b in livros_disp}
                        titulos     = list(livro_map_e.keys())
                        idx_b       = titulos.index(e["livro_titulo"]) if e["livro_titulo"] in titulos else 0
                        sel_b       = st.selectbox("Livro", titulos, index=idx_b, key=f"ee_b_{e['id']}")

                        nd_emp = st.date_input("Data do empréstimo",
                                               value=date.fromisoformat(e["data_emprestimo"]),
                                               key=f"ee_de_{e['id']}")
                        nd_dev = st.date_input("Data de devolução",
                                               value=date.fromisoformat(e["data_devolucao"]),
                                               key=f"ee_dv_{e['id']}")

                        if st.button("Salvar alterações", key=f"sv_emp_{e['id']}", type="primary",
                                     use_container_width=True):
                            if nd_dev <= nd_emp:
                                st.toast("A data de devolução deve ser posterior ao empréstimo.", icon="❌")
                            else:
                                nl = leitor_map[sel_l]
                                nb = livro_map_e[sel_b]
                                with get_conn() as conn:
                                    conn.execute(
                                        "UPDATE emprestimos SET leitor_id=?, livro_id=?, data_emprestimo=?, data_devolucao=? WHERE id=?",
                                        (nl["id"], nb["id"], nd_emp.isoformat(), nd_dev.isoformat(), e["id"]),
                                    )
                                    conn.execute(
                                        "INSERT INTO historico (tipo, leitor_nome, livro_titulo, data, obs) VALUES (?,?,?,?,?)",
                                        ("edicao", nl["nome"], nb["titulo"], date.today().isoformat(),
                                         f"Empréstimo #{e['id']} editado manualmente."),
                                    )
                                st.session_state.edit_emp = None
                                st.toast("Empréstimo atualizado!")
                                st.rerun()

                        if st.button("Cancelar edição", key=f"cl_emp_{e['id']}", use_container_width=True):
                            st.session_state.edit_emp = None
                            st.rerun()

                        st.divider()
                        if st.button("Cancelar este empréstimo", key=f"del_emp_{e['id']}",
                                     use_container_width=True,
                                     help="O livro volta a ficar disponível"):
                            with get_conn() as conn:
                                conn.execute("UPDATE emprestimos SET status='cancelado' WHERE id=?", (e["id"],))
                                conn.execute(
                                    "INSERT INTO historico (tipo, leitor_nome, livro_titulo, data, obs) VALUES (?,?,?,?,?)",
                                    ("cancelamento", e["leitor_nome"], e["livro_titulo"],
                                     date.today().isoformat(),
                                     f"Empréstimo de \"{e['livro_titulo']}\" por {e['leitor_nome']} cancelado."),
                                )
                            st.session_state.edit_emp = None
                            st.toast("Empréstimo cancelado.")
                            st.rerun()
                    else:
                        st.markdown(
                            f"<div class='lc-hdr' style='padding:4px 0'>"
                            f"<div><div class='lc-book'>{e['livro_titulo']}</div>"
                            f"<div class='lc-who'>{e['leitor_nome']}</div>"
                            f"<div class='lc-rens' style='margin-top:6px'>"
                            f"<span class='id-tag'>{fmt_id(e['id'])}</span>&nbsp;&nbsp;"
                            f"{fmt(e['data_emprestimo'])} → {fmt(e['data_devolucao'])} "
                            f"&nbsp;·&nbsp; {e['renovacoes']} renovação(ões)</div>"
                            f"</div>"
                            f"{pill(lbl, kind)}"
                            f"</div>",
                            unsafe_allow_html=True,
                        )
                        if st.button("Editar", key=f"ed_emp_{e['id']}", use_container_width=True):
                            st.session_state.edit_emp = e["id"]
                            st.rerun()


# ══════════════════════════════════════════════════════════════════════
# 📚 LIVROS
# ══════════════════════════════════════════════════════════════════════
with tab_livros:
    with st.expander("Cadastrar novo livro", expanded=False):
        t = st.text_input("Título *", key="nb_titulo")
        a = st.text_input("Autor", key="nb_autor")
        k = st.text_input("Categoria", placeholder="Teologia, Devocional, Missões…", key="nb_cat")
        q = st.number_input("Quantidade de exemplares", min_value=1, value=1, step=1, key="nb_qtd")
        if st.button("Salvar livro", type="primary", key="btn_salvar_livro", use_container_width=True):
            if not t.strip():
                st.toast("O título é obrigatório.", icon="❌")
            else:
                with get_conn() as conn:
                    dup = conn.execute(
                        "SELECT id FROM livros WHERE titulo=? COLLATE NOCASE AND autor=? COLLATE NOCASE",
                        (t.strip(), a.strip()),
                    ).fetchone()
                if dup:
                    st.toast(f"Já existe um livro com o título \"{t.strip()}\" deste autor.", icon="❌")
                else:
                    with get_conn() as conn:
                        conn.execute("INSERT INTO livros (titulo, autor, categoria, quantidade) VALUES (?,?,?,?)",
                                     (t.strip(), a.strip(), k.strip(), int(q)))
                    st.toast(f"\"{t}\" cadastrado!")
                    st.rerun()

    busca    = st.text_input("Buscar livro", placeholder="Título, autor ou categoria…", key="busca_livro")
    livros   = q_livros()
    ativos   = q_ativos()
    loans_map: dict = {}
    for _e in ativos:
        loans_map.setdefault(_e["livro_id"], []).append(_e)
    _tf      = q_fila()
    fila_map: dict = {}
    for _f in _tf:
        fila_map.setdefault(_f["livro_id"], []).append(_f)
    leitores_all = q_leitores()

    if busca:
        q_low  = busca.lower()
        livros = [l for l in livros if q_low in l["titulo"].lower()
                  or q_low in (l["autor"] or "").lower()
                  or q_low in (l["categoria"] or "").lower()]

    def _disponiveis_livro(l):
        qty = l["quantidade"] if l["quantidade"] else 1
        return qty - len(loans_map.get(l["id"], []))

    emprestados = [l for l in livros if _disponiveis_livro(l) <= 0]
    disponiveis = [l for l in livros if _disponiveis_livro(l) > 0]

    st.markdown(
        f"<div style='display:flex;gap:8px;margin:14px 0 4px;'>"
        f"{pill(f'{len(disponiveis)} disponível(is)', 'ok')}"
        f"{pill(f'{len(emprestados)} emprestado(s)', 'late' if emprestados else 'gray')}"
        f"</div>",
        unsafe_allow_html=True,
    )

    def _livro_card(l):
        loans   = loans_map.get(l["id"], [])
        fila    = fila_map.get(l["id"], [])
        qty     = l["quantidade"] if l["quantidade"] else 1
        disp    = qty - len(loans)
        editing = st.session_state.edit_livro == l["id"]

        with st.container(border=True):
            if editing:
                st.markdown(
                    f"<span class='id-tag'>{fmt_id(l['id'])}</span> **Editando: {l['titulo']}**",
                    unsafe_allow_html=True,
                )
                nt = st.text_input("Título *",  value=l["titulo"],          key=f"et_{l['id']}")
                na = st.text_input("Autor",      value=l["autor"] or "",    key=f"ea_{l['id']}")
                nk = st.text_input("Categoria",  value=l["categoria"] or "", key=f"ek_{l['id']}")
                nq = st.number_input("Quantidade de exemplares", min_value=1, value=int(qty), step=1, key=f"eq_{l['id']}")
                if st.button("Salvar", key=f"sv_l_{l['id']}", type="primary", use_container_width=True):
                    if not nt.strip():
                        st.toast("O título é obrigatório.", icon="❌")
                    else:
                        with get_conn() as conn:
                            dup = conn.execute(
                                "SELECT id FROM livros WHERE titulo=? COLLATE NOCASE AND autor=? COLLATE NOCASE AND id!=?",
                                (nt.strip(), na.strip(), l["id"]),
                            ).fetchone()
                        if dup:
                            st.toast(f"Já existe outro livro com o título \"{nt.strip()}\" deste autor.", icon="❌")
                        else:
                            with get_conn() as conn:
                                conn.execute("UPDATE livros SET titulo=?, autor=?, categoria=?, quantidade=? WHERE id=?",
                                             (nt.strip(), na.strip(), nk.strip(), int(nq), l["id"]))
                            st.session_state.edit_livro = None
                            st.toast("Livro atualizado!")
                            st.rerun()
                if st.button("Cancelar", key=f"cl_l_{l['id']}", use_container_width=True):
                    st.session_state.edit_livro = None
                    st.rerun()
            else:
                emp_line = ""
                if loans:
                    fila_tag = (f"&nbsp;&nbsp;·&nbsp;&nbsp;<span style='color:#d97706'>⏳ {len(fila)} na fila</span>"
                                if fila else "")
                    nomes = ", ".join(f"<strong>{e['leitor_nome']}</strong>" for e in loans)
                    emp_line = (f"<div class='bc-info'>Com {nomes}{fila_tag}</div>")

                cat_html   = f"<div class='bc-cat'>{l['categoria']}</div>" if l["categoria"] else ""
                qty_html   = f"<div class='bc-cat'>{disp} de {qty} disponível(is)</div>"
                avail_pill = pill('Emprestado', 'late') if disp <= 0 else pill('Disponível', 'ok')

                st.markdown(
                    f"<div class='lc-hdr'>"
                    f"<div style='flex:1'>"
                    f"<div class='bc-title'><span class='id-tag'>{fmt_id(l['id'])}</span> {l['titulo']}</div>"
                    f"<div class='bc-author'>{l['autor'] or '—'}</div>"
                    f"{cat_html}"
                    f"{qty_html}"
                    f"{emp_line}"
                    f"</div>"
                    f"{avail_pill}"
                    f"</div>",
                    unsafe_allow_html=True,
                )

                ca, cb = st.columns(2)
                if ca.button("Editar", key=f"ed_livro_{l['id']}", use_container_width=True):
                    st.session_state.edit_livro = l["id"]
                    st.rerun()
                if disp > 0 and not loans:
                    if cb.button("Excluir", key=f"del_livro_{l['id']}", use_container_width=True):
                        with get_conn() as conn:
                            em_uso = conn.execute(
                                "SELECT COUNT(*) FROM emprestimos WHERE livro_id=?", (l["id"],)
                            ).fetchone()[0]
                        if em_uso:
                            st.toast("Não é possível excluir: livro possui histórico de empréstimos.", icon="⚠️")
                        else:
                            with get_conn() as conn:
                                conn.execute("DELETE FROM livros WHERE id=?", (l["id"],))
                            st.rerun()

                # Fila de espera (somente livros emprestados)
                if loans:
                    exp_label = (f"⏳ Fila de espera — {len(fila)} pessoa(s)"
                                 if fila else "Adicionar à fila de espera")
                    with st.expander(exp_label):
                        if fila:
                            for i, fi in enumerate(fila):
                                fc1, fc2 = st.columns([5, 1])
                                fc1.markdown(
                                    f"**{i+1}.** {fi['nome']} "
                                    f"<span style='font-size:.75rem;color:#6b7280'>desde {fmt(fi['data_inscricao'])}</span>",
                                    unsafe_allow_html=True,
                                )
                                if fc2.button("✕", key=f"rm_fila_{l['id']}_{fi['leitor_id']}",
                                              help="Remover da fila"):
                                    with get_conn() as conn:
                                        conn.execute(
                                            "DELETE FROM fila_espera WHERE livro_id=? AND leitor_id=?",
                                            (l["id"], fi["leitor_id"]),
                                        )
                                    st.rerun()
                            st.divider()

                        na_fila_ids = {fi["leitor_id"] for fi in fila}
                        candidatos  = [r for r in leitores_all
                                       if r["id"] not in na_fila_ids and r["id"] != e["leitor_id"]]
                        if candidatos:
                            nc       = {r["nome"]: r for r in candidatos}
                            sel_fila = st.selectbox("Adicionar à fila:",
                                                    ["— selecione —"] + list(nc.keys()),
                                                    key=f"sel_fila_{l['id']}")
                            if sel_fila != "— selecione —":
                                if st.button("Confirmar na fila", key=f"add_fila_{l['id']}",
                                             type="primary", use_container_width=True):
                                    novo = nc[sel_fila]
                                    with get_conn() as conn:
                                        conn.execute(
                                            "INSERT OR IGNORE INTO fila_espera (livro_id, leitor_id) VALUES (?,?)",
                                            (l["id"], novo["id"]),
                                        )
                                    st.toast(f"{novo['nome']} adicionado(a) à fila!")
                                    st.rerun()
                        else:
                            st.caption("Todos os leitores já estão na fila.")

    if emprestados:
        st.markdown("<div class='sl'>Emprestados</div>", unsafe_allow_html=True)
        for l in emprestados:
            _livro_card(l)
    if disponiveis:
        st.markdown("<div class='sl'>Disponíveis</div>", unsafe_allow_html=True)
        for l in disponiveis:
            _livro_card(l)
    if not livros:
        st.info("Nenhum livro encontrado." if busca else "Nenhum livro cadastrado ainda.")


# ══════════════════════════════════════════════════════════════════════
# 👥 LEITORES
# ══════════════════════════════════════════════════════════════════════
with tab_leitores:
    with st.expander("Cadastrar novo leitor", expanded=False):
        n   = st.text_input("Nome completo *", key="nl_nome")
        p   = st.text_input("WhatsApp * (com DDD, só números)", key="nl_tel")
        em  = st.text_input("E-mail", key="nl_email", placeholder="exemplo@email.com")
        end = st.text_input("Endereço", key="nl_end", placeholder="Rua, número, bairro — cidade/UF")
        if st.button("Salvar leitor", type="primary", key="btn_salvar_leitor", use_container_width=True):
            if not n.strip() or not p.strip():
                st.toast("Nome e telefone são obrigatórios.", icon="❌")
            else:
                digits = "".join(filter(str.isdigit, p))
                if len(digits) < 10:
                    st.toast("Telefone inválido. Informe DDD + número (mínimo 10 dígitos).", icon="❌")
                else:
                    erros = []
                    with get_conn() as conn:
                        if conn.execute(
                            "SELECT id FROM leitores WHERE telefone=?", (digits,)
                        ).fetchone():
                            erros.append(f"Telefone {digits} já está cadastrado para outro leitor.")
                        if em.strip() and conn.execute(
                            "SELECT id FROM leitores WHERE email=? COLLATE NOCASE AND email!=''",
                            (em.strip(),)
                        ).fetchone():
                            erros.append(f"E-mail já está cadastrado para outro leitor.")
                    if erros:
                        for msg in erros:
                            st.toast(msg, icon="❌")
                    else:
                        with get_conn() as conn:
                            conn.execute(
                                "INSERT INTO leitores (nome, telefone, email, endereco) VALUES (?,?,?,?)",
                                (n.strip(), digits, em.strip(), end.strip()),
                            )
                        st.toast(f"\"{n}\" cadastrado!")
                        st.rerun()

    busca_l  = st.text_input("Buscar leitor", placeholder="Nome, telefone, e-mail…", key="busca_leitor")
    leitores = q_leitores()
    ativos   = q_ativos()
    ativos_ids = {e["leitor_id"] for e in ativos}

    with get_conn() as conn:
        contagem = {r[0]: r[1] for r in conn.execute(
            "SELECT leitor_nome, COUNT(*) FROM historico WHERE tipo='emprestimo' GROUP BY leitor_nome"
        )}

    if busca_l:
        q_low    = busca_l.lower()
        leitores = [l for l in leitores
                    if q_low in l["nome"].lower()
                    or busca_l in l["telefone"]
                    or q_low in (l["email"] or "").lower()
                    or q_low in (l["endereco"] or "").lower()]

    if not leitores:
        st.info("Nenhum leitor encontrado." if busca_l else "Nenhum leitor cadastrado ainda.")

    for l in leitores:
        tem_livro = l["id"] in ativos_ids
        total     = contagem.get(l["nome"], 0)
        editing   = st.session_state.edit_leitor == l["id"]

        with st.container(border=True):
            if editing:
                st.markdown(
                    f"<span class='id-tag'>{fmt_id(l['id'])}</span> **Editando: {l['nome']}**",
                    unsafe_allow_html=True,
                )
                en   = st.text_input("Nome completo *", value=l["nome"],           key=f"eln_{l['id']}")
                ep   = st.text_input("WhatsApp *",       value=l["telefone"],       key=f"elp_{l['id']}")
                eem  = st.text_input("E-mail",            value=l["email"] or "",    key=f"elem_{l['id']}")
                eend = st.text_input("Endereço",          value=l["endereco"] or "", key=f"elend_{l['id']}")
                if st.button("Salvar", key=f"sv_r_{l['id']}", type="primary", use_container_width=True):
                    if not en.strip() or not ep.strip():
                        st.toast("Nome e telefone são obrigatórios.", icon="❌")
                    else:
                        digits = "".join(filter(str.isdigit, ep))
                        if len(digits) < 10:
                            st.toast("Telefone inválido.", icon="❌")
                        else:
                            erros = []
                            with get_conn() as conn:
                                if conn.execute(
                                    "SELECT id FROM leitores WHERE telefone=? AND id!=?",
                                    (digits, l["id"])
                                ).fetchone():
                                    erros.append(f"Telefone {digits} já está cadastrado para outro leitor.")
                                if eem.strip() and conn.execute(
                                    "SELECT id FROM leitores WHERE email=? COLLATE NOCASE AND id!=? AND email!=''",
                                    (eem.strip(), l["id"])
                                ).fetchone():
                                    erros.append("E-mail já está cadastrado para outro leitor.")
                            if erros:
                                for msg in erros:
                                    st.toast(msg, icon="❌")
                            else:
                                with get_conn() as conn:
                                    conn.execute(
                                        "UPDATE leitores SET nome=?, telefone=?, email=?, endereco=? WHERE id=?",
                                        (en.strip(), digits, eem.strip(), eend.strip(), l["id"]),
                                    )
                                st.session_state.edit_leitor = None
                                st.toast("Leitor atualizado!")
                                st.rerun()
                if st.button("Cancelar", key=f"cl_r_{l['id']}", use_container_width=True):
                    st.session_state.edit_leitor = None
                    st.rerun()
            else:
                # Card view
                status_pill = pill("Com livro", "warn") if tem_livro else pill("Livre", "ok")
                extra = ""
                if l["email"]:
                    extra += f"<div class='rc-extra'>{l['email']}</div>"
                if l["endereco"]:
                    extra += f"<div class='rc-extra'>{l['endereco']}</div>"

                st.markdown(
                    f"<div class='lc-hdr' style='padding:4px 0'>"
                    f"<div style='flex:1;min-width:0'>"
                    f"<div class='rc-name'><span class='id-tag'>{fmt_id(l['id'])}</span> {l['nome']}</div>"
                    f"<div class='rc-phone'>{l['telefone']}</div>"
                    f"{extra}"
                    f"<div class='rc-extra' style='margin-top:6px'>{total} empréstimo(s) registrado(s)</div>"
                    f"</div>"
                    f"{status_pill}"
                    f"</div>",
                    unsafe_allow_html=True,
                )

                ca, cb = st.columns(2)
                if ca.button("Editar", key=f"ed_leitor_{l['id']}", use_container_width=True):
                    st.session_state.edit_leitor = l["id"]
                    st.rerun()
                if not tem_livro:
                    if cb.button("Excluir", key=f"del_leitor_{l['id']}", use_container_width=True):
                        with get_conn() as conn:
                            em_uso = conn.execute(
                                "SELECT COUNT(*) FROM historico WHERE leitor_nome=?", (l["nome"],)
                            ).fetchone()[0]
                        if em_uso:
                            st.toast(f"{l['nome']} possui histórico e não pode ser excluído.", icon="⚠️")
                        else:
                            with get_conn() as conn:
                                conn.execute("DELETE FROM leitores WHERE id=?", (l["id"],))
                            st.rerun()


# ══════════════════════════════════════════════════════════════════════
# 🕐 HISTÓRICO
# ══════════════════════════════════════════════════════════════════════
with tab_hist:
    leitores = q_leitores()
    f_leitor = st.selectbox("Filtrar por leitor",
                            ["Todos"] + [l["nome"] for l in leitores], key="hf_leitor")
    f_tipo   = st.selectbox(
        "Filtrar por tipo",
        ["Todos", "emprestimo", "renovacao", "devolucao", "edicao", "cancelamento"],
        format_func=lambda x: {
            "Todos": "Todos os tipos",
            "emprestimo":   "Empréstimo",
            "renovacao":    "Renovação",
            "devolucao":    "Devolução",
            "edicao":       "Edição",
            "cancelamento": "Cancelamento",
        }.get(x, x),
        key="hf_tipo",
    )

    hist = q_historico(
        leitor=f_leitor if f_leitor != "Todos" else None,
        tipo=f_tipo     if f_tipo   != "Todos" else None,
    )

    HIST_TIPOS = {
        "emprestimo":   ("#1d4ed8", "#dbeafe", "Empréstimo"),
        "renovacao":    ("#92400e", "#fef3c7", "Renovação"),
        "devolucao":    ("#14532d", "#dcfce7", "Devolução"),
        "edicao":       ("#5b21b6", "#ede9fe", "Edição"),
        "cancelamento": ("#991b1b", "#fee2e2", "Cancelamento"),
    }

    if not hist:
        st.info("Nenhum registro encontrado.")
    else:
        for h in hist:
            cor, bg, tipo_label = HIST_TIPOS.get(h["tipo"], ("#374151", "#f3f4f6", h["tipo"]))
            st.markdown(
                f"<div class='hi' style='border-color:{cor};background:{bg};'>"
                f"<div class='hi-hdr'>"
                f"<span class='ht' style='color:{cor}'>{tipo_label}</span>"
                f"<span class='hd'>{fmt(h['data'])}</span>"
                f"</div>"
                f"<div class='ho'>{h['obs']}</div>"
                f"</div>",
                unsafe_allow_html=True,
            )


# ══════════════════════════════════════════════════════════════════════
# ⚙️ CONFIG
# ══════════════════════════════════════════════════════════════════════
with tab_cfg:
    cfg = get_cfg()
    st.markdown("<div class='sl'>Configurações gerais</div>", unsafe_allow_html=True)

    novo_nome  = st.text_input("Nome da Igreja", value=cfg["nome_igreja"])
    novos_dias = st.number_input(
        "Período de empréstimo (dias)", min_value=1, max_value=365, value=cfg["dias"]
    )
    if st.button("Salvar configurações", type="primary", use_container_width=True):
        set_cfg(novo_nome.strip() or "Igreja Cristã Reformada", int(novos_dias))
        st.toast("Configurações salvas!")
        st.rerun()

    st.divider()
    st.markdown("<div class='sl'>Exportar dados</div>", unsafe_allow_html=True)

    with get_conn() as conn:
        livros_rows = conn.execute(
            "SELECT titulo, autor, categoria, criado_em FROM livros ORDER BY titulo"
        ).fetchall()
        emp_rows = conn.execute("""
            SELECT lt.nome, lt.telefone, lv.titulo,
                   e.data_emprestimo, e.data_devolucao, e.status, e.renovacoes
            FROM   emprestimos e
            JOIN   leitores lt ON e.leitor_id = lt.id
            JOIN   livros   lv ON e.livro_id  = lv.id
            ORDER  BY e.data_emprestimo DESC
        """).fetchall()

    buf1 = io.StringIO()
    w1   = csv.writer(buf1)
    w1.writerow(["Título", "Autor", "Categoria", "Cadastrado em"])
    for r in livros_rows:
        w1.writerow(list(r))

    buf2 = io.StringIO()
    w2   = csv.writer(buf2)
    w2.writerow(["Leitor", "Telefone", "Livro", "Empréstimo", "Devolução", "Status", "Renovações"])
    for r in emp_rows:
        w2.writerow(list(r))

    st.download_button("Exportar livros (CSV)", buf1.getvalue(), "livros.csv", "text/csv",
                       use_container_width=True)
    st.download_button("Exportar empréstimos (CSV)", buf2.getvalue(), "emprestimos.csv", "text/csv",
                       use_container_width=True)

    # ── Gerenciar usuários ────────────────────────────────────────────
    st.divider()
    st.markdown("<div class='sl'>Usuários do sistema</div>", unsafe_allow_html=True)

    # Formulário de novo usuário — expander igual ao de leitores/livros
    with st.expander("Criar novo usuário", expanded=False):
        nu_login = st.text_input("Usuário *", placeholder="nome de acesso", key="nu_login")
        nu_senha = st.text_input("Senha *", type="password", key="nu_senha")
        nu_conf  = st.text_input("Confirmar senha *", type="password", key="nu_conf")
        if st.button("Salvar usuário", key="sv_nu", type="primary", use_container_width=True):
            if not nu_login.strip() or not nu_senha:
                st.toast("Preencha usuário e senha.", icon="❌")
            elif nu_senha != nu_conf:
                st.toast("As senhas não coincidem.", icon="❌")
            elif len(nu_senha) < 4:
                st.toast("Mínimo 4 caracteres na senha.", icon="❌")
            else:
                try:
                    with get_conn() as conn:
                        conn.execute(
                            "INSERT INTO usuarios (usuario, senha_hash) VALUES (?,?)",
                            (nu_login.strip(), hash_senha(nu_senha)),
                        )
                    st.session_state.edit_usuario = None
                    st.toast(f"Usuário '{nu_login.strip()}' criado!", icon="✅")
                    st.rerun()
                except sqlite3.IntegrityError:
                    st.toast(f"Usuário '{nu_login.strip()}' já existe.", icon="❌")

    usuarios_list = q_usuarios()
    for u in usuarios_list:
        eh_eu        = u["usuario"] == st.session_state.usuario_atual
        eh_admin_row = u["usuario"] == "admin"
        logado_admin = st.session_state.usuario_atual == "admin"
        pode_editar  = eh_eu or logado_admin
        pode_excluir = logado_admin and not eh_admin_row
        editando     = st.session_state.edit_usuario == u["id"]

        # Security guard: prevent session-state abuse
        if editando and not pode_editar:
            st.session_state.edit_usuario = None
            st.rerun()

        with st.container(border=True):
            if editando:
                # ─ Editar senha (inline) ─
                st.markdown(
                    f"<span class='id-tag'>{fmt_id(u['id'])}</span> **Alterar senha — {u['usuario']}**",
                    unsafe_allow_html=True,
                )
                # Próprio usuário deve confirmar senha atual; admin alterando outra conta não precisa
                ms_atual = ""
                if eh_eu:
                    ms_atual = st.text_input("Senha atual", type="password", key=f"ms_a_{u['id']}")
                elif logado_admin:
                    st.caption("Você está redefinindo a senha de outro usuário (admin).")
                ms_nova  = st.text_input("Nova senha",  type="password", key=f"ms_n_{u['id']}")
                ms_conf  = st.text_input("Confirmar",   type="password", key=f"ms_c_{u['id']}")
                _ea, _eb = st.columns(2)
                if _ea.button("Salvar", key=f"sv_u_{u['id']}", type="primary", use_container_width=True):
                    if eh_eu and not verificar_login(u["usuario"], ms_atual):
                        st.toast("Senha atual incorreta.", icon="❌")
                    elif ms_nova != ms_conf:
                        st.toast("As senhas não coincidem.", icon="❌")
                    elif len(ms_nova) < 4:
                        st.toast("Mínimo 4 caracteres.", icon="❌")
                    else:
                        with get_conn() as conn:
                            conn.execute(
                                "UPDATE usuarios SET senha_hash=? WHERE id=?",
                                (hash_senha(ms_nova), u["id"]),
                            )
                        st.session_state.edit_usuario = None
                        st.toast("Senha alterada!")
                        st.rerun()
                if _eb.button("Cancelar", key=f"cl_u_{u['id']}", use_container_width=True):
                    st.session_state.edit_usuario = None
                    st.rerun()
            else:
                # ─ Linha do usuário ─
                _la, _lb, _lc = st.columns([5, 1, 1])
                _la.markdown(
                    f"<span class='id-tag'>{fmt_id(u['id'])}</span> **{u['usuario']}** "
                    + ("<span style='font-size:.7rem;background:#dbeafe;color:#1e40af;padding:2px 8px;border-radius:99px;font-weight:700'>você</span> " if eh_eu else "")
                    + ("<span style='font-size:.7rem;background:#fef3c7;color:#92400e;padding:2px 8px;border-radius:99px;font-weight:700'>admin</span> " if eh_admin_row else "")
                    + f"<span style='font-size:.75rem;color:#6b7280'>desde {fmt(u['criado_em'])}</span>",
                    unsafe_allow_html=True,
                )
                if pode_editar:
                    if _lb.button("✏️", key=f"ed_usr_{u['id']}", help="Alterar senha"):
                        st.session_state.edit_usuario = u["id"]
                        st.rerun()
                else:
                    _lb.markdown("&nbsp;", unsafe_allow_html=True)
                if pode_excluir:
                    if _lc.button("❌", key=f"del_usr_{u['id']}", help="Remover usuário"):
                        with get_conn() as conn:
                            conn.execute("DELETE FROM usuarios WHERE id=?", (u["id"],))
                        st.rerun()
                else:
                    _lc.markdown("&nbsp;", unsafe_allow_html=True)

    st.markdown("<div style='height:48px'></div>", unsafe_allow_html=True)
