# InsightPilot — Deployment Templates

These are **templates**, not a managed deployment pipeline. Nothing here
runs automatically, and there is no CI/CD wiring in this repository —
building images, pushing them to a registry, and applying manifests are
all manual steps you run yourself.

Everything under this directory is deliberately kept outside `backend/`
and `frontend/`: application code has zero Docker/Kubernetes-specific
logic in it (no `if os.environ.get("KUBERNETES_SERVICE_HOST")` branches
anywhere), and these files have zero Python in them. The only thing that
connects them is environment variables — every value a container needs
is something `config/settings.py` already reads via `os.environ` (through
`pydantic-settings`), so nothing here introduces a second configuration
mechanism.

## Layout

```
deploy/
├── docker/
│   ├── Dockerfile.backend      # uvicorn backend.main:app
│   └── Dockerfile.frontend     # streamlit run frontend/app.py
├── compose/
│   └── docker-compose.yml      # both services, one command, local/single-host
├── kubernetes/
│   ├── deployment.yaml         # two Deployments (backend, frontend)
│   ├── service.yaml            # two ClusterIP Services
│   └── configmap.yaml          # shared, non-secret environment configuration
└── README.md                   # this file
```

## Docker (build + run one image at a time)

From the repo root:

```bash
docker build -f deploy/docker/Dockerfile.backend -t insightpilot-backend .
docker build -f deploy/docker/Dockerfile.frontend -t insightpilot-frontend .

docker run -p 8000:8000 --env ACTIVE_PROFILE=production insightpilot-backend
docker run -p 8501:8501 --env BACKEND_URL=http://host.docker.internal:8000 insightpilot-frontend
```

## Docker Compose (both services together)

```bash
docker compose -f deploy/compose/docker-compose.yml up --build
```

- Backend: http://localhost:8000/docs
- Frontend: http://localhost:8501
- Backend readiness (what the compose healthcheck itself polls):
  http://localhost:8000/api/v1/operations/readiness

Override any default by exporting it before running, e.g.
`ACTIVE_PROFILE=staging LOG_LEVEL=DEBUG docker compose -f deploy/compose/docker-compose.yml up --build`.

## Kubernetes (template manifests)

1. Build and push both images to a registry your cluster can pull from,
   then edit `image:` in `deployment.yaml` to point at them (it defaults
   to local, unqualified image names — not something a real cluster can
   resolve on its own).
2. Apply, in any order:

```bash
kubectl apply -f deploy/kubernetes/configmap.yaml
kubectl apply -f deploy/kubernetes/deployment.yaml
kubectl apply -f deploy/kubernetes/service.yaml
```

3. The backend Deployment's liveness/readiness probes point directly at
   Phase 34's own operations endpoints
   (`/api/v1/operations/health`/`/api/v1/operations/readiness`) — no
   separate probe script. A pod only receives traffic once
   `StartupManager` has genuinely completed every startup stage; a pod
   whose `readinessProbe` never turns green is telling you exactly which
   stage failed (`kubectl exec` in and `curl localhost:8000/api/v1/operations/readiness`
   to see which one, and why).

## What's intentionally not here

Per this phase's own explicit scope: no authentication/authorization, no
distributed execution, no autoscaling (`HorizontalPodAutoscaler`, etc.),
and no CI/CD pipeline (GitHub Actions, ArgoCD, or otherwise). See the
main `README.md`'s "Plugin & Extension SDK" and "Operations Architecture"
sections for what each layer these manifests deploy actually does.
