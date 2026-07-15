from app.components.base_components import BaseComponent

class BaseSystemComponent(BaseComponent):
    """
    Prepara o sistema operacional Debian/Ubuntu base do container.
    Configura locais (en_US.UTF-8), timezone (UTC), certificados CA e instala ferramentas básicas.
    """

    @property
    def name(self):
        return "base_system"

    def install(self, session):
        commands = [
            "export DEBIAN_FRONTEND=noninteractive",
            "apt-get update",
            "apt-get install -y --no-install-recommends curl wget ca-certificates apt-transport-https gnupg lsb-release software-properties-common locales tzdata bash-completion",
            "sed -i '/^# en_US.UTF-8 UTF-8/s/^# //' /etc/locale.gen",
            "locale-gen en_US.UTF-8 C.UTF-8",
            "update-locale LANG=en_US.UTF-8",
            "echo 'LANG=en_US.UTF-8' > /etc/default/locale",
            "echo 'LC_ALL=en_US.UTF-8' >> /etc/default/locale",
            "echo 'TERM=xterm-256color' >> /etc/default/locale",
            "update-ca-certificates",
            "ln -sf /usr/share/zoneinfo/UTC /etc/localtime",
            "dpkg-reconfigure -f noninteractive tzdata",
            "apt-get autoremove -y",
            "apt-get clean",
            "rm -rf /var/lib/apt/lists/*"
        ]

        full_command = " && ".join(commands)
        result = session.exec(full_command, timeout=300)

        if result.exit_code != 0:
            raise Exception(
                f"Erro instalando BaseSystemComponent:\n"
                f"stdout:\n{result.stdout}\n\n"
                f"stderr:\n{result.stderr}"
            )

        return "BaseSystemComponent instalado com sucesso."

    def validate(self, session):
        # 1. Validar curl
        res_curl = session.exec("curl --version", timeout=60)
        if res_curl.exit_code != 0:
            raise Exception(f"Validação falhou: curl não está funcionando. stdout: {res_curl.stdout}, stderr: {res_curl.stderr}")

        # 2. Validar wget
        res_wget = session.exec("wget --version", timeout=60)
        if res_wget.exit_code != 0:
            raise Exception(f"Validação falhou: wget não está funcionando. stdout: {res_wget.stdout}, stderr: {res_wget.stderr}")

        # 3. Validar locale & locales gerados
        res_locale = session.exec("locale", timeout=60)
        if res_locale.exit_code != 0:
            raise Exception(f"Validação falhou: comando 'locale' falhou. stderr: {res_locale.stderr}")
            
        res_locale_a = session.exec("locale -a", timeout=60)
        if res_locale_a.exit_code != 0:
            raise Exception(f"Validação falhou: comando 'locale -a' falhou. stderr: {res_locale_a.stderr}")
            
        if "en_US.utf8" not in res_locale_a.stdout and "en_US.UTF-8" not in res_locale_a.stdout:
            raise Exception(f"Validação falhou: locale en_US.utf8 não foi encontrado nos locales gerados: {res_locale_a.stdout}")

        # 4. Validar ca-certificates
        res_ca = session.exec("update-ca-certificates --verbose", timeout=60)
        if res_ca.exit_code != 0:
            raise Exception(f"Validação falhou: update-ca-certificates falhou. stdout: {res_ca.stdout}, stderr: {res_ca.stderr}")

        # 5. Validar timezone (UTC)
        res_tz = session.exec("cat /etc/timezone || readlink /etc/localtime || date", timeout=60)
        if "utc" not in res_tz.stdout.lower() and "utc" not in res_tz.stderr.lower():
            # Validação secundária via date
            res_date = session.exec("date +%Z", timeout=60)
            if "UTC" not in res_date.stdout:
                raise Exception(f"Validação falhou: timezone não está configurado para UTC. Timezone: {res_tz.stdout}, Date: {res_date.stdout}")

        return "BaseSystemComponent validado com sucesso."

    def rollback(self, session):
        # Remove apenas pacotes opcionais que foram instalados por este componente, poupando pacotes essenciais
        rollback_cmd = (
            "export DEBIAN_FRONTEND=noninteractive && "
            "apt-get purge -y apt-transport-https gnupg lsb-release software-properties-common bash-completion && "
            "apt-get autoremove -y"
        )
        session.exec(rollback_cmd, timeout=180)

    def metadata(self):
        return {
            "name": self.name,
            "description": "Prepara o sistema operacional Debian/Ubuntu base do container configurando locales (en_US.UTF-8), timezone (UTC), certificados CA e instalando ferramentas essenciais (curl, wget, gnupg, etc.) para viabilizar o provisionamento seguro dos outros componentes.",
            "version": "1.0.0",
        }

    def execute(self, session):
        pass
