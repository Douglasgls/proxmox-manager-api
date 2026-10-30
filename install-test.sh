#!/bin/bash
set -e

# ============================================================
# Configuração da aplicação (Ambiente de Testes - Branches: teste)
# ============================================================

APP_NAME="agent-proxmox-test"

APP_DIR="/opt/$APP_NAME"
CONFIG_DIR="/etc/$APP_NAME"

BACKEND_DIR="$APP_DIR/backend"
FRONTEND_DIR="$BACKEND_DIR/static"

BACKEND_REPO="https://github.com/Douglasgls/proxmox-manager-api.git"
BACKEND_BRANCH="teste"

FRONTEND_REPO="https://github.com/Douglasgls/proxmox-manager-app.git"
FRONTEND_BRANCH="teste"

BACKEND_SERVICE="agent-proxmox-test.service"

BACKEND_PORT="9000"

DB_NAME="agent_proxmox_test"
DB_USER="agent_proxmox_test"

DB_CONFIG_FILE="$CONFIG_DIR/database.env"
BACKEND_CONFIG_FILE="$CONFIG_DIR/backend.env"

# ============================================================
# Funções Utilitárias Base
# ============================================================

log() {
    echo -e "\n[INFO] $1"
}

error() {
    echo -e "\n[ERRO] $1"
    exit 1
}

check_root() {
    if [ "$EUID" -ne 0 ]; then
        error "Este script precisa ser executado como root (use sudo)."
    fi
}

check_os() {
    if ! grep -q -E "Debian|Proxmox|Ubuntu" /etc/os-release; then
        error "Este script foi feito para rodar em Debian / Proxmox VE."
    fi
}

prepare_directories() {
    log "Preparando diretórios base em $APP_DIR..."
    mkdir -p "$APP_DIR"
    mkdir -p "$CONFIG_DIR"
    chmod 750 "$CONFIG_DIR"
}

get_server_ip() {
    SERVER_IP=$(hostname -I | awk '{print $1}')

    if [ -z "$SERVER_IP" ]; then
        error "Não foi possível identificar o IP do servidor."
    fi

    log "IP do servidor detectado: $SERVER_IP"
}

# ============================================================
# Sincronização de Horário (NTP)
# ============================================================

sync_server_time() {
    log "========================================="
    log "Sincronização de Horário (NTP)"
    log "========================================="

    log "Garantindo sincronização de relógio via NTP..."

    # Garante que um daemon NTP esteja instalado (chrony ou systemd-timesyncd)
    if ! command -v chronyd >/dev/null 2>&1 && ! systemctl is-active --quiet systemd-timesyncd 2>/dev/null; then
        log "Instalando chrony para sincronização de relógio precisa..."
        apt-get update -y >/dev/null 2>&1 || true
        apt-get install -y chrony >/dev/null 2>&1 || apt-get install -y systemd-timesyncd >/dev/null 2>&1 || true
    fi

    # Ativa sincronização NTP no systemd
    timedatectl set-ntp true 2>/dev/null || true

    # Força a sincronização imediata do relógio
    if command -v chronyc >/dev/null 2>&1; then
        systemctl enable --now chrony >/dev/null 2>&1 || true
        chronyc makestep >/dev/null 2>&1 || true
    elif systemctl list-unit-files | grep -q systemd-timesyncd; then
        systemctl enable --now systemd-timesyncd >/dev/null 2>&1 || true
        systemctl restart systemd-timesyncd >/dev/null 2>&1 || true
    fi

    log "Status da sincronização de horário do servidor:"
    timedatectl status 2>/dev/null || date
}

# ============================================================
# PostgreSQL
# ============================================================

install_database() {
    log "Instalando PostgreSQL e dependências básicas..."
    # '|| true' previne que o script aborte caso repositórios do Proxmox Enterprise estejam sem licença e deem erro de GPG/Update
    apt-get update || true
    apt-get install -y postgresql postgresql-client openssl curl git unzip python3
    log "PostgreSQL e dependências instaladas."
}

init_database() {
    log "Iniciando PostgreSQL..."
    systemctl enable postgresql
    systemctl start postgresql

    if ! systemctl is-active --quiet postgresql; then
        error "Não foi possível iniciar o PostgreSQL."
    fi
    log "PostgreSQL está em execução."
}

