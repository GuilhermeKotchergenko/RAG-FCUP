# Architecture Decision Records (ADR)
# Assistente Inteligente FCUP — RAG Local

**Versão:** 1.0  
**Data:** 2026-02-21

> Cada ADR documenta uma decisão arquitetural significativa: o contexto, as alternativas consideradas, a decisão tomada e as suas consequências.

---

## ADR-001 — Processamento 100% Local (sem APIs externas)

**Estado:** Aceite  
**Data:** 2026-02-21

### Contexto
O sistema lida com conteúdo institucional da FCUP e dados de alunos (emails). O Regulamento Geral de Proteção de Dados (RGPD) e a política de privacidade da Universidade do Porto impõem restrições ao envio de dados para servidores externos.

### Alternativas Consideradas
| Opção | Custo | Privacidade | Dependência |
|---|---|---|---|
| OpenAI API | Alto (por token) | ❌ Dados saem da UE | ❌ Externa |
| Azure OpenAI (UE) | Alto | ⚠️ Cloud da Microsoft | ❌ Externa |
| **Ollama local** | Gratuito | ✅ 100% local | ✅ Nenhuma |

### Decisão
**Ollama com modelos open-source** (`llama3.1:8b`) correndo localmente. Todos os embeddings também são gerados localmente (`nomic-embed-text`).

### Consequências
- ✅ Conformidade total com RGPD
- ✅ Sem custos recorrentes de API
- ✅ Funciona offline (dentro da rede da FCUP)
- ⚠️ Performance dependente do hardware disponível (GPU recomendada)

---

## ADR-002 — LlamaIndex como Orquestrador RAG

**Estado:** Aceite  
**Data:** 2026-02-21

### Contexto
Era necessário escolher uma framework para orquestrar o pipeline RAG: ingestão de documentos, geração de embeddings, retrieval semântico e augmentação do prompt.

### Alternativas Consideradas
| Framework | Maturidade RAG | Integração Qdrant | Complexidade |
|---|---|---|---|
| LangChain | Alta | ✅ | Alta (muito genérico) |
| **LlamaIndex** | **Muito Alta (especializado)** | ✅ | Média |
| Haystack | Alta | ✅ | Alta |
| Custom (sem framework) | N/A | Manual | Muito Alta |

### Decisão
**LlamaIndex** — especializado em RAG, com ingestão de documentos, chunking, embeddings, e query engines prontos a usar. Integração nativa com Qdrant e Ollama.

### Consequências
- ✅ Pipeline RAG completo com poucas linhas de código
- ✅ Suporte nativo a streaming (`aquery()` + `async_response_gen()`)
- ✅ `SimilarityPostprocessor` para filtrar chunks irrelevantes
- ⚠️ Versões do `llama-index` mudam frequentemente; fixar versões no `pyproject.toml`

---

## ADR-003 — Qdrant como Vector Store

**Estado:** Aceite  
**Data:** 2026-02-21

### Contexto
Era necessária uma base de dados vetorial para armazenar os embeddings dos chunks de texto e fazer retrieval semântico eficiente.

### Alternativas Consideradas
| Opção | Deploy | Performance | Filtros de Metadados |
|---|---|---|---|
| ChromaDB | Local / Docker | Média | Básicos |
| FAISS | In-memory | Alta | Nenhuns (puro vetor) |
| Pinecone | Cloud | Alta | ✅ | ❌ (cloud) |
| **Qdrant** | **Docker (local)** | **Alta** | **✅ Avançados** |

### Decisão
**Qdrant via Docker** — performante, com filtros avançados de metadados (ex: filtrar por URL ou data de indexação), modo em memória disponível para testes, e preparado para produção.

### Consequências
- ✅ Filtragem por metadados (URL, título, data) disponível para futuras funcionalidades
- ✅ Persistência em volume Docker (survive restarts)
- ✅ API REST para inspeção e debug (`http://localhost:6333/dashboard`)
- ⚠️ Requer Docker; alternativa: `QdrantClient(":memory:")` para testes
- ⚠️ Em ambiente WSL2, as regras de NAT podem corromper-se ao reiniciar containers; requer ciclo `docker compose down && docker compose up` para limpar regras de rede.

---

## ADR-004 — Chainlit como Frontend de Chat

**Estado:** Aceite  
**Data:** 2026-02-21

### Contexto
Era necessária uma interface de chat para o utilizador final, com suporte a streaming de tokens e apresentação de fontes.

### Alternativas Consideradas
| Opção | Streaming | Histórico | Esforço de Implementação |
|---|---|---|---|
| Gradio | ⚠️ Limitado | ❌ | Baixo |
| Streamlit | ⚠️ Simulado | ❌ | Baixo |
| Custom React/Next.js | ✅ | ✅ | Muito Alto |
| **Chainlit** | **✅ Nativo** | **✅ Nativo** | **Baixo** |

### Decisão
**Chainlit** — interface de chat nativa com streaming token-a-token, histórico de sessão, e sistema de feedback, sem necessidade de construir um frontend de raiz.

