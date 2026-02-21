# Tecnologias e Fluxo de Funcionamento
# Assistente Inteligente FCUP — RAG Local

**Versão:** 1.0  
**Data:** 2026-02-21

---

## 1. Stack Tecnológica

### Visão Geral

```
┌─────────────────────────────────────────────────────────┐
│                     Servidor FCUP (on-premise)           │
│                                                         │
│  ┌──────────────┐    ┌──────────────┐    ┌───────────┐  │
│  │   Chainlit   │    │   FastAPI    │    │ PostgreSQL │  │
│  │  (porta 8000)│◄──►│  (porta 8001)│◄──►│ (porta 5432)│ │
│  └──────┬───────┘    └──────────────┘    └───────────┘  │
│         │                                               │
│         ▼                                               │
│  ┌──────────────┐    ┌──────────────┐                   │
│  │  LlamaIndex  │◄──►│    Qdrant    │                   │
│  │ (orquestração)│    │ (porta 6333) │                   │
│  └──────┬───────┘    └──────────────┘                   │
│         │                                               │
│         ▼                                               │
│  ┌──────────────┐                                       │
│  │    Ollama    │  llama3.1:8b + nomic-embed-text       │
│  │ (porta 11434)│  GPU: RTX 5060 (8 GB VRAM)            │
│  └──────────────┘                                       │
└─────────────────────────────────────────────────────────┘
```

### Tabela de Componentes

| Componente | Tecnologia | Versão | Função | Porta |
|---|---|---|---|---|
| **LLM Local** | Ollama + llama3.1:8b | 0.6.x | Geração de respostas em linguagem natural | 11434 |
| **Embeddings** | nomic-embed-text via Ollama | latest | Conversão de texto em vetores semânticos | 11434 |
| **Orquestração RAG** | LlamaIndex | 0.14.x | Pipeline completo: retrieval + augmentation + generation | — |
| **Vector Store** | Qdrant | latest | Armazenamento e busca semântica de chunks | 6333 |
| **Frontend** | Chainlit | 2.x | Interface de chat com streaming | 8000 |
| **Backend** | FastAPI | 0.129.x | API REST, Magic Link, gestão de sessões | 8001 |
| **Base de Dados** | PostgreSQL 16 | 16-alpine | Utilizadores e tokens de autenticação | 5432 |
| **Scraper** | httpx + BeautifulSoup | 0.28.x / 4.12.x | Crawler recursivo de páginas HTML | — |
| **Auth Browser** | Playwright | 1.58.x | Login autenticado no SIGARRA | — |
| **Linguagem** | Python | 3.12 | Linguagem principal do projeto | — |
| **Containers** | Docker Compose | v2 | Orquestração de serviços | — |
| **GPU Runtime** | nvidia-container-toolkit | — | Acesso à GPU dentro do Docker | — |

---

## 2. Fluxo de Ingestão de Dados

```
SIGARRA FCUP                    InfoCiências
(sigarra.up.pt/fcup/)          (info.fc.up.pt/)
        │                              │
        └──────────┬───────────────────┘
                   │
                   ▼
         ┌─────────────────┐
         │  scraper/       │
         │  crawler.py     │  BFS recursivo
         │                 │  crawl-delay: 3s
         │  • Extrai texto │  robots.txt compliance
         │  • Extrai URL   │  Limite: 200–500 pág.
         │  • Filtra HTML  │
         └────────┬────────┘
                  │ data/raw/*.json
                  ▼
         ┌─────────────────┐
         │  scraper/       │
         │  ingest.py      │
         │                 │
         │  1. Carrega JSON│
         │  2. Chunking    │  512 tokens
         │     (LlamaIndex)│  50 overlap
         │  3. Embeddings  │  nomic-embed-text
         │     (Ollama)    │  → 768 dimensões
         │  4. Upsert      │
         └────────┬────────┘
                  │
                  ▼
         ┌─────────────────┐
         │     Qdrant      │
         │  Collection:    │  Metadados:
         │  "fcup_docs"    │  • url
         │                 │  • title
         │  Cosine sim.    │  • crawled_at
         └─────────────────┘
```

**Comando:** `make pipeline` (crawl + ingest)

---

## 3. Fluxo de Autenticação (Magic Link)

```
Aluno                    FastAPI (porta 8001)          PostgreSQL
  │                            │                           │
  │  POST /api/auth/send       │                           │
  │  {"email":"x@fc.up.pt"}   │                           │
  ├──────────────────────────►│                           │
  │                            │  1. Valida @fc.up.pt     │
  │                            │  2. Gera JWT (15 min)    │
  │                            │  3. Hash do token        │
  │                            ├──────── INSERT ──────────►│
  │                            │     MagicToken           │
  │                            │  4. Envia/simula email   │
  │◄──────────────────────────│                           │
  │  {"magic_link": "..."}     │                           │
  │                            │                           │
  │  GET /api/auth/verify      │                           │
  │  ?token=<jwt>              │                           │
  ├──────────────────────────►│                           │
  │                            │  1. Valida JWT           │
  │                            │  2. Busca token na DB    │
  │                            ├──────── SELECT ──────────►│
  │                            │◄──────── token ───────────│
  │                            │  3. Marca token como used│
  │                            ├──────── UPDATE ──────────►│
  │                            │  4. Upsert User          │
  │                            │  5. Emite cookie sessão  │
  │◄──────────────────────────│                           │
  │  Set-Cookie: fcup_session  │                           │
```