create_database_user() {
    log "Configurando usuário do PostgreSQL..."

    if runuser -u postgres -- psql -tAc "SELECT 1 FROM pg_roles WHERE rolname='$DB_USER'" | grep -q 1; then
        log "Usuário '$DB_USER' já existe."
        if [ ! -f "$DB_CONFIG_FILE" ]; then
            log "Aviso: Usuário existe, mas o arquivo de configuração não foi encontrado. Gerando nova senha..."
            DB_PASS=$(openssl rand -base64 32 | tr -dc 'a-zA-Z0-9' | head -c 24)
            runuser -u postgres -- psql -c "ALTER USER $DB_USER WITH PASSWORD '$DB_PASS';"
            
            cat > "$DB_CONFIG_FILE" <<EOF
DATABASE_URL=postgresql+psycopg://$DB_USER:$DB_PASS@127.0.0.1:5432/$DB_NAME
EOF
            chmod 600 "$DB_CONFIG_FILE"
            log "Senha resetada e arquivo de configuração recriado."
        fi
        return
    fi

    DB_PASSWORD=$(openssl rand -hex 32)
    log "Criando usuário '$DB_USER'..."

    runuser -u postgres -- psql -c "CREATE USER $DB_USER WITH PASSWORD '$DB_PASSWORD';"

    cat > "$DB_CONFIG_FILE" <<EOF
DATABASE_URL=postgresql+psycopg://$DB_USER:$DB_PASSWORD@127.0.0.1:5432/$DB_NAME
EOF

    chmod 600 "$DB_CONFIG_FILE"
    log "Usuário criado."
}

create_database() {
    log "Configurando banco de dados..."

    if runuser -u postgres -- psql -tAc "SELECT 1 FROM pg_database WHERE datname='$DB_NAME'" | grep -q 1; then
        log "Banco '$DB_NAME' já existe."
        return
    fi

    runuser -u postgres -- createdb -O "$DB_USER" "$DB_NAME"
    log "Banco '$DB_NAME' criado."
}

grant_permissions() {
    log "Configurando permissões do Banco..."
    runuser -u postgres -- psql -d "$DB_NAME" -c "GRANT ALL PRIVILEGES ON DATABASE $DB_NAME TO $DB_USER;"
    runuser -u postgres -- psql -d "$DB_NAME" -c "GRANT ALL ON SCHEMA public TO $DB_USER;"
    log "Permissões configuradas."
}

check_database() {
    log "Verificando banco de dados..."

    if ! systemctl is-active --quiet postgresql; then
        error "PostgreSQL não está em execução."
    fi

    if ! runuser -u postgres -- psql -tAc "SELECT 1 FROM pg_database WHERE datname='$DB_NAME'" | grep -q 1; then
        error "Banco '$DB_NAME' não encontrado."
    fi

    if ! runuser -u postgres -- psql -tAc "SELECT 1 FROM pg_roles WHERE rolname='$DB_USER'" | grep -q 1; then
        error "Usuário '$DB_USER' não encontrado."
    fi

    log "Banco de dados verificado com sucesso."
}

install_database_stack() {
    log "========================================="
    log "Configurando PostgreSQL"
    log "========================================="
    install_database
    init_database
    create_database_user
    create_database
    grant_permissions
    check_database
    log "PostgreSQL configurado com sucesso."
}

# ============================================================
# Backend (FastAPI / Agent - Branch: teste)
# ============================================================

