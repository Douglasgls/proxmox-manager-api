import re
import unicodedata


def normalize_hostname(name: str | None) -> str:
    """Normaliza o nome do container para um hostname DNS válido (RFC 1123).

    Regras:
    1. Converte para minúsculas e remove acentuação.
    2. Substitui caracteres não alfanuméricos por hífen.
    3. Remove hífens duplicados e hífens nas extremidades.
    4. Trunca o resultado em no máximo 63 caracteres.
    5. Se o resultado for vazio, gera um fallback seguro.
    """
    if not name:
        return "ct-node"

    # Decompor caracteres acentuados e remover marcadores diacríticos
    normalized = unicodedata.normalize("NFKD", name)
    ascii_str = normalized.encode("ASCII", "ignore").decode("utf-8").lower()

    # Substituir qualquer caractere diferente de a-z, 0-9 por hífen
    sanitized = re.sub(r"[^a-z0-9]+", "-", ascii_str)

    # Remover hífens duplicados e hífens nas extremidades
    cleaned = re.sub(r"-+", "-", sanitized).strip("-")

    # Garante limite de 63 caracteres
    cleaned = cleaned[:63].strip("-")

    return cleaned if cleaned else "ct-node"
