# Dockerfile de interfaces (/uis/Dockerfile)
- Crea un Dockerfile en /uis/ basado en una imagen oficial de Node (Alpine). Debe instalar las dependencias de
/uis/website y /uis/backoffice por separado.
- El CMD por defecto del Dockerfile debe invocar un script start.sh que arranque ambas aplicaciones Next.js en puertos distintos (website en el 3000, backoffice en el 3001).
- Crea un .dockerignore en /uis/ que excluya al menos: node_modules .next env* y *.log.

# Dockerfile del backend (/services/Dockerfile)
- Crea un Dockerfile en /services/ basado en una imagen oficial de Python. Debe instalar uv, instalar las dependenciasd esde requirements.txt con uv pip install -r requirements.txt y arrancar el servidor Uvicorn con --reload habilitado.
- Crea un .dockerignore en /services/ que excluya al menos: pycache *.pyc, .env*, tests/ y *.log.

# Docker Compose (docker-compose.yml)
- Crea docker-compose.yml en la raíz con dos servicios: el servicio de interfaces (build desde /uis/, con bind mount sobre el código fuente y comando next dev para ambas apps) y el servicio de backend (build desde /services/, con bind mount y reload ).
- Expón los puertos correctos en cada servicio para que sean accesibles desde el host.
- Conecta ambos servicios en una red Docker con nombre definido explícitamente. Verifica que las URLs de conexión entre servicios usan el nombre del servicio como host, no localhost

- Define todas las variables de entorno de cada servicio mediante un archivo env en la raíz del repositorio (no hardcodeadas en el YAML).
- Confirma que env está en el .gitignore del repositorio.