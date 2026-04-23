#!/usr/bin/env python3
"""
scheduler.py — Envio automático de lembretes WhatsApp às 19h

Regras de envio em massa:
  · Máx 5 mensagens por hora (lotes de 5)
  · 60–1200 s aleatórios entre mensagens do mesmo lote
  · 3600 s (1 hora) de pausa entre lotes
  · Somente leitores atrasados (lembrete) ou vencendo em até 5 dias (aviso)
  · Confirmação NÃO é enviada por este serviço

Uso:
  python scheduler.py              # fica rodando, dispara às 19h todo dia
  python scheduler.py --agora      # executa imediatamente e encerra
"""

import os
import sys
import time
import math
import random
import sqlite3
import logging
from datetime import date, datetime

import requests

# ── Configuração ──────────────────────────────────────────────────────
_DIR = os.path.dirname(os.path.abspath(__file__))
DB   = os.path.normpath(os.path.join(_DIR, "..", "biblioteca.db"))

EVO_URL      = "http://localhost:8080"
EVO_KEY      = "biblio-icr-key"
EVO_INSTANCE = "biblioteca"
EVO_HEADERS  = {"apikey": EVO_KEY, "Content-Type": "application/json"}

HORA_DISPARO   = 19    # 19:hh
MINUTO_DISPARO = 45    # :45 — temporário para validação (voltar para 0)
BATCH_SIZE    = 5      # máx. mensagens por hora
INTER_MSG_MIN = 60     # 1 min — delay mínimo entre msgs do mesmo lote
INTER_MSG_MAX = 1200   # 20 min — delay máximo entre msgs do mesmo lote
INTER_BATCH   = 3600   # 1 hora — pausa entre lotes
DIAS_AVISO    = 5      # notifica quem vence em até X dias