generate_backend_config() {
    log "Gerando configuração do backend..."

    if [ ! -f "$DB_CONFIG_FILE" ]; then
        error "Arquivo $DB_CONFIG_FILE não encontrado."
    fi

    source "$DB_CONFIG_FILE"

    if [ -z "$DATABASE_URL" ]; then
        error "DATABASE_URL não foi encontrada."
    fi

    if [ -f "$BACKEND_CONFIG_FILE" ]; then
        log "Configuração do backend já existe."
        return
    fi

    AGENT_ENCRYPTION_KEY=$(python3 - <<'PY'
import base64
import os
print(base64.urlsafe_b64encode(os.urandom(32)).decode())
PY
)

    if [ -z "$AGENT_ENCRYPTION_KEY" ]; then
        error "Não foi possível gerar AGENT_ENCRYPTION_KEY."
    fi

    CLOUD_ENCRYPTION_KEY=$(python3 - <<'PY'
import base64
import os
print(base64.urlsafe_b64encode(os.urandom(32)).decode())
PY
)

    if [ -z "$CLOUD_ENCRYPTION_KEY" ]; then
        error "Não foi possível gerar CLOUD_ENCRYPTION_KEY."
    fi

    JWT_SECRET_KEY=$(openssl rand -hex 64)

    # Configuração explícita do Cloud Control Plane
    CLOUD_URL="https://douglaspaz.site/api"

    cat > "$BACKEND_CONFIG_FILE" <<EOF
# Banco de dados
DATABASE_URL=$DATABASE_URL

# Criptografia interna e Nuvem
AGENT_ENCRYPTION_KEY=$AGENT_ENCRYPTION_KEY
CLOUD_ENCRYPTION_KEY=$CLOUD_ENCRYPTION_KEY

# Conexão com o Painel de Controle Cloud
CLOUD_URL=$CLOUD_URL

# JWT
JWT_SECRET_KEY=$JWT_SECRET_KEY
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=15
REFRESH_TOKEN_EXPIRE_DAYS=7
EOF

    chmod 600 "$BACKEND_CONFIG_FILE"
    log "Configuração do backend criada."
}

install_uv() {
    log "Verificando uv..."
    
    # O systemd espera o uv sempre em /usr/local/bin/uv
    if [ -x "/usr/local/bin/uv" ]; then
        log "uv já está instalado no diretório global esperado."
        return
    fi

    if command -v uv >/dev/null 2>&1; then
        UV_PATH=$(command -v uv)
        log "uv encontrado em $UV_PATH. Copiando para /usr/local/bin/uv..."
        install -m 0755 "$UV_PATH" /usr/local/bin/uv
        return
    fi

    log "Instalando uv..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    
    if [ -x /root/.local/bin/uv ]; then
        install -m 0755 /root/.local/bin/uv /usr/local/bin/uv
    fi

    if [ ! -x /usr/local/bin/uv ]; then
        error "Não foi possível colocar o uv em /usr/local/bin/uv."
    fi
    
    log "uv instalado com sucesso."
}

clone_backend() {
    log "Preparando backend (branch: $BACKEND_BRANCH)..."
    if [ -d "$BACKEND_DIR/.git" ]; then
        log "Backend já existe. Atualizando para a branch $BACKEND_BRANCH..."
        cd "$BACKEND_DIR"
        git fetch origin "$BACKEND_BRANCH"
        git checkout "$BACKEND_BRANCH"
        git reset --hard "origin/$BACKEND_BRANCH"
    else
        if [ -d "$BACKEND_DIR" ]; then
            log "Diretório do backend existe mas não é um repositório git. Recriando..."
            rm -rf "$BACKEND_DIR"
        fi
        git clone -b "$BACKEND_BRANCH" "$BACKEND_REPO" "$BACKEND_DIR"
    fi
    log "Backend disponível em $BACKEND_DIR na branch $BACKEND_BRANCH."
}

install_backend_dependencies() {
    log "Instalando dependências do backend..."
    cd "$BACKEND_DIR"
    /usr/local/bin/uv python install 3.13
    /usr/local/bin/uv sync --python 3.13
    log "Dependências instaladas."
}

run_database_migrations() {
    log "Executando migrations..."
    cd "$BACKEND_DIR"
    set -a
    source "$BACKEND_CONFIG_FILE"
    set +a
    /usr/local/bin/uv run alembic upgrade head
    log "Migrations executadas com sucesso."
}

# ============================================================
# Frontend Estático (Compilado da branch: teste)
# ============================================================

install_node() {
    log "Verificando Node.js para compilação do frontend..."
    if command -v node >/dev/null 2>&1 && command -v npm >/dev/null 2>&1; then
        NODE_MAJOR=$(node -v | tr -d 'v' | cut -d'.' -f1)
        if [ "$NODE_MAJOR" -ge 20 ]; then
            log "Node.js $NODE_MAJOR já está instalado."
            return
        fi
    fi

    log "Instalando Node.js 22 LTS via NodeSource..."
    curl -fsSL https://deb.nodesource.com/setup_22.x | bash -
    apt-get install -y nodejs
    log "Node.js instalado com sucesso: $(node -v)"
}

