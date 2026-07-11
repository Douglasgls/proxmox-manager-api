# Autenticação

Antes de iniciar a API, configure estas variáveis de ambiente:

- `JWT_SECRET_KEY`: segredo aleatório com pelo menos 32 bytes.
- `JWT_ALGORITHM`: `HS256`.
- `ACCESS_TOKEN_EXPIRE_MINUTES`: `15`.
- `REFRESH_TOKEN_EXPIRE_DAYS`: `7`.

Gere o segredo com `openssl rand -hex 32`. Não versione nem reutilize o segredo entre ambientes.
