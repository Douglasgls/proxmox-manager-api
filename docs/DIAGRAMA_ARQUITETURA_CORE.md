# 📘 Arquitetura Core e Fluxo de Conexão Passo a Passo

> **Documento de Referência da Arquitetura de Comunicação e Guia para o Frontend (Slides Interativos)**  
> **Componentes Principais:** `Cloud Control API (VPS)`, `Agent Proxmox (Servidor Local)` e `Client App (Dispositivo do Usuário)`.

---

## 📑 Sumário

1. [Resumo Executivo do Funcionamento](#-resumo-executivo-do-funcionamento)
2. [Atores e Papéis no Sistema](#-atores-e-papéis-no-sistema)
3. [Jornada Completa: Do Setup à Conexão P2P (6 Passos)](#-jornada-completa-do-setup-à-conexão-p2p-6-passos)
   - [Passo 1: Onboarding do Agent Proxmox](#passo-1-onboarding-do-agent-proxmox)
   - [Passo 2: Criação e Provisionamento do Container LXC](#passo-2-criação-e-provisionamento-do-container-lxc)
   - [Passo 3: Publicação e Geração do Token de Acesso](#passo-3-publicação-e-geração-do-token-de-acesso)
   - [Passo 4: Solicitação de Acesso pelo Cliente Remoto](#passo-4-solicitação-de-acesso-pelo-cliente-remoto)
   - [Passo 5: Validação de Segurança na VPS & Handshake](#passo-5-validação-de-segurança-na-vps--handshake)
   - [Passo 6: Conexão Direta P2P & Navegação Criptografada](#passo-6-conexão-direta-p2p--navegação-criptografada)
4. [Estrutura de Dados em Cada Passo (Guia de Implementação do Slider no Frontend)](#-estrutura-de-dados-em-cada-passo-guia-de-implementação-do-slider-no-frontend)

---

## 🌐 Resumo Executivo do Funcionamento

O objetivo do sistema é permitir que **usuários em redes externas (4G, Wi-Fi público, trabalho)** acessem **containers isolados no Proxmox VE local (ex: FileGator, PostgreSQL, Web Apps)** sem a necessidade de expor o servidor para a internet pública e **sem abrir portas no roteador (Zero Port Forwarding / Sem CGNAT)**.

### O "Segredo" da Arquitetura:
- **Plano de Controle (VPS / Nuvem):** Trata apenas de **Autenticação, Autorização e Orquestração de Tokens**. *Nenhum arquivo ou tráfego pesado do usuário passa pela VPS*.
- **Plano de Dados (Rede Overlay Mesh):** Uma vez autorizado pela VPS, o dispositivo do cliente abre um **túnel criptografado direto (P2P)** com o nó do container LXC dentro da rede local do Proxmox VE.

---

## 👥 Atores e Papéis no Sistema

```
  [ 💻 CLIENT APP ]                 [ ☁️ CLOUD CONTROL API (VPS) ]          [ 🖥️ AGENT PROXMOX + CONTAINER ]
Dispositivo do usuário final        Plano de Controle Centralizado         Servidor local de infraestrutura
(Notebook / Celular no 4G)          (Validação de Tokens & Permissões)     (Proxmox VE + LXC 100 FileGator)
```

1. **Cloud Control API (`VPS`):** O servidor central responsável por gerenciar organizações, emitir tokens criptográficos, auditar conexões e orquestrar as chaves de acesso (`KeyPubClient` e `KeyPubProx`).
2. **Agent Proxmox (`proxmox-manager-api`):** Serviço instalado no servidor Proxmox VE local. Ele gerencia o ciclo de vida dos containers LXC (`pct exec`), instala componentes (ex: FileGator, Tailscale Node) e sincroniza o estado da infraestrutura com a Cloud via conexões de saída (*outbound*).
3. **Client App (`teste-final-cloud-cliente` / Utilitário Desktop):** Aplicativo rodando na máquina do usuário final. Ele solicita tokens de conexão, envia suas chaves públicas para a VPS e levanta a interface de rede privada local para o tunelamento.

---

## 🔄 Jornada Completa: Do Setup à Conexão P2P (6 Passos)

Esta seção foi desenhada especificamente para alimentar o **Slide Interativo do Frontend (Passo 1 a Passo 6)**.

---

### Passo 1: Onboarding do Agent Proxmox
**"Conectando a Infraestrutura Local ao Plano de Controle"**

- **O que acontece:**
  1. O administrador instala o **Agent Proxmox** no seu servidor Proxmox VE local.
  2. O Agent utiliza uma chave de organização (`Organization Token`) para se registrar na **Cloud Control API (VPS)**.
  3. A VPS valida o cadastro e registra o novo **Ambiente (Environment)** (ex: *"Proxmox Casa"*).
  4. O Agent estabelece um canal seguro e persistente de sinalização de saída (*Outbound WebSocket TLS*) com a VPS.
- **Resultado:** O servidor local está online na nuvem, sem precisar de IP público fixo nem redirecionamento de portas.

---

### Passo 2: Criação e Provisionamento do Container LXC
**"Criando o Container com a Aplicação Desejada (ex: FileGator)"**

- **O que acontece:**
  1. No painel web da Cloud, o usuário clica para criar um novo container LXC.
  2. A VPS envia a ordem de criação para o **Agent Proxmox** via canal de sinalização.
  3. O **Agent Proxmox** executa chamadas nativas no host Proxmox VE (`pct create` / `pct start`).
  4. O *Provision Engine* do Agent instala automaticamente a aplicação selecionada (ex: **FileGator** para gerenciamento de arquivos) e o nó de rede overlay dentro do container.
- **Resultado:** Container LXC (ex: `LXC 100`) ativo e rodando a aplicação na rede privada local.

---

### Passo 3: Publicação e Geração do Token de Acesso
**"Definindo Quem Pode Acessar e Registrando a Chave Pública"**

- **O que acontece:**
  1. No painel, o administrador clica em **"Permitir Acesso / Gerar Token"** para o container do FileGator.
  2. O container gera seu par de chaves de rede privada (`KeyPubProx` e `KeyPrivProx`).
  3. O **Agent Proxmox** registra a chave pública do container (`KeyPubProx`) na **Cloud Control API (VPS)** junto com um **Token de Acesso Único (Connection Token)**.
  4. A VPS armazena a associação: `Token -> Container LXC + KeyPubProx + Permissões de Usuário`.
- **Resultado:** O token de acesso seguro está pronto para ser entregue ou utilizado pelo cliente autorizado.

---

### Passo 4: Solicitação de Acesso pelo Cliente Remoto
**"O Usuário no 4G Solicita a Conexão no Aplicativo Cliente"**

- **O que acontece:**
  1. O usuário final (estando na rua, em um café ou no 4G) abre o **Client App**.
  2. O usuário insere o **Token de Acesso** gerado ou seleciona o container "FileGator Casa" na sua lista de serviços autorizados.
  3. O **Client App** gera localmente o seu próprio par de chaves criptográficas de rede (`KeyPubClient` e `KeyPrivClient`).
- **Resultado:** O cliente possui a credencial (Token) e sua chave pública pronta para solicitar autorização de rede.

---

### Passo 5: Validação de Segurança na VPS & Handshake
**"A Nuvem Checa as Permissões e Entrega as Chaves de Conexão"**

- **O que acontece:**
  1. O **Client App** envia à **Cloud Control API (VPS)** o pacote: `Token de Acesso + KeyPubClient`.
  2. A VPS executa a validação rigorosa de segurança:
     - *O Token é válido e não está expirado?*
     - *Este usuário tem permissão para acessar este nó especificamente?*
     - *O Agent Proxmox correspondente está online?*
  3. Se aprovado, a VPS registra a `KeyPubClient` na regra de autorização da malha e responde ao cliente entregando a `KeyPubProx` do container e o endereço privado amigável (ex: `meus-arquivos.internal`).
- **Resultado:** O handshake foi autorizado pela nuvem. O cliente agora sabe como se conectar diretamente ao container.

---

### Passo 6: Conexão Direta P2P & Navegação Criptografada
**"Túnel Privado Estabelecido: Acesso Total sem Passar pela Nuvem"**

- **O que acontece:**
  1. Posse das chaves (`KeyPubClient` $\leftrightarrow$ `KeyPubProx`), o **Client App** e o **Container LXC** fecham um **Túnel de Rede Privada P2P (WireGuard/Tailscale)**.
  2. Todo o tráfego pesado de dados (upload/download de arquivos no FileGator) trafega **diretamente entre o notebook do usuário e o Proxmox de casa**.
  3. A VPS não atua como gargalo de banda nem lê os dados do usuário.
  4. O usuário abre o navegador em `http://meus-arquivos.internal` e acessa seus arquivos normalmente com **Zero Port Forwarding**.
- **Resultado:** **CONECTADO COM SUCESSO!** Acesso rápido, privado e 100% seguro.

---

## 📊 Estrutura de Dados em Cada Passo (Guia de Implementação do Slider no Frontend)

Caso você queira criar um componente de **Slide Interativo (Passo 1 ao 6)** no Vue (ex: `InteractiveDemo.vue`), você pode utilizar este JSON como fonte de dados para iterar entre os passos:

```json
[
  {
    "step": 1,
    "badge": "Passo 1 • Onboarding",
    "title": "Registro do Agent Proxmox",
    "subtitle": "Conexão de saída (outbound) mantida entre a infraestrutura local e a nuvem.",
    "actor_source": "Servidor Proxmox VE (Local)",
    "actor_target": "Cloud Control API (VPS)",
    "action_label": "Handshake de Registro de Ambiente",
    "status_text": "Agent Online na Nuvem",
    "icon": "server"
  },
  {
    "step": 2,
    "badge": "Passo 2 • Provisionamento",
    "title": "Criação do Container LXC (FileGator)",
    "subtitle": "O Agent executa comandos nativos (pct exec) e instala o gerenciador de arquivos.",
    "actor_source": "Cloud Control API",
    "actor_target": "Agent Proxmox (Local)",
    "action_label": "Executando Provision Engine -> LXC 100 (FileGator)",
    "status_text": "Container LXC Criado e Ativo",
    "icon": "box"
  },
  {
    "step": 3,
    "badge": "Passo 3 • Permissão",
    "title": "Publicação & Geração do Token",
    "subtitle": "A nuvem registra a chave pública do container (KeyPubProx) e emite um token único.",
    "actor_source": "Agent Proxmox (LXC 100)",
    "actor_target": "Cloud Control API (VPS)",
    "action_label": "Registrando KeyPubProx + Token de Conexão",
    "status_text": "Token de Acesso Pronto",
    "icon": "key"
  },
  {
    "step": 4,
    "badge": "Passo 4 • Solicitação Remota",
    "title": "Cliente Inicia o Acesso no 4G",
    "subtitle": "O usuário cola o token no aplicativo e gera localmente a sua chave pública (KeyPubClient).",
    "actor_source": "Notebook do Usuário (Rede Externa)",
    "actor_target": "Client App Local",
    "action_label": "Gerando KeyPubClient + Preparando Solicitação",
    "status_text": "Aguardando Autorização da VPS",
    "icon": "smartphone"
  },
  {
    "step": 5,
    "badge": "Passo 5 • Autenticação na VPS",
    "title": "Validação de Token e Handshake",
    "subtitle": "A VPS confirma que o token é válido, verifica permissões e devolve os dados de rede.",
    "actor_source": "Client App",
    "actor_target": "Cloud Control API (VPS)",
    "action_label": "Validação de Token & Troca de Chaves (KeyPubClient <-> KeyPubProx)",
    "status_text": "Acesso Autorizado pela Nuvem",
    "icon": "shield-check"
  },
  {
    "step": 6,
    "badge": "Passo 6 • Conexão P2P Direta",
    "title": "Túnel Privado & Navegação no FileGator",
    "subtitle": "Conexão direta criptografada entre o usuário e o container. Sem expor portas no roteador!",
    "actor_source": "Notebook do Usuário",
    "actor_target": "Container LXC (FileGator em Casa)",
    "action_label": "Túnel Criptografado P2P Ativo (http://meus-arquivos.internal)",
    "status_text": "CONECTADO COM SUCESSO!",
    "icon": "lock"
  }
]
```

---
*Documentação gerada para o projeto Proxmox Cloud.*
