from app.components.base_components import BaseComponent


class CurlComponent(BaseComponent):

    @property
    def name(self):
        return "curl"

    def install(self, session):
        teste = session.exec(
            "DEBIAN_FRONTEND=noninteractive apt-get install -y curl"
        )

        print("Curl installation result:", teste)

    def metadata(self):
        return {
            "name": self.name,
            "description": "Instala o curl no sistema.",
            "version": "1.0.0",
        }

    def rollback(self, session):
        session.exec(
            "DEBIAN_FRONTEND=noninteractive apt-get remove -y curl"
        )

    def validate(self, session):
        result = session.exec(
            "curl --version"
        )

        print("Curl validation result:", result)

        if result.exit_code != 0:
            raise Exception(
                f"Curl validation failed: {result.stderr}"
            )   

    def execute(self, session):

        result = session.exec(
            "echo 'Hello, World!'"
        )
        print("AQUI: ", result)
