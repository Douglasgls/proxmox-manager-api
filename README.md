# 🚀 Proxmox Manager API (Agent)

Uma API REST e serviço de agente construído em **FastAPI (Python)** para automação, gerenciamento e monitoramento local de containers LXC em nós ou clusters **Proxmox VE**, atuando de forma integrada com a malha de rede overlay e o plano de controle central (Cloud).

---

## 📌 1. O que é este projeto?

O **Proxmox Manager API** é o **Agente local** da plataforma. Ele é responsável por:
* **Gerenciamento do Ciclo de Vida de Containers LXC:** Criar, iniciar, parar, reiniciar e remover containers no Proxmox VE.
* **Terminal Interativo (Console PTY):** Expor streaming de terminal PTY em tempo real via WebSockets (Xterm.js).
* **Configuração de Rede:** Ajustar interfaces de rede (DHCP/Estático, Bridge, VLAN, MAC) nos containers.
* **Rede Overlay (Tailscale):** Provisionar e configurar o nó Tailscale diretamente dentro do ambiente/container.
* **Coleta de Métricas & Saúde:** Coletar uso de CPU, Memória, Disco e estatísticas de rede do Proxmox VE.
* **Sincronização com o Cloud:** Reconciliar o estado local e sincronizar o inventário de containers publicados com o Cloud Control Plane (`cloud_control_api`).

---

## 🛠️ 2. Como Rodar o Projeto

### Pré-requisitos
* **Python** `>= 3.13`
* Gerenciador de pacotes **`uv`** (recomendado) ou `pip`/`venv`.
* Servidor **Proxmox VE** acessível com permissões de API Token.
* Instância do **PostgreSQL** acessível para armazenar os dados locais do agente.

### Passo a Passo

1. **Clonar/Acessar o repositório:**
   ```bash
   cd proxmox-manager-api
   ```

2. **Instalar as dependências com `uv`:**
   ```bash
   uv sync
   ```

3. **Configurar as Variáveis de Ambiente (`.env`):**
   Crie o arquivo `.env` a partir do modelo fornecido:
   ```bash
   cp .env.example .env
   ```
   *(Edite o arquivo `.env` preenchendo as variáveis conforme explicado na seção abaixo).*

4. **Executar as Migrações do Banco de Dados (Alembic):**
   ```bash
   uv run alembic upgrade head
   ```

5. **Iniciar a Aplicação:**
   ```bash
   uv run uvicorn app.main:app --host 0.0.0.0 --port 8090 --reload
   ```

   A API estará acessível em: `http://localhost:8090`  
   Documentação Swagger disponível em: `http://localhost:8090/docs`

---

## 🔑 3. Configuração do `.env`

O arquivo `.env` armazena as credenciais de acesso, URLs e chaves secretas necessárias para que o Agente se comunique com o Proxmox VE, o Banco de Dados e o Cloud Control Plane.

### De onde vem cada informação?

#### 🗄️ **Banco de Dados (DATABASE_URL)**
* **De onde vem:** Do servidor PostgreSQL configurado para o Agente.
* **Formato:** `postgresql+psycopg://USUARIO:SENHA@HOST:PORTA/NOME_DO_BANCO`
* **Exemplo:** `postgresql+psycopg://admin:admin123@192.168.0.122:5432/proxmox`

---

#### 🖥️ **Proxmox VE (PROXMOX_*)**
Para obter os dados do Proxmox:
1. Acesse a interface web do seu Proxmox VE (`https://<IP-DO-PROXMOX>:8006`).
2. Vá em **Datacenter → API Tokens → Add**.
3. Crie um Token para o usuário (ex: `root@pam`) com ID/Name `localAPI`.
4. Copie a chave/Secret gerada (ela só é mostrada uma vez).

* **`PROXMOX_HOST`:** IP e porta da Web UI do Proxmox VE. (Ex: `192.168.0.122:8006`)
* **`PROXMOX_USER`:** Usuário e realm do Proxmox. (Ex: `root@pam`)
* **`PROXMOX_TOKEN_NAME`:** O nome do Token criado. (Ex: `localAPI`)
* **`PROXMOX_TOKEN_VALUE`:** O valor/UUID do Secret gerado na criação do Token no Proxmox.
* **`PROXMOX_NODE`:** O nome do nó do Proxmox VE. (Ex: `pve`)
* **`PROXMOX_DEFAULT_TEMPLATE`:** (Opcional) Caminho do template padrão de container LXC.
* **`PROXMOX_DEFAULT_STORAGE`:** (Opcional) Nome do storage do Proxmox onde os containers serão criados. (Ex: `local-lvm`)

---

#### 🔐 **Autenticação JWT (JWT_*)**
* **`JWT_SECRET_KEY`:** Chave secreta usada para assinar e validar tokens JWT locais.
  * *Como gerar:* Execute no terminal: `openssl rand -hex 32`
* **`JWT_ALGORITHM`:** Algoritmo de criptografia (padrão: `HS256`).
* **`ACCESS_TOKEN_EXPIRE_MINUTES`:** Tempo de expiração do Token de Acesso em minutos (ex: `15`).
* **`REFRESH_TOKEN_EXPIRE_DAYS`:** Tempo de expiração do Refresh Token em dias (ex: `7`).

---

#### ☁️ **Conexão com o Cloud Control Plane (CLOUD_*)**
* **`CLOUD_URL`:** URL base da API Cloud Control Plane. (Ex: `http://192.168.0.122:8000`)
* **`CLOUD_ENCRYPTION_KEY`:** Chave de criptografia compartilhada entre o Agent e o Cloud para troca segura de mensagens.

---

### 📄 Exemplo Prático de `.env`

```ini
# Configuração do Banco de Dados PostgreSQL (Local do Agent)
DATABASE_URL=postgresql+psycopg://usuario:senha@ip_do_banco:5432/nome_do_banco

# Configurações de Acesso à API do Proxmox VE
PROXMOX_HOST=192.168.0.100:8006
PROXMOX_USER=root@pam
PROXMOX_TOKEN_NAME=localAPI
PROXMOX_TOKEN_VALUE=seu-token-uuid-gerado-no-proxmox
PROXMOX_NODE=pve
PROXMOX_DEFAULT_TEMPLATE=local:vztmpl/ubuntu-22.04-standard_22.04-1_amd64.tar.zst
PROXMOX_DEFAULT_STORAGE=local-lvm

# Configurações de Autenticação JWT
JWT_SECRET_KEY=sua_chave_secreta_jwt_super_segura_aqui
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=15
REFRESH_TOKEN_EXPIRE_DAYS=7

# Conexão com o Cloud Control Plane
CLOUD_URL=http://192.168.0.200:8000
CLOUD_ENCRYPTION_KEY=sua_chave_de_criptografia_com_o_cloud
```

---

## 🧪 Testes

Para rodar a suíte de testes unitários e de integração:
```bash
uv run python -m unittest discover -s tests -p "test_*.py"
```