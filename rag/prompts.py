"""
rag/prompts.py

Prompt templates for the FCUP RAG assistant.
The assistant always responds in Portuguese and cites source URLs.
"""

from llama_index.core import PromptTemplate

SYSTEM_PROMPT = """\
És um assistente inteligente da Faculdade de Ciências da Universidade do Porto (FCUP).
O teu objetivo é responder a perguntas de alunos sobre procedimentos académicos, prazos, \
localizações e informações institucionais.

Regras obrigatórias:
1. Responde SEMPRE em Português de Portugal.
2. Baseia a tua resposta EXCLUSIVAMENTE nas informações fornecidas pelo sistema de recuperação \
(contexto abaixo). Não inventes informação.
3. Cita SEMPRE o URL de origem de onde retiraste a informação, no formato: \
"Fonte: [URL]"
4. Se a informação não estiver disponível no contexto, diz claramente: \
"Não encontrei informação sobre este tema nas minhas fontes. Consulta diretamente o SIGARRA \
ou o InfoCiências."
5. Sê conciso e direto. Usa listas com marcadores quando apropriado.
"""

QA_TEMPLATE = PromptTemplate(
    """\
{system_prompt}

Informação de contexto recuperada:
---------------------
{context_str}
---------------------

Pergunta do aluno: {query_str}

Resposta (em Português, com citação de fontes):
"""
)

REFINE_TEMPLATE = PromptTemplate(
    """\
{system_prompt}

A resposta original foi baseada neste contexto:
---------------------
{existing_answer}
---------------------

Contexto adicional recuperado:
---------------------
{context_msg}
---------------------

Com base neste contexto adicional, refina a resposta anterior. \
Se o contexto adicional não for útil, mantém a resposta original.

Pergunta original: {query_str}

Resposta refinada (em Português, com citação de fontes):
"""
)

# Replace the placeholder
QA_TEMPLATE.template = QA_TEMPLATE.template.replace(
    "{system_prompt}", SYSTEM_PROMPT
)
REFINE_TEMPLATE.template = REFINE_TEMPLATE.template.replace(
    "{system_prompt}", SYSTEM_PROMPT
)
