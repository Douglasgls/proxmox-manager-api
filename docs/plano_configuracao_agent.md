# PLANO DE ALTERAÇÕES — CONFIGURAÇÃO DO AGENT VIA INTERFACE

## Contexto e Objetivo
Este plano descreve como alterar a arquitetura do **proxmox-manager-api** para permitir que ele inicie e funcione parcialmente mesmo sem as credenciais do Proxmox VE configuradas via `.env`. A configuração passará a ser realizada pela interface web, gravada em uma nova tabela de banco de dados (`agent_config`), migrando instalações antigas de forma transparente e blindando o token de segurança.

---

## A. Arquivos que serão modificados

### `app/main.py`
- **Motivo**: Atualmente o `lifespan` tenta realizar `sync_all` e iniciar o `metrics_collector`, gerando erro (`ProxmoxConnectionError`) se as configurações não estiverem no `.env`.
- **Alteração**:
  - Antes de inicializar serviços dependentes do Proxmox, consultar o `AgentConfigService` para verificar se existe configuração.
  - Se configurado: fluxo normal.
  - Se não configurado: pular `sync_all` e a inicialização de métricas (`metrics_collector`).
  - Marcar o status global do Agent (`app.state.proxmox_configured`) para uso em endpoints de status.

### `app/integrations/proxmox/proxmox_client.py`
- **Motivo**: Hoje o `ProxmoxClient` busca hardcoded via `os.getenv`.
- **Alteração**:
  - Alterar o `__init__` para aceitar credenciais e configurações explicitamente via parâmetros, ou fazer com que o client as busque através de um provider (por exemplo, `AgentConfigService`).
  - O botão "Testar conexão" poderá injetar credenciais temporárias para validar sem salvar no banco.

### `app/core/dependencies.py`
- **Motivo**: Centraliza a injeção do `ProxmoxClient`.
- **Alteração**:
  - Atualizar a factory `get_proxmox_client` para injetar os dados vindo do banco de dados (via `AgentConfigService`). Caso a configuração não exista, levantar um erro amigável (`AgentNotConfiguredError`) ou retornar `None` (dependendo de como a API vai reagir).

### `app/cloud/crypto.py` (ou mover para `app/security/crypto.py`)
- **Motivo**: O `token_value` do Proxmox precisa ser salvo criptografado no banco de dados.
- **Alteração**: Reutilizar o mecanismo de criptografia existente (`CLOUD_ENCRYPTION_KEY`) para criar um utilitário genérico de encriptação no banco, permitindo guardar tokens de forma segura.

---

## B. Arquivos novos

### Banco e Domínio
- **`app/models/agent_config.py`**: Model do SQLAlchemy representando a tabela `agent_config`.
- **`app/schemas/agent_config.py`**: Pydantic schemas para requisições e respostas (ex: `AgentConfigResponse`, ocultando o token).
- **`app/repositories/agent_config_repository.py`**: Repositório para gerenciar a entidade (get, upsert).
- **`app/services/agent_config_service.py`**: Lógica de negócio, como migração do `.env` para o banco, criptografia/descriptografia do token e validação.

### API Routes
- **`app/api/agent.py`**: Novo router para lidar com a configuração:
  - `GET /agent/config`: Retorna a configuração atual.
  - `POST /agent/config`: Salva/atualiza a configuração.
  - `POST /agent/test-connection`: Testa as credenciais no corpo da requisição usando `ProxmoxClient`.
  - `POST /agent/restart`: Para solicitar um reinício da API.
  - `GET /agent/status`: Resumo geral do Agent (Configurado? Cloud Conectada? Database?).

---

## C. Banco de Dados

### Tabela `agent_config`
- **`id`**: String (UUID) - primary key.
- **`proxmox_host`**: String.
- **`proxmox_user`**: String.
- **`proxmox_token_name`**: String.
- **`proxmox_token_value`**: String (guardado criptografado).
- **`proxmox_node`**: String.
- **`default_storage`**: String.
- **`default_template`**: String.
- **`created_at`** e **`updated_at`**: Datetime.

**Constraints**: O sistema será projetado para ter um único registro nessa tabela. O repositório deverá usar `first()` e sempre atualizar o mesmo registro em caso de upsert.

