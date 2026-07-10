from app.components.base_components import BaseComponent




class GitComponent(BaseComponent):

    @property
    def name(self):
        return "git"

    def install(self, session):

        result = session.exec(
            "export DEBIAN_FRONTEND=noninteractive && "
            "apt-get update && "
            "apt-get install -y --no-install-recommends git",
            timeout=180,
        )

        if result.exit_code != 0:
            raise Exception(
                f"Erro instalando git:\n"
                f"stdout:\n{result.stdout}\n\n"
                f"stderr:\n{result.stderr}"
            )

        return "Git instalado."

    def validate(self, session):

        result = session.exec(
            "git --version",
            timeout=180,
        )

        if result.exit_code != 0:
            raise Exception(
                f"Git validation failed:\n"
                f"stdout:\n{result.stdout}\n\n"
                f"stderr:\n{result.stderr}"
            )

        return "Git validado."

    def metadata(self):
        return {
            "name": self.name,
            "description": "Instala o Git no sistema.",
            "version": "1.0.0",
        }

    def rollback(self, session):

        session.exec(
            "export DEBIAN_FRONTEND=noninteractive && "
            "apt-get remove -y git"
        )

    def execute(self, session):
        pass