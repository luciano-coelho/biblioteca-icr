# Biblioteca ICR

Sistema de gerenciamento de biblioteca para a **Igreja Cristã Reformada**.  
Controla empréstimos, devolucões, renovações e fila de espera, com notificações automáticas via **WhatsApp**.

---

## Funcionalidades

- **Empréstimos** — registrar, renovar (até 3x), devolver e cancelar
- **Leitores** — cadastro completo com telefone WhatsApp
- **Livros** — acervo com suporte a múltiplos exemplares
- **Fila de espera** — notificação automática ao próximo da fila quando o livro é devolvido
- **Histórico** — registro auditável de todas as operações com filtros e exportação CSV
- **Mensagens WhatsApp** — caixa de entrada, envio em massa e envio individual
- **Scheduler** — lembretes diários automáticos (atrasos e vencimentos próximos)
- **Dashboard** — indicadores em tempo real com alertas visuais
- **Configurações** — prazo padrão, nome da instituição, gerenciamento de usuários

### Regras de negócio

- Máximo de 3 empréstimos ativos por leitor
- Mesmo livro não pode ser emprestado duas vezes ao mesmo leitor simultaneamente
- Renovação bloqueada se houver fila de espera para o livro
- Exclusão de leitor ou livro bloqueada se houver empréstimos vinculados

---

## Stack

| Componente | Tecnologia |
|---|---|
| Interface | Python 3.13 · Streamlit |
| Banco de dados | SQLite |
| WhatsApp | Evolution API v2.2.3 |
| Testes | pytest (224 testes) |
| Infraestrutura | Docker Compose (Evolution API + PostgreSQL + Redis) |

---

## Pré-requisitos

- Python 3.11+
- Node.js 18+ (apenas para Evolution API sem Docker)
- Docker e Docker Compose (recomendado para Evolution API)

---

## Instalação

### 1. Clonar o repositório

```bash
git clone https://github.com/luciano-coelho/biblioteca-icr.git
cd biblioteca-icr
```

### 2. Instalar dependências Python

```bash
pip install -r requirements.txt
```

### 3. Subir a Evolution API (WhatsApp)

```bash
docker compose up -d
```

Isso sobe três containers:
- `biblio-evolution` — Evolution API na porta **8080**
- `biblio-postgres` — PostgreSQL na porta **5433**
- `biblio-redis` — Redis na porta **6380**

### 4. Conectar o WhatsApp

Acesse `http://localhost:8080` e conecte a instância `biblioteca` via QR Code ou Pairing Code.

### 5. Iniciar o app

```bash
python -m streamlit run app/app.py --server.port 8503
```

Acesse em: **http://localhost:8503**

Credenciais padrão: `admin` / `admin` (trocar após o primeiro login em Configurações).

### 6. Iniciar o scheduler de lembretes (opcional)

```bash
python -m app.scheduler
```

Para executar imediatamente (útil para testes):

```bash
python -m app.scheduler --agora
```

---

## Estrutura do projeto

```
biblioteca-icr/
├── app/
│   ├── app.py           # Aplicação principal Streamlit
│   └── scheduler.py     # Serviço de lembretes automáticos
├── tests/
│   └── test_app.py      # Suite de testes (224 testes)
├── biblioteca.db        # Banco SQLite (gerado automaticamente)
├── docker-compose.yml   # Evolution API + PostgreSQL + Redis
├── requirements.txt
├── CHANGELOG.md
└── README.md
```

---

## Configuração

### Evolution API

As configurações de conexão ficam no topo de `app/app.py`:

```python
EVO_URL      = "http://localhost:8080"
EVO_KEY      = "biblio-icr-key"
EVO_INSTANCE = "biblioteca"
```

### Scheduler

Horário de disparo configurável em `app/scheduler.py`:

```python
HORA_DISPARO   = 19   # hora (formato 24h)
MINUTO_DISPARO = 0    # minuto — padrão produção
BATCH_SIZE     = 5    # máx. mensagens por hora
DIAS_AVISO     = 5    # dias antes do vencimento para enviar lembrete
```

---

## Testes

```bash
pytest tests/test_app.py -v
```

224 testes cobrindo: regras de empréstimo, devolução, renovação, fila de espera, validações de formulário, exportação CSV, normalização de telefone, restrições de admin e comportamento do session state.

---

## Segurança

- Senhas armazenadas com **PBKDF2-SHA256** (200.000 iterações) + salt aleatório
- Acesso administrativo restrito por role
- Proteção contra exclusão de registros com dependências
- Migrações de banco executadas automaticamente na inicialização

---

## Licença

Uso interno — Igreja Cristã Reformada.