**Segredo**: O `proxmox_token_value` será criptografado via AES (reaproveitando a infra do `app/cloud/crypto.py`) antes de ser salvo, e mascarado/removido nas saídas da API (endpoints GET nunca retornam o token real).

---

## D. Startup e Migração

O que impede a API de iniciar hoje é a chamada incondicional a `service.sync_all` e `metrics_collector.start()` em `app/main.py`.

### Novo fluxo de Startup:
1. Conexão com o banco (`SessionLocal`).
2. Verifica se a tabela `agent_config` tem registro.
3. Se NÃO tiver registro, checa as variáveis de ambiente `PROXMOX_*`.
   - Se `PROXMOX_HOST` etc. existirem, o `AgentConfigService` importa esses valores para o banco e cria o registro (Compatibilidade Retroativa).
4. Verifica a configuração atual (do banco).
5. Se `proxmox_configured == False`:
   - Configura `app.state.status = "NOT_CONFIGURED"`.
   - **Pula** o `sync_all` e o start das métricas.
   - API inicia perfeitamente saudável, mas rotas que pedem o `get_proxmox_client` retornarão `HTTP 503` ou um custom error `"Proxmox não configurado"`.
6. Se `proxmox_configured == True`:
   - Tenta conectar via client (`connect()`).
   - Se erro (host down), `app.state.status = "CONNECTION_ERROR"`.
   - Se ok, `app.state.status = "READY"`, prossegue com `sync_all` e métricas.

---

## E. API e Contract do Frontend

Novo router: `app/api/agent.py`.

### Endpoints
1. `GET /agent/config`
   - Retorna os dados cadastrados, mas mascara o segredo.
   - Retorno:
     ```json
     {
       "configured": true,
       "host": "192.168.0.175:8006",
       "user": "root@pam",
       "token_name": "vmAPI",
       "token_configured": true,
       "node": "pve",
       "default_storage": "local-lvm",
       "default_template": "local:vztmpl/..."
     }
     ```

2. `POST /agent/test-connection`
   - Recebe as credenciais completas, cria um `ProxmoxClient` em memória e roda `client.get_version()` ou `client.list_nodes()`.
   - Retorno: `{"success": true}` ou erro.

3. `POST /agent/config`
   - Salva a configuração validada no banco de dados.

4. `POST /agent/restart`
   - Realiza o restart. **Estratégia**: A API não pode rodar `systemctl`. Podemos enviar um sinal para o próprio processo ou utilizar mecanismos de exit (ex: `os._exit(1)` onde o `systemd` ou docker irá reabrir o processo automaticamente, caso aplicável. Precisaremos definir a melhor abordagem compatível com o environment).

5. `GET /agent/status`
   - Status de prontidão consolidado:
     ```json
     {
       "version": "1.x.x",
       "agent_status": "Em execução",
       "readiness": "NOT_CONFIGURED" | "CONNECTION_ERROR" | "READY",
       "cloud_status": "Conectado",
       "db_status": "Saudável"
     }
     ```

### Frontend
- Quando o front inicializar, chama `GET /agent/status`.
- Se `readiness == NOT_CONFIGURED`, a rota React router deve bloquear as views que dependem do Proxmox e forçar redirect para `/configuracoes`.
- A tela de configuração reutiliza a lógica de buscar templates e storages via API.

---

## F. Testes Mínimos Previstos

- **Startup sem Env:** Iniciar `app/main.py` sem `PROXMOX_*` definidos. Validar se a API sobe sem log de Exception.
- **API `GET /agent/config`**: Validar que a resposta nunca contém `token_value`.
- **API `POST /agent/test-connection`**: Testar com mock credentials pra simular sucesso/falha do Proxmox.
- **Teste de Migração**: Subir a aplicação com banco vazio + variáveis `PROXMOX_*`. Validar que o banco preenche com os valores do `.env`.
- **API Dependency**: Criar um endpoint usando `get_proxmox_client` e forçar estado `NOT_CONFIGURED`, checando se o retorno é `HTTP 503 Agent Not Configured`.

---
**Nota para revisão**: A principal decisão arquitetural tomada foi utilizar o banco de dados como única fonte de verdade a partir da inicialização, realizando um bootstrap silencioso a partir do `.env` na primeira vez que o sistema iniciar em uma instalação já existente.
