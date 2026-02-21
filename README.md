# 🎓 RAG-FCUP – Assistente Inteligente para Alunos da FCUP

Chatbot local e privado (100% RGPD) para alunos da **Faculdade de Ciências da Universidade do Porto (FCUP)**. Responde a perguntas sobre procedimentos académicos, prazos e serviços, citando sempre o URL da fonte.

## Stack

| Componente | Tecnologia |
|---|---|
| LLM local | Ollama (`llama3.1:8b`) |
| Embeddings | Ollama (`nomic-embed-text`) |
| RAG | LlamaIndex |
| Vector Store | Qdrant |
| Frontend | Chainlit |
| Backend/Auth | FastAPI + PostgreSQL |
| Scraping | Playwright + httpx |

---

## Início Rápido

### 1. Pré-requisitos

```bash
# Docker + Docker Compose
docker --version

# Python 3.10+
python --version

# Ollama (https://ollama.com)
ollama --version
```

### 2. Configurar ambiente

```bash
cp .env.example .env
# Edita .env se necessário (por defeito SIMULATE_EMAIL=true)
```

### 3. Instalar dependências Python

```bash
pip install uv
uv pip install -e ".[dev]"
playwright install chromium
```

### 4. Iniciar serviços (Docker)

```bash
docker compose up -d qdrant ollama postgres

# Descarregar modelos Ollama (apenas uma vez, pode demorar)
docker exec rag_ollama ollama pull llama3.1:8b
docker exec rag_ollama ollama pull nomic-embed-text
```

---

## Pipeline de Dados

### Passo 1 – Crawl (5 páginas de exemplo)

```bash
python scraper/crawler.py --limit 5
```

> Respeita `robots.txt`: pausa de 3s entre pedidos, evita caminhos bloqueados.

### Passo 2 – Ingestão no Qdrant

```bash
python scraper/ingest.py
```

### [Opcional] Login autenticado no SIGARRA

Para páginas que requerem autenticação:

```bash
python scraper/login.py
# Faz login manualmente na janela do browser
# O estado da sessão é guardado em data/browser_state.json
```

---

## Iniciar o Chat

```bash
# Interface Chainlit
chainlit run frontend/app.py --port 8000
# Abre http://localhost:8000
```

---

## Autenticação (Magic Link)

```bash
# Iniciar API
uvicorn api.main:app --port 8001 --reload

# Testar envio de Magic Link (modo simulado: imprime link na consola)
curl -X POST http://localhost:8001/api/auth/send \
  -H "Content-Type: application/json" \
  -d '{"email": "utilizador@fc.up.pt"}'
```

Apenas emails `@fc.up.pt` são aceites. Com `SIMULATE_EMAIL=true`, o link é impresso na consola em vez de enviado por email.

---

## Testes

```bash
# Testes unitários (não requerem serviços externos)
pytest tests/test_auth.py tests/test_scraper.py -v

# Testes de integração (requerem Qdrant + Ollama)
pytest tests/test_rag.py -v
```

---

## Docker Compose Completo

```bash
docker compose up -d
# chainlit  → http://localhost:8000
# api       → http://localhost:8001
# qdrant    → http://localhost:6333
# ollama    → http://localhost:11434
```

### GPU (opcional)

Descomenta a secção `deploy.resources` em `docker-compose.yml` se tiveres `nvidia-container-toolkit` instalado.

---

## Estrutura do Projeto

```
RAG-FCUP/
├── scraper/        # Playwright login, crawler, ingestão
├── rag/            # LlamaIndex pipeline + prompts PT
├── api/            # FastAPI + Magic Link + PostgreSQL
├── frontend/       # Chainlit UI (streaming + fontes)
├── tests/          # pytest (unit + integration)
└── data/
    ├── seed_urls.txt    # URLs de seed para o crawler
    └── raw/             # Páginas crawladas (JSON, não commitado)
```

---

## Conformidade RGPD

- Todos os dados processados localmente (sem APIs externas)
- Autenticação por Magic Link (sem palavras-passe armazenadas)
- Tokens de acesso de uso único com TTL de 15 minutos
- Conteúdo institucional nunca sai do servidor