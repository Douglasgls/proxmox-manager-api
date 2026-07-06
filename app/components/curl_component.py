from app.components.base_components import BaseComponent

class CurlComponent(BaseComponent):

    @property
    def name(self):
        return "curl"

    def install(self, session):

        result = session.exec(
            "export DEBIAN_FRONTEND=noninteractive && "
            "apt-get update && "
            "apt-get install -y --no-install-recommends curl",
            timeout=180,
        )

        if result.exit_code != 0:
            raise Exception(
                f"Erro instalando curl:\n"
                f"stdout:\n{result.stdout}\n\n"
                f"stderr:\n{result.stderr}"
            )

        return "Curl instalado."


    def validate(self, session):

        result = session.exec(
            "curl --version",
            timeout=180,
        )

        if result.exit_code != 0:
            raise Exception(
                f"Curl validation failed:\n"
                f"stdout:\n{result.stdout}\n\n"
                f"stderr:\n{result.stderr}"
            )

        return "Curl validado."

    def metadata(self):
        return {
            "name": self.name,
            "description": "Instala o curl no sistema.",
            "version": "1.0.0",
        }

    def rollback(self, session):

        session.exec(
            "export DEBIAN_FRONTEND=noninteractive && "
            "apt-get remove -y curl"
        )

    def execute(self, session):
        pass