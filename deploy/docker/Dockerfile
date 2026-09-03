# Ruta opcional (Linux). Para Windows Server nativo ver deploy/windows/.
# Imagen única: compila el frontend y corre el backend Reflex.
FROM python:3.12-slim

# ODBC Driver 17 + dependencias
RUN apt-get update && apt-get install -y --no-install-recommends \
        curl gnupg2 apt-transport-https ca-certificates unixodbc-dev \
    && curl -fsSL https://packages.microsoft.com/keys/microsoft.asc | gpg --dearmor -o /usr/share/keyrings/microsoft.gpg \
    && echo "deb [signed-by=/usr/share/keyrings/microsoft.gpg] https://packages.microsoft.com/debian/12/prod bookworm main" > /etc/apt/sources.list.d/mssql.list \
    && apt-get update && ACCEPT_EULA=Y apt-get install -y msodbcsql17 \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY pyproject.toml requirements.txt ./
RUN pip install --no-cache-dir -e ".[web]" "psycopg[binary]"

COPY . .
# TLS 1.0 para SQL Server 2008 R2 (equivalente al hack de OPENSSL_CONF del legado)
RUN printf 'openssl_conf = default_conf\n[default_conf]\nssl_conf = ssl_sect\n[ssl_sect]\nsystem_default = system_default_sect\n[system_default_sect]\nMinProtocol = TLSv1\nCipherString = DEFAULT@SECLEVEL=0\n' > /etc/ssl/openssl_legacy.cnf
ENV OPENSSL_CONF=/etc/ssl/openssl_legacy.cnf

RUN reflex export --no-zip --frontend-only || reflex init

EXPOSE 8000 3000
CMD ["sh", "-c", "alembic upgrade head && reflex run --env prod"]
