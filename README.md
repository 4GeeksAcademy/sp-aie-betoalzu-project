# Nexova Solutions — AI Engineering

Monorepositorio de herramientas para modernizar procesos de Nexova Solutions, consultora de recursos humanos y seleccion de talento. El proyecto combina aplicaciones web, servicios backend y componentes de datos e IA para resolver necesidades operativas concretas.

## Resumen ejecutivo

La primera solucion de producto es **Talent Pipeline Tracker**, una aplicacion para centralizar el seguimiento de candidaturas y reducir el uso de hojas de calculo desconectadas. El repositorio tambien incluye herramientas para gestionar incidencias, inventario y proveedores, consultar telemetria y generar reportes.

La plataforma incorpora una base para busqueda semantica con RAG sobre conocimiento de la empresa y un agente de soporte capaz de combinar ese contexto con consultas operativas. Estas capacidades dependen de la configuracion de Qdrant y de los proveedores externos correspondientes.

## Tecnologia

| Area | Tecnologias |
| --- | --- |
| Backoffice | Next.js 16 (App Router), React 19, TypeScript, Tailwind CSS 4 |
| Website | HTML/CSS y Tailwind CSS 4 |
| Backend y API | Python 3.11, FastAPI, Pydantic, SQLModel |
| Datos y reporting | SQLite/TinyDB, PostgreSQL (configurable), pandas, Prefect |
| IA y busqueda | Qdrant, RAG, LangGraph y proveedores compatibles con API OpenAI |
| Calidad y despliegue | pytest, ESLint, Docker Compose |

## Estructura del repositorio

```text
.
├── data_project/       # Procesamiento de conocimiento, RAG, pipelines y evaluacion
├── docs/               # Arquitectura, configuracion y documentacion funcional
├── packages/shared/    # Tipos compartidos
├── scripts/            # Scripts de carga y utilidades
├── services/           # API FastAPI, autenticacion, agente y servicios de dominio
├── tests/              # Pruebas automatizadas
├── uis/
│   ├── backoffice/     # Aplicacion Next.js para operaciones internas
│   └── website/        # Sitio web estatico
├── docker-compose.yml  # Orquestacion local de backend, Qdrant e interfaces
└── server.py           # Aplicacion FastAPI
```

## Requisitos

- Docker y Docker Compose v2.
- Un archivo `.env` en la raiz del repositorio. Docker Compose lo carga para el backend y las interfaces; configura como minimo `SECRET_KEY` para autenticacion.
- Para las funciones RAG y de agente que llaman a servicios externos, configura tambien las variables y credenciales de embeddings y del modelo generativo. Consulta [docs/rag/configuration.md](./docs/rag/configuration.md).

No guardes claves, tokens ni otros secretos en Git. Si no necesitas las funciones de IA externas, puedes dejar sin configurar sus credenciales; esas funciones no estaran disponibles.

## Levantar el proyecto con Docker

Desde la raiz:

```bash
# Crea .env y configura SECRET_KEY antes de iniciar los servicios.
docker compose up --build
```

Cuando los contenedores esten listos, abre:

- Website: <http://localhost:3000>
- Backoffice: <http://localhost:3001>
- API y documentacion interactiva: <http://localhost:8000/docs>
- Qdrant: <http://localhost:6333/dashboard>

Para detener los servicios, pulsa `Ctrl+C` o ejecuta:

```bash
docker compose down
```

Compose conserva los datos de Qdrant en un volumen Docker. No uses `docker compose down -v` salvo que quieras borrar tambien los datos persistidos.

### Codespaces

Si el backend no puede resolver los proveedores externos desde la red bridge de Docker, puedes iniciar el backend y Qdrant con la configuracion de red de Codespaces:

```bash
docker compose -f docker-compose.yml -f docker-compose.codespaces.yml up -d backend qdrant
```

La variante de Codespaces es opcional. Inicia solo `backend` y `qdrant`; para ejecutar las interfaces en este modo, arranca sus aplicaciones localmente y configura la URL del backend.

## Aplicaciones y capacidades

- **Talent Pipeline Tracker:** listado, busqueda y filtros de candidatos, edicion de etapas y estados, notas y formularios de alta.
- **Backoffice:** autenticacion y cuenta, proveedores, inventario, incidencias, analisis de incidentes, telemetria y reporting.
- **Website:** sitio web corporativo independiente del backoffice.
- **API:** endpoints para los dominios operativos, autenticacion, consultas de conocimiento, agente de soporte y reportes.
- **Datos e IA:** ingesta y recuperacion semantica de conocimiento, flujos de reporting y evaluaciones offline del agente.

## Desarrollo y validacion

El backoffice puede ejecutarse en modo desarrollo desde su directorio:

```bash
cd uis/backoffice
npm install
API_URL=http://localhost:8000 NEXT_PUBLIC_API_URL=http://localhost:8000 npm run dev
```

El backend debe estar disponible en `http://localhost:8000`; puedes iniciarlo con Docker o, teniendo Python 3.11 instalado, instalar sus dependencias y ejecutar:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r services/requirements.txt
export SECRET_KEY='configura-un-secreto-local'
uvicorn server:app --reload
```

Comprobaciones focalizadas:

```bash
python -m pytest
cd uis/backoffice && npm run lint
```

## Documentacion adicional

- [Configuracion de RAG](./docs/rag/configuration.md)
- [Diseno de RAG](./docs/rag/rag-design.md)
- [Propuesta de arquitectura](./docs/ARCHITECTURE_PROPOSAL.md)
