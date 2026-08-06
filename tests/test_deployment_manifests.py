"""Validates the deployment templates under deploy/ — YAML syntax, expected
document counts/kinds, and that the Dockerfiles/README exist and are
non-empty. Not a Docker/Kubernetes integration test (no daemon/cluster
required) — this only proves the templates are well-formed and self-
consistent, matching what a `docker compose config`/`kubectl apply
--dry-run` pass would additionally check in a real environment.
"""

from pathlib import Path

import yaml

from shared.paths import PROJECT_ROOT

_DEPLOY_DIR = PROJECT_ROOT / "deploy"


def test_deploy_directory_layout_exists() -> None:
    assert (_DEPLOY_DIR / "docker" / "Dockerfile.backend").is_file()
    assert (_DEPLOY_DIR / "docker" / "Dockerfile.frontend").is_file()
    assert (_DEPLOY_DIR / "compose" / "docker-compose.yml").is_file()
    assert (_DEPLOY_DIR / "kubernetes" / "deployment.yaml").is_file()
    assert (_DEPLOY_DIR / "kubernetes" / "service.yaml").is_file()
    assert (_DEPLOY_DIR / "kubernetes" / "configmap.yaml").is_file()
    assert (_DEPLOY_DIR / "README.md").is_file()


def test_dockerfiles_are_non_empty_and_reference_the_right_command() -> None:
    backend_dockerfile = (_DEPLOY_DIR / "docker" / "Dockerfile.backend").read_text()
    assert "uvicorn" in backend_dockerfile
    assert "backend.main:app" in backend_dockerfile

    frontend_dockerfile = (_DEPLOY_DIR / "docker" / "Dockerfile.frontend").read_text()
    assert "streamlit" in frontend_dockerfile
    assert "frontend/app.py" in frontend_dockerfile


def test_docker_compose_defines_both_services() -> None:
    doc = yaml.safe_load((_DEPLOY_DIR / "compose" / "docker-compose.yml").read_text())
    assert set(doc["services"]) == {"backend", "frontend"}
    assert doc["services"]["backend"]["build"]["dockerfile"] == "deploy/docker/Dockerfile.backend"
    assert doc["services"]["frontend"]["build"]["dockerfile"] == "deploy/docker/Dockerfile.frontend"


def test_kubernetes_deployment_defines_both_components_with_probes() -> None:
    docs = list(yaml.safe_load_all((_DEPLOY_DIR / "kubernetes" / "deployment.yaml").read_text()))
    assert len(docs) == 2
    names = {doc["metadata"]["name"] for doc in docs}
    assert names == {"insightpilot-backend", "insightpilot-frontend"}

    backend_doc = next(doc for doc in docs if doc["metadata"]["name"] == "insightpilot-backend")
    container = backend_doc["spec"]["template"]["spec"]["containers"][0]
    assert container["livenessProbe"]["httpGet"]["path"] == "/api/v1/operations/health"
    assert container["readinessProbe"]["httpGet"]["path"] == "/api/v1/operations/readiness"


def test_kubernetes_service_defines_both_components() -> None:
    docs = list(yaml.safe_load_all((_DEPLOY_DIR / "kubernetes" / "service.yaml").read_text()))
    assert len(docs) == 2
    names = {doc["metadata"]["name"] for doc in docs}
    assert names == {"insightpilot-backend", "insightpilot-frontend"}


def test_kubernetes_configmap_has_no_secrets_and_matches_settings_env_var_names() -> None:
    doc = yaml.safe_load((_DEPLOY_DIR / "kubernetes" / "configmap.yaml").read_text())
    assert doc["kind"] == "ConfigMap"
    # Every key must correspond to a real Settings field's environment variable
    # name (case-insensitive) — proves the manifest isn't inventing config
    # that config/settings.py wouldn't actually read.
    from config.settings import Settings

    known_upper = {name.upper() for name in Settings.model_fields}
    for key in doc["data"]:
        assert key.upper() in known_upper, f"ConfigMap key '{key}' has no matching Settings field."


def test_deploy_readme_documents_no_ci_cd_scope() -> None:
    content = (_DEPLOY_DIR / "README.md").read_text()
    assert "CI/CD" in content
    assert "template" in content.lower()


def _iter_yaml_files() -> list[Path]:
    return sorted(_DEPLOY_DIR.rglob("*.yaml")) + sorted(_DEPLOY_DIR.rglob("*.yml"))


def test_every_yaml_file_parses_cleanly() -> None:
    files = _iter_yaml_files()
    assert files, "expected at least one YAML manifest under deploy/"
    for path in files:
        list(yaml.safe_load_all(path.read_text()))  # raises on invalid YAML
