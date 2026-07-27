# 🏗️ Análise Técnica e Arquitetural da Plataforma (Cloud, Agent e Client)

> **Data da Análise:** 27 de Julho de 2026  
> **Status:** Protótipo Avançado em Transição para Produção  

---

## 📑 Sumário

1. [Visão Geral da Arquitetura](#-visão-geral-da-arquitetura)
2. [Análise Detalhada: CLOUD (`cloud_control_api`)](#-1-cloud-cloud_control_api)
3. [Análise Detalhada: AGENT (`proxmox-manager-api`)](#-2-agent-proxmox-manager-api)
4. [Análise Detalhada: CLIENT (`client` & `proxmox-manager-app`)](#-3-client-client--proxmox-manager-app)
5. [Matriz e Estimativa de Maturidade](#-4-matriz-e-estimativa-de-maturidade)
6. [Dívida Técnica Consolidada](#-5-dívida-técnica-consolidada)
7. [Roadmap e Ordem Recomendada de Evolução](#-6-roadmap-e-ordem-recomendada-de-evolução)
8. [Componentes Maduros (Congelados para Novas Features)](#-7-componentes-maduros-congelados)

---

## 🌐 Visão Geral da Arquitetura

A plataforma é composta por 3 projetos principais integrados para oferecer gerenciamento centralizado e acesso remoto seguro a containers LXC e infraestrutura Proxmox VE através de redes overlay privadas (Tailscale/Headscale).

```
 +-----------------------------------------------------------------------+
 |                            CLIENT (Desktop/CLI)                       |
 |  Go Wails App + React Frontend (proxmox-manager-app)                  |
 |  - Autenticação e Seleção de Ambientes                                |
 |  - Tunelamento SOCKS5 & Port Forwarding Local                         |
 |  - Console PTY via WebSockets (Xterm.js)                              |
 +-------------------+-----------------------------------+---------------+
                     |                                   |
           (Autenticação / Token)                    (Túnel Overlay / PTY)
                     |                                   |
                     v                                   v
 +-------------------+-------------------+   +-----------+---------------+
 |            CLOUD                      |   |             AGENT             |
 |    (cloud_control_api)                |   |    (proxmox-manager-api)      |
 |  - Control Plane Central              |   |  - Executa no Proxmox VE      |
 |  - Orquestrador Headscale             |   |  - Gestão LXC & Métricas      |
 |  - Emissão de Tokens & Conexões       |   |  - Server PTY / Node Tailscale|
 +-------------------+-------------------+   +-----------+---------------+
                     |                                   |
                     +---- (Sync Estado / Heartbeat) ----+
```

---

## ☁️ 1. CLOUD (`cloud_control_api`)

### 1.1 Estado Atual
* **Objetivo do Projeto:**  
  Atuar como o **Plano de Controle Centralizado (Control Plane / SaaS)**. Gerencia usuários, organizações, ambientes, permissões e orquestra a malha de rede overlay via Headscale (Tailscale controller), autorizando a comunicação entre clientes e nós/agentes.
* **O que faz hoje:**
  * Autenticação e autorização de usuários e agentes.
  * Cadastro e controle de Ambientes (`Environments`).
  * Registro de nós (`Published Nodes`) e containers publicados pelos agentes.
  * Integração com Headscale para provisionamento de `preauth_keys`, gerenciamento de usuários Headscale e registro de nós na rede overlay.
  * Emissão e resolução de tokens de conexão (`connection_tokens`) para autenticar o acesso dos clientes aos containers.
  * Registro de auditoria de conexões (`connection_audit`).
* **Responsabilidades:**
  * Gestão de identidade e autorização.
  * Orquestração de Rede Overlay (Headscale API/CLI integration).
  * Inventário centralizado de infraestrutura publicada.
  * Emissão e validação de credenciais de sessão.
* **Como conversa com os outros projetos:**
  * **Com o Agent:** Recebe chamadas REST dos agentes para registro de nó, heartbeat, sincronização de containers e autenticação.
  * **Com o Client:** Expõe rotas REST para autenticação do usuário, listagem de ambientes/containers autorizados e geração de tokens de conexão.
  * **Com o Headscale:** Executa chamadas HTTP / wrappers CLI para gerenciar a malha Tailscale/Headscale.

---

### 1.2 Qualidade da Arquitetura
* **Organização das Pastas:** Excelente segmentação modular (`app/api/`, `app/controllers/`, `app/services/`, `app/models/`, `app/repositories/`, `app/dto/`, `app/integrations/`).
* **Separação de Responsabilidades:** Clara. Controllers lidam apenas com HTTP, Services contêm a lógica de negócio e Repositories cuidam da persistência com SQLAlchemy.
* **Acoplamento:** Moderado. Depende fortemente de chamadas síncronas ao Headscale durante o fluxo de provisionamento de conexões.
* **Reutilização de Código:** Elevada, utilizando DTOs Pydantic e base models SQLAlchemy.
* **Padrões Utilizados:** Service Layer, Repository Pattern, Dependency Injection (FastAPI `Depends`), DTO Pattern.
* **Problemas Reais Identificados:**
  1. ⚠️ **Duplicidade de diretórios de DTO:** Existem as pastas `app/dto` e `app/dtos` simultaneamente, gerando ambiguidade de imports e redundância.
  2. ⚠️ **Integração Síncrona com Headscale:** Falhas ou lentidões na API do Headscale causam timeout na requisição do cliente no Cloud. Falta tratamento assíncrono com retry/circuit-breaker.
  3. ⚠️ **Sessões e Tokens Órfãos:** Se o cliente solicitar uma conexão e desconectar abruptamente antes do handshake final, o token/registro no banco pode permanecer em estado intermediário sem expiração automática.

---

### 1.3 O que ainda está faltando

#### **Essencial (MVP Sólido)**
* Worker/Mecanismo em background para **expiração e limpeza automática de conexões e tokens órfãos** (Garbage Collector de sessões).
* Tratamento de exceções e fallback gracioso no serviço de integração com Headscale.

#### **Desejável (Futuro)**
* Sistema de permissões RBAC refinado por container/tag dentro do mesmo ambiente.
* Webhooks para auditoria externa ou notificações de status de rede.

---

### 1.4 Dívida Técnica
* **Refatoração:** Unificar as pastas `app/dto` e `app/dtos`.
* **Tratamento de Erros:** Centralizar as exceções personalizadas de integração Headscale/Rede.
* **Banco de Dados:** Criar índices nas colunas de consulta frequente (`agent_id`, `user_id`, `token_hash`, `status`).

---

### 1.5 Maturidade do Projeto: **80%**
> **Justificativa:** O core de autenticação, sincronização de containers e emissão de chaves Headscale está consolidado e funcional. Faltam resiliência na comunicação com o Headscale e expurgo automático de sessões expiradas.

---

## 🤖 2. AGENT (`proxmox-manager-api`)

### 2.1 Estado Atual
* **Objetivo do Projeto:**  
  Executar diretamente no nó ou cluster Proxmox VE. Atua como o braço operacional local, gerenciando o ciclo de vida de containers LXC, provisionando nós Tailscale locais, gerando sessões de console PTY via WebSockets e reportando o estado da infraestrutura local ao Cloud.
* **O que faz hoje:**
  * Comunicação com Proxmox VE API (criação, início, parada, destruição e métricas de LXC).
  * Provisionamento de Tailscale local nos containers/host.
  * Emissão e validação de tokens de acesso local (`access`).
  * PTY Terminal / Console interativo em tempo real via WebSockets (`console`).
  * Sincronização e publicação automática do inventário de containers para o Cloud Control Plane (`cloud`).
  * Coleta de métricas do sistema e containers (`monitoring`).
* **Responsabilidades:**
  * Executar operações de infraestrutura no Proxmox VE local.
  * Gerenciar PTYs e sessões interativas dos usuários.
  * Manter o estado da rede overlay no nó.
  * Notificar o Cloud sobre o estado real dos containers.
* **Como conversa com os outros projetos:**
  * **Com o Proxmox VE:** Comunica via HTTP REST API do Proxmox / CLI local (`pct`, `pvesh`).
  * **Com o Cloud:** Envia heartbeats, sincroniza a lista de containers e valida credenciais via chamadas REST/WebSocket.
  * **Com o Client:** Recebe conexões de WebSocket diretas (ou tuneladas) para streaming de terminal PTY e validação de tokens de acesso.

---

### 2.2 Qualidade da Arquitetura
* **Organização das Pastas:** Muito bem segmentado por domínios funcionais (`access/`, `cloud/`, `console/`, `tailscale/`, `provision/`, `integrations/`, `monitoring/`).
* **Separação de Responsabilidades:** Excelente no isolamento de PTY/WebSockets e comandos Tailscale.
* **Acoplamento:** Moderado a alto dentro do serviço central de containers.
* **Reutilização de Código:** Uso de repositórios e serviços específicos por domínio.
* **Padrões Utilizados:** Service/Manager Pattern, Event Bus assíncrono para jobs de longa duração, WebSocket Handlers para streaming PTY.
* **Problemas Reais Identificados:**
  1. ⚠️ **Monolito de Serviço de Container:** O arquivo `app/services/container_service.py` possui acúmulo de responsabilidades (criação, edição, validação Proxmox, atualização de rede e métricas num único arquivo extenso de ~30KB).
  2. ⚠️ **Reconciliação no Boot (Startup Sync):** Na inicialização do Agent, o banco SQLite local precisa reconciliar o estado real dos containers no Proxmox VE **antes** de disparar o sync com o Cloud, evitando enviar dados desatualizados ao Cloud após um reboot.
  3. ⚠️ **Gerenciamento de Processos PTY Órfãos:** Se a conexão WebSocket do terminal for interrompida bruscamente pelo cliente sem sinal de `CLOSE`, o processo subjacente do PTY precisa garantir encerramento via timeout no SO local.

---

### 2.3 O que ainda está faltando

#### **Essencial (MVP Sólido)**
* Fluxo atômico de reconciliação de inicialização (**Startup Auto-Sync Proxmox VE ↔ Agent DB ↔ Cloud**).
* *Encerramento gracioso (Graceful shutdown)* garantido para matar subprocessos PTY ativos quando o agente for parado.

#### **Desejável (Futuro)**
* Suporte ao gerenciamento de VMs (QEMU/KVM), além dos containers LXC.
* Gestão de Snapshots/Backups de containers via API.

---

### 2.4 Dívida Técnica
* **Refatoração:** Fatiar o `container_service.py` em serviços especializados (ex: `container_lifecycle_service`, `container_metrics_service`).
* **Logs:** Adicionar logs estruturados auditáveis para aberturas de console e execução de comandos administrativos.

---

### 2.5 Maturidade do Projeto: **85%**
> **Justificativa:** O Agent é a peça mais madura da plataforma. A comunicação com Proxmox VE, gerenciamento de Tailscale e streaming de terminal PTY via WebSockets estão funcionando com alta estabilidade.

---

## 💻 3. CLIENT (`client` Go/Wails & `proxmox-manager-app` React)

### 3.1 Estado Atual
* **Objetivo do Projeto:**  
  Prover a interface de usuário final (Desktop GUI e CLI). Permite que os usuários se autentiquem no Cloud, visualizem seus ambientes/containers, estabeleçam túneis de rede seguros (Tailscale/SOCKS5), gerenciem redirecionamento de portas (*port forwarding*) e acessem o terminal dos containers.
* **O que faz hoje:**
  * **Modo CLI (Go):** Comando `connect <token>` para conexão via linha de comando.
  * **Modo GUI Desktop (Go + Wails + React):** Interface desktop completa com gerenciamento de **multi-sessões**, lista de ambientes/containers, criação e ativação de **Port Forwardings isolados por container**, terminal interativo (Xterm.js) e controle de credenciais.
  * **Motor de Rede Local:** Inicia daemon local do Tailscale, dialer SOCKS5 e proxy de portas locais.
  * **Dashboard Frontend (`proxmox-manager-app`):** Interface em React 18, Tailwind CSS, Shadcn/UI, Lucide Icons, React Query e Zustand.
* **Responsabilidades:**
  * Autenticação e gestão de sessão do usuário no Desktop.
  * Orquestração de processos locais (Tailscale daemon / SOCKS5 proxy).
  * Mapeamento e tunelamento de portas locais para os containers remotos.
  * Interface gráfica responsiva e amigável.
* **Como conversa com os outros projetos:**
  * **Com o Cloud:** Consome a API REST para login, obtenção de tokens de conexão, listagem de ambientes e registro de heartbeat de sessão.
  * **Com o Agent:** Conecta-se via rede privada (Tailscale/SOCKS5) e via WebSockets para a sessão do console PTY.
  * **Internamente (Go ↔ React):** Comunicação bidirecional via Wails Bridge (`internal/bridge`).

---

### 3.2 Qualidade da Arquitetura
* **Organização das Pastas:** Excelente tanto no Go (`internal/app`, `internal/bridge`, `internal/forwarding`, `internal/session`, `internal/tailscale`, `internal/runtime`) quanto no React (`src/components`, `src/features`, `src/hooks`, `src/stores`, `src/services`).
* **Separação de Responsabilidades:** Claríssima. O Go trata puramente de rede, processos de SO, túneis e persistência local; o React cuida exclusivamente de renderização, UX e gerenciamento de estado visual.
* **Acoplamento:** Muito baixo. A ponte Wails desacopla completamente a lógica do SO da camada visual.
* **Reutilização de Código:** Alta. Componentes de UI modulares e desacoplados.
* **Padrões Utilizados:** Clean Architecture / Use Cases no Go (`ConnectUseCase`), State Management via Zustand, Data Fetching via React Query, Bridge Pattern no Wails.
* **Problemas Reais Identificados:**
  1. ⚠️ **Detecção de Conflito de Portas Locais:** Ao ativar um Port Forwarding (ex: mapear porta local `8080`), se a porta já estiver em uso por outro programa no computador do usuário, o binding pode falhar sem uma mensagem explicativa na UI.
  2. ⚠️ **Resiliência na Persistência JSON Local:** O armazenamento local de sessões e forwarding (`JSONStorage`) grava diretamente em arquivo. Em caso de desligamento repentino do computador, exige salvamento atômico (escrita em arquivo temporário + rename) para prevenir corrupção do JSON.
  3. ⚠️ **Tratamento de Oscilação de Rede:** Se a conexão de internet do cliente cair momentaneamente, o túnel SOCKS5/Tailscale precisa disparar reconexão automática transparente com aviso visual de "Reconectando...".

---

### 3.3 O que ainda está faltando

#### **Essencial (MVP Sólido)**
* Verificação prévia de disponibilidade da porta local no Port Forwarding.
* Escrita atômica nos arquivos de persistência JSON do Client (`.tmp` -> `rename`).
* Reconexão automática graciosa do túnel de rede em oscilações de sinal.

#### **Desejável (Futuro)**
* Notificações nativas do SO (Toast nativo ao conectar/desconectar).
* Exportação/Importação de perfis de forwarding configurados.

---

### 3.4 Dívida Técnica
* **UX/Rede:** Feedback visual amigável quando o processo local necessitar de privilégios de administrador/rede no sistema operacional (Linux/Windows).
* **Limpeza de Recursos:** Garantir o fechamento de listeners SOCKS5 locais no evento de encerramento do app Wails.

---

### 3.5 Maturidade do Projeto: **75%**
> **Justificativa:** O Client evoluiu muito rápido recentemente com suporte a multi-sessão e port forwarding isolado. Está extremamente bem estruturado, faltando apenas ajustes de resiliência com o SO (conflito de portas, escrita atômica e reconexão de rede).

---

## 📊 4. Matriz e Estimativa de Maturidade

| Projeto | Maturidade | Principais Fortalezas | Pontos Críticos para Produção |
|---|---|---|---|
| **Agent (`proxmox-manager-api`)** | **85%** | Integração Proxmox VE funcional, PTY WebSockets estável, gerador de Tailscale local. | Startup Auto-sync atômico e refatoração do `container_service.py`. |
| **Cloud (`cloud_control_api`)** | **80%** | Autenticação, gestão de ambientes, integração Headscale e emissão de tokens. | Resiliência na API do Headscale e Garbage Collector de sessões/tokens órfãos. |
| **Client (`client` + `front`)** | **75%** | Wails + React limpo, multi-sessão, port forwarding isolado e console Xterm.js. | Detecção de portas ocupadas no SO, escrita atômica no JSON local e auto-reconexão. |

---

## 🛠️ 5. Dívida Técnica Consolidada

| Categoria | Projeto(s) Afetado(s) | Descrição do Item de Dívida Técnica | Severidade |
|---|---|---|---|
| **Estrutura** | Cloud | Unificação dos diretórios `app/dto` e `app/dtos` para evitar duplicidade de imports. | Média |
| **Resiliência** | Cloud | Tratamento com retry/circuit-breaker na comunicação síncrona com Headscale. | Alta |
| **Integridade** | Cloud | Garbage Collector / Background Task para expurgo de tokens/conexões órfãs. | Alta |
| **Concorrência** | Agent | Reconciliação atômica Proxmox VE ↔ Agent DB ↔ Cloud na inicialização do serviço. | Alta |
| **Refatoração** | Agent | Decomposição do `container_service.py` (~30KB) em serviços especializados. | Média |
| **Estabilidade SO** | Client | Verificação prévia de porta livre no SO antes de ativar Port Forwardings. | Alta |
| **Persistência** | Client | Gravação atômica em arquivos de storage JSON (`.tmp` + `rename`) contra corrupção. | Alta |
| **Rede/UX** | Client | Reconexão automática transparente em caso de queda temporária da internet. | Média |

---

## 🛤️ 6. Roadmap e Ordem Recomendada de Evolução

Para caminhar da fase de **protótipo avançado** para **produção sólida**, o desenvolvimento deve focar estritamente em **Estabilidade, Confiabilidade de Rede, Resiliência e Segurança**, evitando adicionar novas features antes de consolidar o core.

```
 +-----------------------------------------------------------------+
 | FASE 1: Estabilização de Estado & Sync Atômico (Agent & Cloud)  |
 +-----------------------------------------------------------------+
                                  |
                                  v
 +-----------------------------------------------------------------+
 | FASE 2: Resiliência de Rede & Concorrência de SO (Client)       |
 +-----------------------------------------------------------------+
                                  |
                                  v
 +-----------------------------------------------------------------+
 | FASE 3: Infraestrutura em VPS & Hardening de Segurança          |
 +-----------------------------------------------------------------+
                                  |
                                  v
 +-----------------------------------------------------------------+
 | FASE 4: Testes de Carga, Observabilidade & Polimento de UX      |
 +-----------------------------------------------------------------+
```

### 🔹 FASE 1: Estabilização de Estado & Sync Atômico (Curto Prazo)
1. **Agent — Startup Reconciliation Sync:**
   * Garantir que no boot do Agent, a reconciliação Proxmox VE ↔ SQLite do Agent ↔ Cloud DB aconteça de forma atômica antes de liberar tráfego de conexões.
2. **Cloud — Unificação de DTOs & Expurgador de Conexões:**
   * Unificar as pastas `app/dto` e `app/dtos`.
   * Criar worker para limpeza periódica de sessões e tokens desconectados ou expirados.

---

### 🔹 FASE 2: Resiliência de Rede & Concorrência de SO (Client)
3. **Client — Validação de Portas Locais & Escrita Atômica:**
   * Implementar checagem de disponibilidade de porta no SO antes de iniciar listeners no Port Forwarding.
   * Usar salvamento atômico nos arquivos de storage JSON do Client local.
4. **Client & Agent — Heartbeat & Auto-reconexão:**
   * Adicionar retry com indicador visual de "Reconectando..." na UI durante instabilidades na internet.

---

### 🔹 FASE 3: Infraestrutura, VPS e Deploy Real
5. **Deploy do Cloud & Headscale em VPS de Produção:**
   * Subir a **Cloud Control API** + **Headscale** em VPS (ex: Hetzner / AWS / DigitalOcean).
   * Configurar HTTPS/TLS (Let's Encrypt) para APIs e WebSockets.
6. **Hardening de Segurança e Auditoria:**
   * Revisar segredos em variáveis de ambiente e encriptação end-to-end de sockets PTY/SOCKS5.

---

### 🔹 FASE 4: Testes de Carga, Observabilidade & Polimento
7. **Testes de Integração Ponta a Ponta (E2E):**
   * Cobertura automatizada para a jornada: *Login → Selecionar Ambiente → Obter Token → Conectar Client → Abrir Terminal/Forwarding → Desconectar*.
8. **Logging Estruturado Centralizado:**
   * Implementar logs estruturados JSON para fácil integração com observabilidade (Grafana/Loki).

---

## 🛑 7. Componentes Maduros (Congelados para Novas Features)

Estes componentes já alcançaram a qualidade e estabilidade necessárias para o MVP e **não devem receber novas funcionalidades no próximo ciclo**:

* 🛑 **Interface Visual & Layout (`proxmox-manager-app`):** O dashboard React com Tailwind, Shadcn/UI, Lucide Icons e Xterm.js está maduro, responsivo e funcional.
* 🛑 **Integração Core com Proxmox VE (LXC):** O módulo de gerenciamento básico de LXC no Agent (criar, parar, iniciar, métricas) atende 100% da necessidade do MVP.
