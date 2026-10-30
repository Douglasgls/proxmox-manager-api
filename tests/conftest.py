import os
import base64
from unittest.mock import MagicMock, patch
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# 1. Configurar variáveis de ambiente essenciais para testes
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["AGENT_ENCRYPTION_KEY"] = base64.urlsafe_b64encode(b"a" * 32).decode()
os.environ["CLOUD_ENCRYPTION_KEY"] = base64.urlsafe_b64encode(b"b" * 32).decode()
os.environ["JWT_SECRET_KEY"] = "super-secret-jwt-key-with-sufficient-length-for-testing"
os.environ["JWT_ALGORITHM"] = "HS256"
os.environ["ACCESS_TOKEN_EXPIRE_MINUTES"] = "60"
os.environ["REFRESH_TOKEN_EXPIRE_DAYS"] = "7"
os.environ["CLOUD_URL"] = "https://cloud.test.example/api"

# 2. Configurar SQLite em memória compartilhado
import app.models
import app.cloud.models
from app.models.base import Base
import app.database.session as session_mod

test_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
Base.metadata.create_all(bind=test_engine)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

# Interceptar globalmente SessionLocal e engine da aplicação
session_mod.engine = test_engine
session_mod.SessionLocal = TestingSessionLocal

from app.main import app
from app.core.dependencies import get_db, get_proxmox_client
from app.models.user import User
from app.security.password import PasswordManager
from app.security.jwt import JWTManager
from app.core.settings import Settings


@pytest.fixture(scope="session")
def engine():
    return test_engine


@pytest.fixture(scope="function")
def db(engine):
    """Fornece uma sessão de banco de dados limpa para cada teste."""
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture(scope="function")
def client(db):
    """Cliente HTTP de teste para FastAPI com injeção de dependência do banco."""
    def override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app, raise_server_exceptions=True) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture(scope="function")
def password_manager():
    return PasswordManager()


@pytest.fixture(scope="function")
def jwt_manager():
    settings = Settings(
        jwt_secret_key=os.environ["JWT_SECRET_KEY"],
        jwt_algorithm=os.environ["JWT_ALGORITHM"],
        access_token_expire_minutes=60,
        refresh_token_expire_days=7,
    )
    return JWTManager(settings)


@pytest.fixture(scope="function")
def test_user(db, password_manager):
    """Cria e persiste um usuário de teste padrão."""
    user = User(
        username="admin_test",
        email="admin_test@example.com",
        password_hash=password_manager.hash("Secret123!"),
        is_active=True,
        role="admin",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture(scope="function")
def auth_token(test_user, jwt_manager):
    """Gera um JWT de acesso válido para o usuário de teste."""
    return jwt_manager.create_access_token(
        user_id=test_user.id,
        subject=test_user.username,
    )


@pytest.fixture(scope="function")
def auth_headers(auth_token):
    """Headers de autorização Bearer prontos para consumo."""
    return {"Authorization": f"Bearer {auth_token}"}


@pytest.fixture(scope="function")
def auth_client(client, auth_headers):
    """Wrapper para fazer chamadas HTTP autenticadas de forma conveniente."""
    class AuthenticatedClient:
        def __init__(self, c, headers):
            self.c = c
            self.headers = headers

        def get(self, url, **kwargs):
            headers = {**self.headers, **kwargs.pop("headers", {})}
            return self.c.get(url, headers=headers, **kwargs)

        def post(self, url, **kwargs):
            headers = {**self.headers, **kwargs.pop("headers", {})}
            return self.c.post(url, headers=headers, **kwargs)

        def put(self, url, **kwargs):
            headers = {**self.headers, **kwargs.pop("headers", {})}
            return self.c.put(url, headers=headers, **kwargs)

        def delete(self, url, **kwargs):
            headers = {**self.headers, **kwargs.pop("headers", {})}
            return self.c.delete(url, headers=headers, **kwargs)

    return AuthenticatedClient(client, auth_headers)


@pytest.fixture(scope="function")
def mock_proxmox():
    """Mock do ProxmoxClient para testes que necessitam interagir com Proxmox."""
    mock = MagicMock()
    mock.get_node_status.return_value = {"status": "online", "uptime": 12345}
    mock.list_containers.return_value = []
    return mock
