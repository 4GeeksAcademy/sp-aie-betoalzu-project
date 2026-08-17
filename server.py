try:
    from fastapi import FastAPI
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import FileResponse, HTMLResponse
    import uvicorn
except ImportError:
    print("You don't have FastAPI installed, run `$ pip3 install fastapi uvicorn` and try again")
    exit(1)

import os, subprocess

try:
    from services.api.incident_analyzer.routes import incidents_api as incident_analyzer_api
except (ImportError, ModuleNotFoundError):
    incident_analyzer_api = None

from services.api.incidents.routes import incidents_api as centralized_incidents_api
from services.api.suppliers.routes import suppliers_api
from services.api.users.routes import users_api
from services.api.profiles.routes import profiles_api

static_file_dir = os.path.join(os.path.dirname(os.path.realpath(__file__)), './')
app = FastAPI()

# CORS — allow the Next.js dev server and any local origin during development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

if incident_analyzer_api is not None:
    app.include_router(incident_analyzer_api)
app.include_router(centralized_incidents_api)
app.include_router(suppliers_api)
app.include_router(users_api)
app.include_router(profiles_api)

# Serving the index file
@app.get('/')
async def serve_dir_directory_index():
    if os.path.exists("app.py"):
        # if app.py exists we use the render function
        out = subprocess.Popen(['python3','app.py'], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        stdout,stderr = out.communicate()
        if out.returncode == 0:
            return HTMLResponse(content=stdout.decode('utf-8'))
        return HTMLResponse(content=f"<pre style='color: red;'>{stdout.decode('utf-8')}</pre>", status_code=500)
    if os.path.exists("index.html"):
        response = FileResponse(os.path.join(static_file_dir, 'index.html'))
        response.headers['Cache-Control'] = 'no-cache'
        return response
    else:
        return HTMLResponse(
            content="<h1 align='center'>404</h1><h2 align='center'>Missing index.html file</h2><p align='center'><img src='https://github.com/4GeeksAcademy/html-hello/blob/main/.vscode/rigo-baby.jpeg?raw=true' /></p>",
            status_code=404,
        )

# Serving any other image
@app.get('/{path:path}')
async def serve_any_other_file(path: str):
    full_path = os.path.join(static_file_dir, path)
    if not os.path.isfile(full_path):
        full_path = os.path.join(static_file_dir, path, 'index.html')

    if not os.path.isfile(full_path):
        return HTMLResponse(content="<h1 align='center'>404</h1>", status_code=404)

    response = FileResponse(full_path)
    response.headers['Cache-Control'] = 'no-cache'
    return response

if __name__ == '__main__':
    uvicorn.run(app, host='0.0.0.0', port=8000, reload=True)