from dataclasses import dataclass

# objetdo de dominio que representa a configuração de rede de um container
# não pertence nem ao banco nem a API é apenas uma logica de negócio.

@dataclass(frozen=True)
class OsTemplate:
    name: str
    filename: str
    distribution: str | None = None
    version: str | None = None
    architecture: str | None = None
    description: str | None = None
    storage: str | None = None
    downloaded: bool = False
    size: int | None = None
    source: str | None = None


    @property
    def volume_id(
        self,
    ) -> str | None:

        if not self.storage:
            return None

        return f"{self.storage}:vztmpl/{self.filename}"
