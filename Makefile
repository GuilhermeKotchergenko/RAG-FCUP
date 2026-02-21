PYTHON = .venv/bin/python
CHAINLIT = .venv/bin/chainlit
PYTEST = .venv/bin/pytest
PORT = 8000

.PHONY: help chat chat-stop services services-down crawl ingest pipeline login test clean

# ── Default ────────────────────────────────────────────────────────────────────

help:
	@echo ""
	@echo "  RAG-FCUP – Comandos disponíveis"
	@echo "  ─────────────────────────────────────────────────────"
	@echo "  make services      Inicia Docker (Qdrant, Ollama, Postgres)"
	@echo "  make services-down Para todos os containers Docker"
	@echo ""
	@echo "  make chat          (Re)inicia o Chainlit em background → http://localhost:$(PORT)"
	@echo "  make chat-dev      Inicia o Chainlit em foreground (Ctrl+C para parar)"
	@echo "  make chat-stop     Para o Chainlit"
	@echo "  make logs          Acompanha os logs do Chainlit em tempo real"
	@echo ""
	@echo "  make crawl         Crawl recursivo (até 200 páginas)"
	@echo "  make crawl-full    Crawl completo (até 500 páginas)"
	@echo "  make ingest        Indexa data/raw/ no Qdrant"
	@echo "  make pipeline      Crawl (200) + ingest numa só execução"
	@echo "  make pipeline-full Crawl (500) + ingest numa só execução"
	@echo ""
	@echo "  make login         Playwright: login manual no SIGARRA"
	@echo "  make test          Testes unitários (sem serviços externos)"
	@echo "  make test-all      Todos os testes (requer Qdrant + Ollama)"
	@echo "  make clean         Remove data/raw/ e ficheiros temporários"
	@echo ""

# ── Docker Services ────────────────────────────────────────────────────────────

services:
	docker compose up -d qdrant ollama postgres
	@echo "✅ Serviços a correr. Ollama: http://localhost:11434 | Qdrant: http://localhost:6333"

services-down:
	docker compose down
	@echo "🛑 Containers parados."

logs:
	tail -f /tmp/chainlit.log

# ── Chainlit Chat ──────────────────────────────────────────────────────────────

chat:
	@fuser -k $(PORT)/tcp 2>/dev/null || true
	@sleep 1
	$(CHAINLIT) run frontend/app.py --port $(PORT)

chat-bg:
	@echo "🔄 A iniciar Chainlit em background..."
	@fuser -k $(PORT)/tcp 2>/dev/null || true
	@sleep 1
	nohup $(CHAINLIT) run frontend/app.py --port $(PORT) > /tmp/chainlit.log 2>&1 & echo "✅ http://localhost:$(PORT)  |  Logs: make logs"

chat-stop:
	@pkill -f "chainlit run" 2>/dev/null && echo "🛑 Chainlit parado." || echo "ℹ️  Chainlit não estava a correr."

# ── Scraper ────────────────────────────────────────────────────────────────────

crawl:
	$(PYTHON) scraper/crawler.py --limit 200

crawl-full:
	$(PYTHON) scraper/crawler.py --limit 500

login:
	$(PYTHON) scraper/login.py

# ── Ingest ─────────────────────────────────────────────────────────────────────

ingest:
	$(PYTHON) scraper/ingest.py

# ── Full Pipeline ──────────────────────────────────────────────────────────────

pipeline:
	$(PYTHON) scraper/run_full_pipeline.py --limit 200

pipeline-full:
	$(PYTHON) scraper/run_full_pipeline.py --limit 500

re-ingest:
	$(PYTHON) scraper/run_full_pipeline.py --skip-crawl

# ── Tests ──────────────────────────────────────────────────────────────────────

test:
	$(PYTEST) tests/test_auth.py tests/test_scraper.py -v

test-all:
	$(PYTEST) tests/ -v

# ── Cleanup ────────────────────────────────────────────────────────────────────

clean:
	@rm -rf data/raw/
	@find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	@echo "🧹 data/raw/ e caches limpos."