### Consequências
- ✅ Streaming via `async_response_gen()` funciona nativamente
- ✅ Histórico de conversa por sessão
- ⚠️ Chainlit lê a variável `DATABASE_URL` para persistência própria → conflito com a nossa variável SQLAlchemy → renomeada para `APP_DATABASE_URL`
- ⚠️ Requer `await engine.aquery()` (async) em vez de `engine.query()` (sync)

---

## ADR-005 — Magic Link como Mecanismo de Autenticação

**Estado:** Aceite  
**Data:** 2026-02-21

### Contexto
Era necessário restringir o acesso ao chatbot a utilizadores com email `@fc.up.pt`, sem armazenar palavras-passe e com o mínimo de dependências externas.

### Alternativas Consideradas
| Opção | Sem senha | Dependências Externas | Complexidade |
|---|---|---|---|
| SSO Shibboleth (FCUP) | ✅ | ❌ (infra FCUP) | Alta |
| OAuth (Google/GitHub) | ✅ | ❌ (externo) | Média |
| Username + Password | ❌ | Nenhuma | Baixa |
| **Magic Link** | **✅** | **Nenhuma** | **Baixa** |

### Decisão
**Magic Link via JWT** — email `@fc.up.pt` validado por domínio, token JWT assinado com TTL de 15 minutos, token de uso único (hash guardado na DB), sessão via cookie seguro.

### Consequências
- ✅ Sem palavras-passe armazenadas
- ✅ Sem dependências de OAuth externos
- ✅ Validação de domínio `@fc.up.pt` simples e robusta
- ⚠️ Requer SMTP funcional em produção (simulado por console em desenvolvimento com `SIMULATE_EMAIL=true`)

---

## ADR-006 — Playwright para Scraping Autenticado

**Estado:** Pendente (Fase 3)  
**Data:** 2026-02-21

### Contexto
Parte do conteúdo relevante do SIGARRA (ex: regulamentos curriculares, informação de unidades curriculares) está atrás de login. Era necessária uma estratégia de scraping autenticado.

### Alternativas Consideradas
| Opção | Login Autenticado | Javascript | Manutenção |
|---|---|---|---|
| `requests` + `BeautifulSoup` | ⚠️ (só POST simples) | ❌ | Baixa |
| Selenium | ✅ | ✅ | Alta |
| **Playwright** | **✅** | **✅** | **Média** |

### Decisão
**Playwright** — suporte a login autenticado com persistência de sessão (`storage_state.json`), execução headless ou com browser visível para login manual inicial.

### Consequências
- ✅ Login manual uma vez → sessão persistida para crawls futuros
- ✅ Suporte a páginas com JavaScript (SIGARRA usa SSO)
- ⚠️ Sessão expira (necessário renovar periodicamente)
- ⚠️ Executar com cuidado para não disparar alertas de segurança do SIGARRA

---

## ADR-007 — Modelo LLM: llama3.1:8b com fallback qwen2.5:3b

**Estado:** Aceite  
**Data:** 2026-02-21

### Contexto
Em CPU, o `llama3.1:8b` requer ~20 GB de RAM — inviável em máquinas com 14.9 GB. Com GPU (RTX 5060, 8 GB VRAM), o modelo cabe integralmente na VRAM e corre a ~30–60 tokens/s.

### Decisão
- **Com GPU disponível:** `llama3.1:8b` (melhor qualidade, ~4.9 GB VRAM)
- **Sem GPU / RAM limitada:** `qwen2.5:3b` (fallback, ~1.9 GB, ~2–5 tokens/s em CPU)
- Configurável via `LLM_MODEL` no `.env` sem alterar código

### Consequências
- ✅ Flexibilidade de hardware via variável de ambiente
- ✅ Em produção no servidor FCUP, pode-se usar modelos maiores (70B com A100)
- ⚠️ `llama3.1:8b` com RTX 5060 tem VRAM ocupada ~5–6 GB; modelos maiores requerem hardware de servidor

---

## ADR-008 — Normalização de Query (Query Rewriting)

**Estado:** Aceite  
**Data:** 2026-02-21

### Contexto
O corpus de documentos (SIGARRA/InfoCiências) está maioritariamente em Português de Portugal (PT-PT). Utilizadores que perguntem em Inglês ou Português do Brasil (PT-BR) geram embeddings que podem não ser semanticamente próximos dos termos técnicos/académicos em PT-PT, degradando a qualidade do retrieval.

### Alternativas Consideradas
| Opção | Complexidade | Latência | Eficácia |
|---|---|---|---|
| Indexação bilingue | Muito Alta | Alta | Média |
| Embedding Multilingue | Baixa | Baixa | Variável (depende do modelo) |
| **Query Rewriting (LLM)** | **Média** | **Média** | **Alta** |

### Decisão
**Query Rewriting via LLM** — Antes de realizar a pesquisa vetorial, a pergunta do utilizador é passada por um prompt "magro" que a traduz/normaliza para PT-PT conciso. Isto garante que o embedding gerado usa a terminologia correta do corpus.

### Consequências
- ✅ Melhoria drástica no retrieval para utilizadores internacionais (Erasmus) e brasileiros
- ✅ Remoção de ruído e "filler words" da pergunta original
- ⚠️ Pequeno aumento na latência (um call extra ao LLM antes do retrieval)
- ⚠️ Requer prompt robusto para o LLM não responder à pergunta neste passo intermédio