---

## 4. Fluxo de Consulta (RAG Pipeline)

```
Aluno (browser)
      │
      │  "Como me inscrevo em cadeiras no SIGARRA?"
      ▼
┌─────────────────────────────────┐
│         Chainlit (8000)         │  Interface de chat
│  on_message() — async           │
└────────────────┬────────────────┘
                 │
                 ▼
┌─────────────────────────────────┐
│   LlamaIndex – RetrieverQuery   │
│   Engine (async)                │
│                                 │
│   engine.aquery(pergunta)        │
└──────┬──────────────────────────┘
       │
       ├─── 1. EMBEDDING DA PERGUNTA
       │         │
       │         ▼
       │    ┌─────────────┐
       │    │   Ollama    │  nomic-embed-text
       │    │  /api/embed │  → vetor 768-dim
       │    └─────────────┘
       │
       ├─── 2. RETRIEVAL SEMÂNTICO
       │         │
       │         ▼
       │    ┌─────────────┐
       │    │   Qdrant    │  Busca top-5 chunks
       │    │ cosine sim. │  similitude ≥ 0.3
       │    │             │  retorna texto + URL
       │    └─────────────┘
       │
       └─── 3. GENERATION (AUGMENTED)
                 │
                 ▼
            ┌─────────────┐
            │   Ollama    │  llama3.1:8b
            │  /api/chat  │  GPU: RTX 5060
            │             │  Prompt:
            │  SISTEMA:   │  • Responde em PT
            │  Contexto   │  • Cita URL
            │  [chunks]   │  • Sem inventar
            │  Pergunta   │
            └──────┬──────┘
                   │
                   ▼  streaming token-a-token
┌─────────────────────────────────┐
│         Chainlit (8000)         │
│  stream_token() por token       │
│                                 │
│  "O SIGARRA permite inscrição   │
│   de cadeiras no início de cada │
│   semestre através do menu..."  │
│                                 │
│  📚 Fontes:                     │
│  • [FCUP - SIGARRA](https://...)│
└─────────────────────────────────┘
```

---

## 5. Modelo de Dados

### Qdrant — Collection `fcup_docs`

```
Chunk {
  id:       UUID (gerado por LlamaIndex)
  vector:   float[768]   (nomic-embed-text)
  payload: {
    url:         "https://sigarra.up.pt/fcup/pt/..."
    title:       "FCUP - Inscrição de Cadeiras"
    crawled_at:  "2026-02-21T11:30:00Z"
    text:        "Para se inscrever em cadeiras..."  (512 tokens)
  }
}
```

### PostgreSQL — Tabelas de Auth

```sql
CREATE TABLE users (
    email       VARCHAR PRIMARY KEY,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE magic_tokens (
    token_hash  VARCHAR PRIMARY KEY,   -- SHA-256 do JWT
    email       VARCHAR NOT NULL,
    expires_at  TIMESTAMPTZ NOT NULL,  -- agora + 15 min
    used        BOOLEAN DEFAULT FALSE,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);
```

---

## 6. Configuração de Hardware

### Desenvolvimento Local (actual)

| Componente | Valor |
|---|---|
| CPU | Intel/AMD (WSL2) |
| RAM | 14.9 GB disponível |
| GPU | NVIDIA RTX 5060 Laptop (8 GB VRAM) |
| LLM | llama3.1:8b (GPU, ~5 GB VRAM) |
| Embeddings | nomic-embed-text (CPU/GPU, ~300 MB) |
| Velocidade estimada | ~30–60 tokens/s |

### Recomendação para Produção (servidor FCUP)

| Componente | Mínimo | Ideal |
|---|---|---|
| CPU | 8 cores | 16+ cores |
| RAM | 32 GB | 64 GB |
| GPU | NVIDIA A10 (24 GB) | NVIDIA A100 (80 GB) |
| LLM | llama3.1:8b | llama3.1:70b ou Qwen2.5:72b |
| Velocidade estimada | ~80 tokens/s | ~200+ tokens/s |

---

## 7. Ficheiros de Configuração Chave

| Ficheiro | Função |
|---|---|
| `.env` | Variáveis de ambiente (modelo, URLs, credenciais) |
| `docker-compose.yml` | Definição de todos os serviços e volumes |
| `pyproject.toml` | Dependências Python e configuração de testes |
| `data/seed_urls.txt` | URLs de entrada para o crawler |
| `Makefile` | Atalhos para todos os comandos frequentes |