install_frontend() {
    log "Instalando Frontend Estático a partir da branch $FRONTEND_BRANCH..."
    install_node

    local FRONTEND_TEMP_DIR="/tmp/frontend_test_build"
    rm -rf "$FRONTEND_TEMP_DIR"
    mkdir -p "$FRONTEND_TEMP_DIR"

    log "Clonando frontend (branch: $FRONTEND_BRANCH)..."
    git clone --depth 1 -b "$FRONTEND_BRANCH" "$FRONTEND_REPO" "$FRONTEND_TEMP_DIR"

    cd "$FRONTEND_TEMP_DIR"
    log "Instalando dependências do frontend (npm install)..."
    npm install

    log "Configurando variáveis de ambiente do frontend..."
    echo "VITE_API_URL=/api" > .env.production
    echo "VITE_WS_URL=" >> .env.production

    log "Compilando frontend (npm run build)..."
    npm run build

    log "Copiando build para $FRONTEND_DIR..."
    mkdir -p "$FRONTEND_DIR"
    rm -rf "$FRONTEND_DIR"/*
    cp -r "$FRONTEND_TEMP_DIR/dist"/* "$FRONTEND_DIR/"

    rm -rf "$FRONTEND_TEMP_DIR"
    log "Frontend compilado e copiado para $FRONTEND_DIR com sucesso."
}

# ============================================================
# Serviços e Finalização
# ============================================================

create_backend_service() {
    log "Criando serviço systemd do Agent..."

    cat > "/etc/systemd/system/$BACKEND_SERVICE" <<EOF
[Unit]
Description=Proxmox Manager Agent (Test Branch)
After=network-online.target postgresql.service
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=$BACKEND_DIR
EnvironmentFile=$BACKEND_CONFIG_FILE
ExecStart=/usr/local/bin/uv run uvicorn app.main:app --host 0.0.0.0 --port $BACKEND_PORT
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

    systemctl daemon-reload
    systemctl enable "$BACKEND_SERVICE"
    log "Serviço criado."
}

start_backend_service() {
    log "Iniciando Agent ($BACKEND_SERVICE)..."
    systemctl restart "$BACKEND_SERVICE"
    log "Serviço acionado."
}

check_backend_service() {
    log "Aguardando e verificando Health Check do Agent na porta $BACKEND_PORT..."
    local max_attempts=20
    local attempt=1

    while [ $attempt -le $max_attempts ]; do
        if ! systemctl is-active --quiet "$BACKEND_SERVICE"; then
            echo ""
            journalctl -u "$BACKEND_SERVICE" --no-pager -n 50
            error "O serviço $BACKEND_SERVICE parou de responder durante a inicialização."
        fi

        if curl -fsS "http://127.0.0.1:$BACKEND_PORT/api/health" >/dev/null 2>&1 || curl -fsS "http://127.0.0.1:$BACKEND_PORT" >/dev/null 2>&1; then
            echo ""
            log "Health check OK! Agent respondendo com sucesso na porta $BACKEND_PORT."
            return 0
        fi

        echo -n "."
        sleep 2
        attempt=$((attempt + 1))
    done

    echo ""
    journalctl -u "$BACKEND_SERVICE" --no-pager -n 50
    error "Agent não respondeu na porta $BACKEND_PORT após 40 segundos de inicialização."
}

main() {
    check_root
    check_os
    prepare_directories
    get_server_ip
    sync_server_time

    # 1. Banco
    install_database_stack

    # 2. Prepara o Backend (Git Clone - branch teste)
    install_uv
    clone_backend

    # 3. Compila e instala o Frontend da branch teste
    install_frontend

    # 4. Configura, instala dependências e sobe o Agent (Backend)
    generate_backend_config
    install_backend_dependencies
    run_database_migrations
    create_backend_service
    start_backend_service
    check_backend_service

    log "========================================="
    log "INSTALAÇÃO DE TESTES CONCLUÍDA"
    log "========================================="
    echo
    echo "Acesse o sistema no seu navegador:"
    echo
    echo "URL Principal: http://$SERVER_IP:$BACKEND_PORT"
    echo
}

main "$@"
