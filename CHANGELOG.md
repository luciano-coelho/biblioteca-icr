# Biblioteca ICR — Changelog

Sistema de gerenciamento de biblioteca para a Igreja Cristã Reformada.
Stack: Python 3.13 · Streamlit · SQLite · Evolution API (WhatsApp) · pytest

---

## [Unreleased] — Sessão atual (23/04/2026)

### Correções de bugs

- **`StreamlitDuplicateElementKey`** — crash ao listar empréstimos de um leitor que possui 2 ou mais livros ativos.  
  Causa: `wa_button` gerava a chave via `hash(label + phone)`, colidente quando o telefone era o mesmo.  
  Solução: adicionado parâmetro `key` explícito à função; todos os pontos de chamada passam `key=f"wa_conf_{e['id']}"` ou similar, tornando as chaves únicas por ID de empréstimo.

- **`StreamlitAPIException` na caixa de entrada** — ao enviar uma resposta pelo módulo Mensagens, o campo de texto crashava ao tentar ser limpo após o `st.rerun()`.  
  Causa: `st.session_state[key] = ""` depois que o widget já havia sido instanciado no mesmo ciclo.  
  Solução: a limpeza foi movida para antes da criação do `text_area`, usando `pop` para remover a key do session state.

### Novas funcionalidades

- **Confirmação de envio com bloqueio de reenvio** — após enviar a mensagem de confirmação de empréstimo com sucesso, o botão WhatsApp é substituído por uma mensagem informativa:
  > ✅ Confirmação já enviada. Para reenviar, visite a edição do empréstimo.
  Evita o envio repetido por clique acidental. O estado `enviado` é armazenado em `session_state` e zerado ao fechar o aviso ou ao registrar um novo empréstimo.

### Melhorias de UX

- **Formato de datas em padrão brasileiro (DD/MM/YYYY)** — todos os campos `st.date_input` passaram a exibir e aceitar datas no formato `DD/MM/YYYY` via parâmetro `format=`.

- **Reset do formulário de empréstimo** — após registrar ou fechar o aviso, o formulário volta ao estado inicial (placeholders "— Selecionar leitor —" / "— Selecionar livro —") e o botão fica desabilitado até que ambos os campos sejam preenchidos.

- **Scheduler ajustado para testes** — horário de disparo configurável via `HORA_DISPARO` + `MINUTO_DISPARO` (atualmente 19h45 para validação; retornar para `:00` em produção).

### Qualidade de código

- **Suite de testes expandida: 135 → 224 testes** (+89), cobrindo:

  | Classe | Testes | O que valida |
  |---|---|---|
  | `TestWaButtonKeyUniqueness` | 11 | Unicidade de chaves — previne exatamente o bug DuplicateElementKey |
  | `TestFormValidation` | 9 | Lógica de placeholder e guarda de acesso ao mapa |
  | `TestSessionStateReset` | 6 | Reset do formulário após registro e fechar aviso |
  | `TestDevolucao` | 6 | Fluxo completo de devolução: status, histórico, fila |
  | `TestRenovacaoLimite` | 6 | Limite de 3 renovações e bloqueio por fila de espera |
  | `TestRegrasDeEmprestimo` | 7 | Regras de negócio: 3 livros/pessoa, duplicata, esgotamento |
  | `TestAdminRestrictions` | 12 | Acesso admin case-sensitive, UNIQUE constraint, configurações |
  | `TestCsvExport` | 5 | Colunas e dados em cada CSV exportado |
  | `TestPhoneNormalization` | 10 | Edge cases: `+55`, `(48)`, hífen, espaço, letras, vazio |
  | `TestQAtivos` | 8 | JOIN correto, campos presentes, filtro de status, ordenação |
  | `TestHistoricoFiltros` | 8 | Filtros por leitor/tipo combinados, ordenação DESC |

- **`wa_button` agora retorna `bool`** — retorna `True` quando o envio via API foi bem-sucedido, permitindo que o chamador reaja ao resultado sem acessar estado interno.

### Limpeza do projeto

Arquivos removidos:
- `app/app.py` — versão anterior do app (76 KB), substituída por `app_v3.py`
- `index.html` — protótipo HTML descartado (40 KB)
- `Dockerfile.evolution` — abordagem de build abandonada (todas as tentativas falharam)
- `app/__pycache__/`, `tests/__pycache__/`, `.pytest_cache/` — caches automáticos

Arquivos atualizados:
- `.gitignore` — agora ignora `__pycache__/`, `*.pyc`, `.pytest_cache/`, `logs/`
- `requirements.txt` — versão mínima corrigida para `streamlit>=1.24.0` (versão que introduziu `format=` no `date_input`)

---

## [v3] — Refatoração maior (commits anteriores)

