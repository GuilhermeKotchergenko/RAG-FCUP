# Troubleshooting

## `[Errno 104] Connection reset by peer` ao ligar ao Qdrant

### Sintoma

Ao correr `make chat` (ou qualquer código que use o `QdrantClient`), a aplicação falha imediatamente com:

```
qdrant_client.http.exceptions.ResponseHandlingException: [Errno 104] Connection reset by peer
```

O container `rag_qdrant` aparece como `Up` em `docker ps`, mas qualquer pedido HTTP a `localhost:6333` é recusado.

### Causa

Esta é uma **race condition de rede do WSL2 + Docker**. Quando os containers já estão a correr e se executa `docker compose up -d` novamente (por exemplo, após reiniciar o WSL2 ou aumentar a memória), o Docker **reinicia** os containers em vez de os recriar. Nesse processo, as regras de NAT/iptables que encaminham as portas do host para os containers ficam **corrompidas**, mesmo que o Docker reporte as portas como mapeadas.

### Solução

Em vez de `docker compose up -d` sobre containers já existentes, fazer sempre um ciclo completo de `down`/`up`:

```bash
docker compose down && docker compose up -d qdrant ollama postgres
```

O `down` remove os containers **e a rede Docker**, forçando o Docker a recriar regras de NAT limpas no `up` seguinte.

### Verificação

Depois do `up`, confirmar que o Qdrant responde antes de correr a aplicação:

```bash
curl http://localhost:6333/
# Deve devolver: {"title":"qdrant - vector search engine","version":"..."}
```

### Quando acontece

- Após reiniciar o WSL2
- Após aumentar a memória do WSL2 (`.wslconfig`)
- Após `docker compose up -d` sobre containers que já estavam a correr