# ── Logging ───────────────────────────────────────────────────────────
_LOG_DIR = os.path.normpath(os.path.join(_DIR, "..", "logs"))
os.makedirs(_LOG_DIR, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(
            os.path.join(_LOG_DIR, "scheduler.log"), encoding="utf-8"
        ),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger(__name__)


# ── DB ────────────────────────────────────────────────────────────────
def get_conn():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn


def get_cfg() -> dict:
    with get_conn() as conn:
        rows = conn.execute("SELECT chave, valor FROM config").fetchall()
    d = {r["chave"]: r["valor"] for r in rows}
    return {"nome_igreja": d.get("nome_igreja", "Igreja Cristã Reformada")}


# ── Helpers ───────────────────────────────────────────────────────────
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


def gerar_texto(nome: str, livro: str, tipo: str,
                data_emp: str, data_dev: str, igreja: str) -> str:
    msgs = {
        "lembrete": (
            f"Olá, {nome}! \n\n"
            f"O prazo para devolver o livro *{livro}* da {igreja} já passou "
            f"(venceu em {fmt(data_dev)}).\n\n"
            f"⚠ Por favor, devolva assim que possível para que outros irmãos "
            f"possam ler. Obrigado! ♡"
        ),
        "aviso": (
            f"Olá, {nome}! \n\n"
            f"Passando para lembrar que o prazo de devolução do livro *{livro}* "
            f"da {igreja} é *{fmt(data_dev)}*.\n\n"
            f"Se precisar de mais tempo, podemos renovar! ♡"
        ),
    }
    return msgs.get(tipo, "")


# ── Evolution API ─────────────────────────────────────────────────────
def evo_is_connected() -> bool:
    try:
        r = requests.get(
            f"{EVO_URL}/instance/connectionState/{EVO_INSTANCE}",
            headers=EVO_HEADERS,
            timeout=5,
        )
        if r.status_code == 200:
            data = r.json()
            state = (
                data.get("state")
                or (data.get("instance") or {}).get("state")
                or "close"
            )
            return state == "open"
    except Exception:
        pass
    return False


def evo_send(phone: str, text: str) -> bool:
    digits = "".join(filter(str.isdigit, str(phone)))
    if not digits.startswith("55"):
        digits = "55" + digits
    try:
        r = requests.post(
            f"{EVO_URL}/message/sendText/{EVO_INSTANCE}",
            headers=EVO_HEADERS,
            json={"number": digits, "text": text},
            timeout=10,
        )
        return r.status_code in (200, 201)
    except Exception:
        return False


# ── Lógica de disparo ─────────────────────────────────────────────────
def buscar_destinatarios(cfg: dict) -> list:
    """Consulta empréstimos ativos e retorna quem deve receber mensagem hoje."""
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT lt.nome, lt.telefone, lv.titulo,
                   e.data_emprestimo, e.data_devolucao
            FROM   emprestimos e
            JOIN   leitores lt ON e.leitor_id = lt.id
            JOIN   livros   lv ON e.livro_id  = lv.id
            WHERE  e.status = 'ativo'
            ORDER  BY e.data_devolucao
        """).fetchall()

    destinos = []
    for r in rows:
        dl = dias_restantes(r["data_devolucao"])
        if dl < 0:
            tipo = "lembrete"        # atrasado
        elif dl <= DIAS_AVISO:
            tipo = "aviso"           # vencendo em breve
        else:
            continue                 # em dia — não notifica
        destinos.append({
            "nome":            r["nome"],
            "telefone":        r["telefone"],
            "titulo":          r["titulo"],
            "tipo":            tipo,
            "data_emprestimo": r["data_emprestimo"],
            "data_devolucao":  r["data_devolucao"],
        })
    return destinos


def montar_fila(destinos: list) -> list:
    """Distribui destinatários em lotes de BATCH_SIZE com delays calculados."""
    total_lotes = math.ceil(len(destinos) / BATCH_SIZE)
    fila = []
    for i, d in enumerate(destinos):
        pos_in_lote = i % BATCH_SIZE
        lote_num    = i // BATCH_SIZE
        if i == 0:
            delay = 0
        elif pos_in_lote == 0:
            delay = INTER_BATCH                          # início de novo lote → 1h
        else:
            delay = random.randint(INTER_MSG_MIN, INTER_MSG_MAX)  # dentro do lote
        fila.append({
            **d,
            "delay":       delay,
            "lote":        lote_num + 1,
            "total_lotes": total_lotes,
        })
    return fila


def executar_fila(fila: list, cfg: dict) -> dict:
    """Percorre a fila, aguarda os delays e dispara cada mensagem."""
    total  = len(fila)
    sent   = 0
    failed = []

    for i, item in enumerate(fila):
        if item["delay"] > 0:
            if item["delay"] >= INTER_BATCH:
                log.info(
                    "⏳ Lote %d/%d concluído — aguardando %d min para o próximo lote...",
                    item["lote"] - 1, item["total_lotes"], item["delay"] // 60,
                )
            else:
                log.info(
                    "  ⏱  Aguardando %ds antes da próxima mensagem...", item["delay"]
                )
            time.sleep(item["delay"])

        txt = gerar_texto(
            item["nome"], item["titulo"], item["tipo"],
            item["data_emprestimo"], item["data_devolucao"],
            cfg["nome_igreja"],
        )
        ok = evo_send(item["telefone"], txt)

        if ok:
            sent += 1
            log.info(
                "  ✅ [%d/%d] Lote %d — %s (%s)",
                i + 1, total, item["lote"], item["nome"], item["tipo"],
            )
        else:
            failed.append(item["nome"])
            log.warning(
                "  ❌ [%d/%d] %s — falha no envio", i + 1, total, item["nome"]
            )

    return {"sent": sent, "failed": failed, "total": total}


def job_envio_diario():
    log.info("═" * 60)
    log.info("🚀 Iniciando envio automático diário")

    if not evo_is_connected():
        log.warning("⚠️  WhatsApp desconectado — envio cancelado")
        return

    cfg      = get_cfg()
    destinos = buscar_destinatarios(cfg)

    if not destinos:
        log.info("✅ Nenhum leitor em atraso ou com vencimento próximo hoje.")
        log.info("═" * 60)
        return

    atrasados = [d for d in destinos if d["tipo"] == "lembrete"]
    vencendo  = [d for d in destinos if d["tipo"] == "aviso"]
    log.info(
        "📋 %d destinatário(s): %d atrasado(s), %d vencendo em até %d dias",
        len(destinos), len(atrasados), len(vencendo), DIAS_AVISO,
    )
    total_lotes = math.ceil(len(destinos) / BATCH_SIZE)
    log.info("📦 %d lote(s) de até %d mensagens", total_lotes, BATCH_SIZE)

    fila  = montar_fila(destinos)
    stats = executar_fila(fila, cfg)

    log.info("🏁 Concluído: %d/%d enviados", stats["sent"], stats["total"])
    if stats["failed"]:
        log.warning("  Falhas: %s", ", ".join(stats["failed"]))
    log.info("═" * 60)


# ── Ponto de entrada ──────────────────────────────────────────────────
if __name__ == "__main__":
    # Disparo manual: python scheduler.py --agora
    if len(sys.argv) > 1 and sys.argv[1] == "--agora":
        log.info("▶️  Execução manual solicitada (--agora)")
        job_envio_diario()
        sys.exit(0)

    log.info("📅 Agendador iniciado — disparo diário às %02d:%02dh", HORA_DISPARO, MINUTO_DISPARO)
    ultimo_disparo: date | None = None

    while True:
        agora = datetime.now()
        hoje  = agora.date()

        if agora.hour == HORA_DISPARO and agora.minute == MINUTO_DISPARO and ultimo_disparo != hoje:
            ultimo_disparo = hoje
            job_envio_diario()

        time.sleep(30)  # verifica a cada 30 s
