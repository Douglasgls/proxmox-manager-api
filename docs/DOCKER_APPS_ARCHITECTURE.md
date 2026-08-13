# Arquitetura de Componentes Native + Docker Applications (Fase 1)

## 1. Visão Geral

Esta documentação descreve a arquitetura refinada de componentes do **Agent Proxmox Manager**, responsável pelo provisionamento declarativo e pela execução de aplicações nativas e via Docker dentro de containers LXC.

A arquitetura estabelece uma separação clara entre duas categorias exclusivas de componentes:

- **`native`**: Componentes de sistema instalados diretamente no sistema operacional do container LXC.
- **`docker_apps`**: Aplicações de usuário executadas isoladamente como containers Docker dentro do LXC.

---

## 2. Catálogo Ativo da Fase 1

### Componentes Nativos (`native`)
| Slug | Nome | Descrição |
| --- | --- | --- |
| `curl` | cURL | Utilitário de transferência de dados via URL |
| `git` | Git | Sistema de controle de versão distribuído |
| `tailscale` | Tailscale | Infraestrutura de rede mesh e VPN |

### Aplicação Docker (`docker_apps`)
| Slug | Nome | Imagem Docker | Container Name | Porta Padrão |
| --- | --- | --- | --- | --- |
| `filegator` | FileGator | `filegator/filegator` | `filegator-app` | `80` |

*Nota: O componente `python` e categorias legadas (`database`, `programming_language`) foram totalmente removidos nesta fase e serão reintroduzidos futuramente como componentes nativos.*

---

## 3. Nesting Global em LXC

Por padrão, todos os containers LXC gerenciados pelo sistema passam a ser criados com a funcionalidade **`nesting=1`** (`features: nesting=1`) ativada no Proxmox VE. Isso garante suporte nativo e sem atritos para execução do daemon Docker dentro de qualquer LXC instanciado.

---

## 4. Configuração Estruturada de Aplicações Docker

Ao solicitar uma aplicação Docker na criação de um container ou na instalação de componentes posteriores, a requisição suporta parâmetros estruturados de configuração:

```json
{
  "name": "meu-servidor-filegator",
  "password": "senha_segura",
  "components": [
    "curl",
    "git",
    {
      "slug": "filegator",
      "config": {
        "host": "0.0.0.0",
        "host_port": 8990,
        "container_port": 80,
        "restart_policy": "unless-stopped"
      }
    }
  ]
}
```

### Parâmetros Suportados:
- **`host`**: Endereço IP de escuta no LXC (`"0.0.0.0"` para rede externa ou `"127.0.0.1"` para escuta interna).
- **`host_port`**: Porta publicada pelo Docker no container LXC (ex: `8990`).
- **`container_port`**: Porta interna utilizada pela aplicação Docker (ex: `80`).
- **`restart_policy`**: Política de reinicialização do container Docker (`"no"`, `"unless-stopped"`, `"always"`).

---

## 5. Validação de Conflito de Portas

Antes de iniciar o provisionamento, o `ComponentService` valida se duas ou mais aplicações Docker no mesmo container LXC estão tentando utilizar o mesmo par de **`(host, host_port)`**. Em caso de colisão, a requisição é rejeitada preventivamente com um erro `DomainValidationError`.

---

## 6. Persistência de Configurações

A configuração utilizada na instalação de cada componente é persistida na coluna `config` (`JSON`) da tabela **`container_components`**:

```json
{
  "host": "0.0.0.0",
  "host_port": 8990,
  "container_port": 80,
  "restart_policy": "unless-stopped"
}
```

---

## 7. Preparação para a Próxima Fase (Templates Dinâmicos)

A arquitetura foi desenhada seguindo os princípios **SOLID** e os padrões **Registry** e **Template Method**. A classe base `DockerApplicationComponent` encapsula toda a lógica declarativa de:
1. Instalação e validação do runtime Docker;
2. Execução e inicialização idempotente do container (`docker run` / `docker start`);
3. Validação do estado de execução do container.

Em uma próxima fase, o cadastro dinâmico de novos templates pelo usuário reutilizará 100% desta infraestrutura sem necessidade de alterar o motor de provisionamento (`ProvisionEngine`).
