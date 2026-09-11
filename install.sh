#!/bin/bash
set -e

# ============================================================
# Configuração da aplicação (Single Server Deployment)
# ============================================================

APP_NAME="agent-proxmox"

APP_DIR="/opt/$APP_NAME"
CONFIG_DIR="/etc/$APP_NAME"

BACKEND_DIR="$APP_DIR/backend"
FRONTEND_DIR="$BACKEND_DIR/static"

BACKEND_REPO="https://github.com/Douglasgls/proxmox-manager-api.git"
FRONTEND_RELEASE_URL="https://github.com/Douglasgls/proxmox-manager-app/releases/latest/download/dist.zip"

BACKEND_SERVICE="agent-proxmox.service"

BACKEND_PORT="8000"

DB_NAME="agent_proxmox"
DB_USER="agent_proxmox"

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
# PostgreSQL
# ============================================================

install_database() {
    log "Instalando PostgreSQL e dependências básicas..."
    apt-get update
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
            error "Usuário '$DB_USER' já existe, mas $DB_CONFIG_FILE não existe."
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
# Backend (FastAPI / Agent)
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

    JWT_SECRET_KEY=$(openssl rand -hex 64)

    cat > "$BACKEND_CONFIG_FILE" <<EOF
# Banco de dados
DATABASE_URL=$DATABASE_URL

# Criptografia interna
AGENT_ENCRYPTION_KEY=$AGENT_ENCRYPTION_KEY

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
    if command -v uv >/dev/null 2>&1; then
        log "uv já está instalado."
        return
    fi

    log "Instalando uv..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    if [ -x /root/.local/bin/uv ]; then
        install -m 0755 /root/.local/bin/uv /usr/local/bin/uv
    fi

    if ! command -v uv >/dev/null 2>&1; then
        error "Não foi possível instalar o uv."
    fi
    log "uv instalado com sucesso."
}

clone_backend() {
    log "Preparando backend..."
    if [ -d "$BACKEND_DIR/.git" ]; then
        log "Backend já existe. Atualizando..."
        cd "$BACKEND_DIR"
        git pull --ff-only
    else
        git clone "$BACKEND_REPO" "$BACKEND_DIR"
    fi
    log "Backend disponível em $BACKEND_DIR."
}

install_backend_dependencies() {
    log "Instalando dependências do backend..."
    cd "$BACKEND_DIR"
    uv python install 3.13
    uv sync --python 3.13
    log "Dependências instaladas."
}

run_database_migrations() {
    log "Executando migrations..."
    cd "$BACKEND_DIR"
    set -a
    source "$BACKEND_CONFIG_FILE"
    set +a
    uv run alembic upgrade head
    log "Migrations executadas com sucesso."
}

# ============================================================
# Frontend Estático
# ============================================================

install_frontend() {
    log "Instalando Frontend Estático..."
    mkdir -p "$FRONTEND_DIR"
    
    log "Fazendo download do artefato mais recente do frontend..."
    curl -sL "$FRONTEND_RELEASE_URL" -o /tmp/dist.zip
    
    # Extrair os arquivos
    unzip -o /tmp/dist.zip -d "$FRONTEND_DIR/"
    rm /tmp/dist.zip
}

# ============================================================
# Serviços e Finalização
# ============================================================

create_backend_service() {
    log "Criando serviço systemd do Agent..."

    cat > "/etc/systemd/system/$BACKEND_SERVICE" <<EOF
[Unit]
Description=Proxmox Manager Agent
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
    log "Iniciando Agent..."
    systemctl restart "$BACKEND_SERVICE"
    sleep 3

    if ! systemctl is-active --quiet "$BACKEND_SERVICE"; then
        journalctl -u "$BACKEND_SERVICE" --no-pager -n 50
        error "Agent não iniciou corretamente."
    fi
    log "Agent iniciado com sucesso."
}

check_backend_service() {
    log "Verificando Health Check do Agent..."
    if ! curl -fsS "http://127.0.0.1:$BACKEND_PORT/api/health" >/dev/null; then
        log "Health check via /api/health falhou (ou rota não existe). Tentando porta HTTP pura..."
        if ! curl -fsS "http://127.0.0.1:$BACKEND_PORT" >/dev/null; then
            error "Agent não está respondendo na porta $BACKEND_PORT."
        fi
    fi
    log "Health check OK."
}

install_agent() {
    log "========================================="
    log "Instalando Proxmox Manager Agent"
    log "========================================="

    install_uv
    clone_backend
    generate_backend_config
    install_backend_dependencies
    run_database_migrations
    create_backend_service
    start_backend_service
    check_backend_service
}

main() {
    check_root
    check_os
    prepare_directories
    get_server_ip

    # 1. Banco
    install_database_stack

    # 2. Frontend Estático
    install_frontend

    # 3. Agent (Backend)
    install_agent

    log "========================================="
    log "INSTALAÇÃO CONCLUÍDA"
    log "========================================="
    echo
    echo "Acesse o sistema no seu navegador:"
    echo
    echo "URL Principal: http://$SERVER_IP:$BACKEND_PORT"
    echo
}

main "$@"