### Funcionalidades principais

#### 🏠 Dashboard (Home)
- Painel com indicadores em tempo real: total de livros, leitores cadastrados, empréstimos ativos, devoluções pendentes e atrasadas.
- Alertas visuais automáticos para empréstimos vencendo nos próximos 5 dias e já atrasados, com atalho direto para envio de WhatsApp.

#### 📖 Empréstimos
- **Novo empréstimo**: seleção de leitor + livro disponível, cálculo automático da data de devolução (configurável, padrão 30 dias), banner de confirmação com envio WhatsApp.
- **Renovação**: até 3 renovações por empréstimo; bloqueada se houver fila de espera para o livro; nova data de devolução calculada a partir da data atual.
- **Devolução**: marca o empréstimo como devolvido, libera o exemplar no acervo, notifica automaticamente o próximo da fila de espera via WhatsApp.
- **Edição**: correção de data, reenvio de confirmação, cancelamento de empréstimo.
- **Regras de negócio**:
  - Máximo 3 empréstimos ativos por leitor.
  - Mesmo livro não pode ser emprestado duas vezes ao mesmo leitor.
  - Livro só aparece como disponível se houver exemplares não emprestados (`quantidade - ativos > 0`).

#### 📚 Livros
- CRUD completo: cadastro, edição e exclusão de livros.
- Campo **quantidade de exemplares** — suporta acervo com múltiplas cópias.
- Campos: título, autor, categoria, quantidade.
- Exportação da lista em CSV.

#### 👤 Leitores
- CRUD completo: cadastro, edição e exclusão de leitores.
- Campos: nome, telefone (WhatsApp), e-mail, endereço.
- Exportação da lista em CSV.
- Proteção: leitor com empréstimos ativos não pode ser excluído.

#### 📊 Histórico
- Registro automático de todas as operações: empréstimo, devolução, renovação, cancelamento.
- Filtros por leitor e por tipo de operação.
- Exportação em CSV.

#### 💬 Mensagens
- **Caixa de entrada**: visualização das mensagens recebidas pelo WhatsApp (via Evolution API), agrupadas por contato, com campo de resposta rápida integrado.
- **Envio em massa**: mensagem personalizada enviada a todos os leitores com empréstimos ativos de uma vez.
- **Envio individual**: seleção de leitor e texto livre, com pré-visualização.

#### ⚙️ Configurações (admin)
- Nome da igreja (aparece nas mensagens automáticas).
- Prazo padrão de empréstimo em dias.
- Gerenciamento de usuários do sistema (criar, trocar senha, excluir).

### Integração WhatsApp (Evolution API)
- Conexão via QR Code ou Pairing Code.
- Envio automático de mensagens de confirmação ao registrar empréstimo.
- Mensagens de renovação e devolução com dados formatados.
- Fallback para link `wa.me` quando a API não está conectada.
- Indicador de status de conexão visível no app.

### Scheduler de lembretes automáticos (`app/scheduler.py`)
- Serviço independente que roda em background.
- Disparo diário configurável (`HORA_DISPARO`, `MINUTO_DISPARO`).
- Lógica:
  - **Atrasados**: envia aviso de atraso a quem já passou da data de devolução.
  - **Vencendo**: envia lembrete a quem vence nos próximos `DIAS_AVISO` dias (padrão: 5).
- Controle de lote: `BATCH_SIZE=5` mensagens por hora, com delays aleatórios entre mensagens para evitar bloqueio do WhatsApp.
- Log em `logs/scheduler.log`.

### Segurança
- Autenticação com hash PBKDF2-SHA256 + salt (200.000 iterações).
- Senhas nunca armazenadas em texto plano.
- Controle de acesso: funcionalidades admin restritas por role.
- Proteção contra exclusão de dados com dependências (leitor com empréstimo, livro emprestado).
- Migrações de banco executadas na inicialização, garantindo backward compatibility.

### Banco de dados (SQLite)
Tabelas: `livros`, `leitores`, `emprestimos`, `historico`, `fila_espera`, `usuarios`, `config`.

---

## [v1/v2] — Versões iniciais

- `708e3ba` — Primeiro commit: estrutura inicial do projeto.
- `73bd771` — CRUD completo, login, WhatsApp, fila de espera.
- `fe1b0a7` — Validações de integridade e segurança do BD.
- `6e1ce6d` — Correção de f-strings incompatíveis com Python 3.11.
- `5b44206` — Remoção do venv do repositório.
- `afccb69` — Campo quantidade de exemplares nos livros.
- `a2c9dea` — Correção de totalizadores, NameError e melhoria de feedback via toast.
- `65e2c19` — Regras de empréstimo por pessoa (limite 3, sem duplicatas) e botões padronizados.
