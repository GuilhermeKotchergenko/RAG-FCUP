# Product Requirements Document (PRD)
# Assistente Inteligente FCUP — RAG Local

**Versão:** 1.0  
**Data:** 2026-02-21  
**Autor:** Guilherme Batista  
**Estado:** Em desenvolvimento (Fase 1 – POC)

---

## 1. Visão Geral

### 1.1 Problema

Os alunos da Faculdade de Ciências da Universidade do Porto (FCUP) enfrentam dificuldades em navegar nos sistemas institucionais — principalmente o **SIGARRA** e o **InfoCiências**. Encontrar informação sobre procedimentos académicos, prazos, localização de serviços e regulamentos é frequentemente frustrante, dispersa por múltiplas páginas sem uma forma centralizada de pesquisa.

### 1.2 Solução

Um **chatbot inteligente local** que:
- Responde em linguagem natural a perguntas dos alunos
- Baseia todas as respostas em conteúdo oficial do SIGARRA e do InfoCiências
- Cita **sempre** o URL de origem para que o aluno possa validar a informação
- Funciona **100% localmente** (sem envio de dados para APIs externas), garantindo conformidade com o RGPD

### 1.3 Utilizadores-Alvo

- Alunos de licenciatura, mestrado e doutoramento da FCUP
- Alunos internacionais (Erasmus) com menor familiaridade com os sistemas portugueses
- Estudantes em mobilidade que precisam de informação rápida sobre procedimentos

---

## 2. Objetivos e Métricas de Sucesso

| Objetivo | Métrica | Alvo |
|---|---|---|
| Resposta relevante | % de respostas classificadas como úteis | ≥ 80% |
| Citação de fontes | Toda resposta inclui URL | 100% |
| Tempo de resposta | Tempo até primeiro token | ≤ 5s (com GPU) |
| Conformidade RGPD | Nenhum dado enviado a APIs externas | 100% |
| Acesso restrito | Apenas emails @fc.up.pt | 100% |

---

## 3. Requisitos Funcionais

### RF-01 — Autenticação Magic Link
- O utilizador insere o email `@fc.up.pt`
- O sistema valida o domínio (rejeita outros domínios)
- É enviado (ou simulado) um link de acesso único com TTL de 15 minutos
- O link é de uso único (após uso, fica inválido)
- É criada uma sessão via cookie seguro (HTTPOnly, SameSite=Lax)

### RF-02 — Interface de Chat
- Chat em linguagem natural em Português de Portugal
- Streaming de tokens (resposta aparece progressivamente)
- Links clicáveis para as fontes consultadas
- Histórico de conversa visível durante a sessão

### RF-03 — Resposta Baseada em Fontes
- O sistema responde **exclusivamente** com base no conteúdo indexado.
- Proibição de uso de conhecimento interno/próprio do LLM para evitar alucinações.
- Se não tiver informação no contexto, usa um fallback genérico direcionando para os serviços académicos.
- Cada resposta deve terminar com as fontes no formato `Fonte: [URL]`

### RF-04 — Ingestão de Dados
- Crawler respeita `robots.txt` (crawl-delay: 3s, paths bloqueados)
- Índice cobre páginas públicas do SIGARRA FCUP e InfoCiências
- Suporte a re-indexação periódica (atualização do conteúdo)
- Login autenticado via Playwright para conteúdo restrito (Fase 3)

### RF-05 — Retrieval Semântico
- Pergunta é convertida em embedding (nomic-embed-text)
- Busca os N chunks mais semelhantes no Qdrant (top-3 por defeito para reduzir ruído)
- Chunks com similaridade abaixo de 0.45 são descartados (threshold rigoroso contra alucinações)
- Metadados incluem: URL de origem, título, data de indexação

### RF-06 — Normalização de Query (Query Rewriting)
- Suporte a perguntas em Inglês e Português do Brasil (PT-BR).
- O sistema utiliza o LLM para reescrever a pergunta em Português de Portugal (PT-PT) antes da geração do embedding.
- Melhora a precisão do retrieval semântico contra o corpus que está em PT-PT.

---

## 4. Requisitos Não-Funcionais

### RNF-01 — Privacidade e RGPD
- Todo o processamento ocorre no servidor da FCUP (on-premise)
- Nenhum dado de alunos ou conteúdo institucional sai do servidor
- Palavras-passe nunca são armazenadas (Magic Link)
- Tokens de acesso são hashed antes de serem guardados na base de dados

### RNF-02 — Performance
- Tempo de resposta (primeiro token) ≤ 5s com GPU
- Embedding de queries ≤ 500ms
- Retrieval no Qdrant ≤ 200ms
- Suporte a múltiplos utilizadores simultâneos (configurável via `OLLAMA_NUM_PARALLEL`)

### RNF-03 — Disponibilidade
- Sistema deve reiniciar automaticamente após falha (`restart: unless-stopped`)
- Dados persistidos em volumes Docker (não se perdem com reinicios)

### RNF-04 — Manutenibilidade
- Re-indexação de conteúdo executável com `make pipeline`
- Configuração centralizada via ficheiro `.env`
- Logs estruturados em todos os componentes

---

## 5. Fora de Âmbito (MVP)

- Resposta a perguntas fora do âmbito da FCUP
- Interface de administração para gestão de conteúdo
- Autenticação via SSO institucional (Shibboleth)
- App mobile

---

## 6. Roadmap por Fases

| Fase | Descrição | Estado |
|---|---|---|
| **Fase 1 – POC** | Chat funcional com dados públicos, sem autenticação obrigatória | ✅ Em curso |
| **Fase 2 – Auth** | Magic Link + restrição a `@fc.up.pt` | 🔵 Implementado, por ativar |
| **Fase 3 – SIGARRA Auth** | Scraping autenticado com Playwright + conteúdo restrito | ⏳ Pendente |
| **Fase 4 – Produção** | Deploy no servidor on-premise da FCUP, GPU dedicada, múltiplos utilizadores | ⏳ Pendente |

---

## 7. Riscos e Mitigações

| Risco | Probabilidade | Impacto | Mitigação |
|---|---|---|---|
| SIGARRA altera estrutura HTML | Média | Alto | Crawler com extração genérica de texto; monitorização periódica |
| GPU insuficiente para múltiplos utilizadores | Alta | Médio | `OLLAMA_NUM_PARALLEL` + fila de espera nativa do Ollama |
| Conteúdo indexado desatualizado | Alta | Médio | Re-indexação semanal agendada (`make pipeline`) |
| Modelo LLM produz respostas incorretas ("alucinações") | Média | Alto | Sistema prompt restrito; similaridade mínima 0.45; citação de fontes obrigatória; normalização de query (Query Rewriting) |
