#!/usr/bin/env bash

set -uo pipefail

# Fetch Kubernetes RBAC + workload data and save it as raw JSON files
# expected by backend/app/services/ingestion_service.py.
#
# Usage:
#   bash scripts/fetch_k8s_data.sh
#   bash scripts/fetch_k8s_data.sh --context minikube
#   bash scripts/fetch_k8s_data.sh --output-dir /tmp/raw

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
OUTPUT_DIR="${REPO_ROOT}/data/raw"
KUBE_CONTEXT="${KUBE_CONTEXT:-minikube}"
KUBECTL_TIMEOUT="${KUBECTL_TIMEOUT:-30s}"
KUBECTL_BIN="${KUBECTL_BIN:-}"
MODE="${MODE:-presentation}"
TARGET_NAMESPACES="${TARGET_NAMESPACES:-}"
EXCLUDE_NAMESPACES="${EXCLUDE_NAMESPACES:-kube-system,kube-public,kube-node-lease,local-path-storage,ingress-nginx,kubernetes-dashboard,cert-manager,metallb-system}"
MAX_PODS="${MAX_PODS:-24}"
MAX_SECRETS="${MAX_SECRETS:-16}"
MAX_CLUSTERROLES="${MAX_CLUSTERROLES:-16}"
KEEP_DEFAULT_SA="${KEEP_DEFAULT_SA:-false}"

is_wsl() {
  [[ -n "${WSL_DISTRO_NAME:-}" || -n "${WSL_INTEROP:-}" ]]
}

if [[ -z "${KUBECTL_BIN}" ]]; then
  if is_wsl && command -v kubectl.exe >/dev/null 2>&1; then
    KUBECTL_BIN="kubectl.exe"
  else
    KUBECTL_BIN="kubectl"
  fi
fi

kubectl_cmd() {
  "${KUBECTL_BIN}" "$@"
}

usage() {
  cat <<EOF
Usage: $(basename "$0") [options]

Options:
  --context <name>      Kubernetes context to use (default: ${KUBE_CONTEXT})
  --output-dir <path>   Directory for raw JSON output (default: ${OUTPUT_DIR})
  --timeout <duration>  kubectl request timeout (default: ${KUBECTL_TIMEOUT})
  --kubectl-bin <cmd>   kubectl command to run (default: ${KUBECTL_BIN})
  --mode <name>         presentation | full (default: ${MODE})
  --namespaces <csv>    Explicit namespaces to include in presentation mode
  --exclude-ns <csv>    Namespaces to exclude (default: system namespaces)
  --max-pods <n>        Max pods in presentation mode (default: ${MAX_PODS})
  --max-secrets <n>     Max secrets in presentation mode (default: ${MAX_SECRETS})
  --max-clusterroles <n> Max clusterroles in presentation mode (default: ${MAX_CLUSTERROLES})
  --keep-default-sa     Keep default service accounts in presentation mode
  -h, --help            Show this help
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --context)
      [[ $# -lt 2 ]] && echo "Error: --context requires a value" >&2 && exit 1
      KUBE_CONTEXT="$2"
      shift 2
      ;;
    --output-dir)
      [[ $# -lt 2 ]] && echo "Error: --output-dir requires a value" >&2 && exit 1
      OUTPUT_DIR="$2"
      shift 2
      ;;
    --timeout)
      [[ $# -lt 2 ]] && echo "Error: --timeout requires a value" >&2 && exit 1
      KUBECTL_TIMEOUT="$2"
      shift 2
      ;;
    --kubectl-bin)
      [[ $# -lt 2 ]] && echo "Error: --kubectl-bin requires a value" >&2 && exit 1
      KUBECTL_BIN="$2"
      shift 2
      ;;
    --mode)
      [[ $# -lt 2 ]] && echo "Error: --mode requires a value" >&2 && exit 1
      MODE="$2"
      shift 2
      ;;
    --namespaces)
      [[ $# -lt 2 ]] && echo "Error: --namespaces requires a value" >&2 && exit 1
      TARGET_NAMESPACES="$2"
      shift 2
      ;;
    --exclude-ns)
      [[ $# -lt 2 ]] && echo "Error: --exclude-ns requires a value" >&2 && exit 1
      EXCLUDE_NAMESPACES="$2"
      shift 2
      ;;
    --max-pods)
      [[ $# -lt 2 ]] && echo "Error: --max-pods requires a value" >&2 && exit 1
      MAX_PODS="$2"
      shift 2
      ;;
    --max-secrets)
      [[ $# -lt 2 ]] && echo "Error: --max-secrets requires a value" >&2 && exit 1
      MAX_SECRETS="$2"
      shift 2
      ;;
    --max-clusterroles)
      [[ $# -lt 2 ]] && echo "Error: --max-clusterroles requires a value" >&2 && exit 1
      MAX_CLUSTERROLES="$2"
      shift 2
      ;;
    --keep-default-sa)
      KEEP_DEFAULT_SA="true"
      shift 1
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage >&2
      exit 1
      ;;
  esac
done

if [[ "${MODE}" != "presentation" && "${MODE}" != "full" ]]; then
  echo "Error: --mode must be either 'presentation' or 'full'." >&2
  exit 1
fi

if ! command -v "${KUBECTL_BIN}" >/dev/null 2>&1; then
  echo "Error: '${KUBECTL_BIN}' is not installed or not in PATH." >&2
  exit 1
fi

CONTEXTS_OUTPUT="$(kubectl_cmd config get-contexts -o name 2>&1)"
CONTEXTS_RC=$?
if [[ ${CONTEXTS_RC} -ne 0 ]]; then
  echo "Error: failed to read Kubernetes contexts using '${KUBECTL_BIN}'." >&2
  printf '%s\n' "${CONTEXTS_OUTPUT}" >&2
  exit 1
fi
AVAILABLE_CONTEXTS="$(printf '%s\n' "${CONTEXTS_OUTPUT}" | tr -d '\r')"

if ! printf '%s\n' "${AVAILABLE_CONTEXTS}" | grep -Fxq -- "${KUBE_CONTEXT}"; then
  echo "Error: Kubernetes context '${KUBE_CONTEXT}' not found." >&2
  echo "kubectl binary in use: ${KUBECTL_BIN}" >&2
  echo "Available contexts:" >&2
  printf '%s\n' "${AVAILABLE_CONTEXTS}" >&2
  exit 1
fi

CURRENT_CONTEXT="$(kubectl_cmd config current-context 2>/dev/null | tr -d '\r')"
if [[ "${CURRENT_CONTEXT}" != "${KUBE_CONTEXT}" ]]; then
  echo "Info: current context is '${CURRENT_CONTEXT}'. Fetching from '${KUBE_CONTEXT}'."
fi

mkdir -p "${OUTPUT_DIR}"
TMP_DIR="$(mktemp -d 2>/dev/null || mktemp -d -t k8sfetch)"
RAW_FULL_DIR="${TMP_DIR}/full"
mkdir -p "${RAW_FULL_DIR}"
trap 'rm -rf "${TMP_DIR}"' EXIT

echo "Saving Kubernetes data to: ${OUTPUT_DIR}"
echo "Using context: ${KUBE_CONTEXT}"
echo "Using kubectl: ${KUBECTL_BIN}"
echo "Mode: ${MODE}"

SUCCESS_COUNT=0
FAIL_COUNT=0

write_empty_items_file() {
  local out_file="$1"
  printf '{ "items": [] }\n' > "${out_file}"
}

fetch_cluster_resource() {
  local out_name="$1"
  local resource="$2"
  local out_file="${RAW_FULL_DIR}/${out_name}.json"

  echo "Fetching ${resource} -> ${out_name}.json"
  if kubectl_cmd --context "${KUBE_CONTEXT}" \
      --request-timeout="${KUBECTL_TIMEOUT}" \
      get "${resource}" -o json > "${out_file}"; then
    SUCCESS_COUNT=$((SUCCESS_COUNT + 1))
  else
    echo "Warning: failed to fetch '${resource}'. Writing empty fallback file." >&2
    write_empty_items_file "${out_file}"
    FAIL_COUNT=$((FAIL_COUNT + 1))
  fi
}

fetch_namespaced_resource() {
  local out_name="$1"
  local resource="$2"
  local out_file="${RAW_FULL_DIR}/${out_name}.json"

  echo "Fetching ${resource} (-A) -> ${out_name}.json"
  if kubectl_cmd --context "${KUBE_CONTEXT}" \
      --request-timeout="${KUBECTL_TIMEOUT}" \
      get "${resource}" -A -o json > "${out_file}"; then
    SUCCESS_COUNT=$((SUCCESS_COUNT + 1))
  else
    echo "Warning: failed to fetch '${resource}'. Writing empty fallback file." >&2
    write_empty_items_file "${out_file}"
    FAIL_COUNT=$((FAIL_COUNT + 1))
  fi
}

fetch_namespaced_resource "pods" "pods"
fetch_namespaced_resource "serviceaccounts" "serviceaccounts"
fetch_namespaced_resource "roles" "roles"
fetch_cluster_resource "clusterroles" "clusterroles"
fetch_namespaced_resource "rolebindings" "rolebindings"
fetch_cluster_resource "clusterrolebindings" "clusterrolebindings"
fetch_namespaced_resource "secrets" "secrets"

copy_full_to_output() {
  cp "${RAW_FULL_DIR}"/*.json "${OUTPUT_DIR}/"
}

detect_python_bin() {
  local candidate
  for candidate in python3 python python.exe; do
    if command -v "${candidate}" >/dev/null 2>&1; then
      echo "${candidate}"
      return 0
    fi
  done
  return 1
}

run_presentation_filter() {
  local python_bin
  if ! python_bin="$(detect_python_bin)"; then
    echo "Warning: Python not found. Falling back to full dataset." >&2
    copy_full_to_output
    return 0
  fi

  RAW_IN_DIR="${RAW_FULL_DIR}" \
  RAW_OUT_DIR="${OUTPUT_DIR}" \
  TARGET_NAMESPACES="${TARGET_NAMESPACES}" \
  EXCLUDE_NAMESPACES="${EXCLUDE_NAMESPACES}" \
  MAX_PODS="${MAX_PODS}" \
  MAX_SECRETS="${MAX_SECRETS}" \
  MAX_CLUSTERROLES="${MAX_CLUSTERROLES}" \
  KEEP_DEFAULT_SA="${KEEP_DEFAULT_SA}" \
  "${python_bin}" - <<'PYCODE'
import json
import os
from pathlib import Path

RAW_IN_DIR = Path(os.environ["RAW_IN_DIR"])
RAW_OUT_DIR = Path(os.environ["RAW_OUT_DIR"])
TARGET_NAMESPACES = {ns.strip() for ns in os.environ.get("TARGET_NAMESPACES", "").split(",") if ns.strip()}
EXCLUDE_NAMESPACES = {ns.strip() for ns in os.environ.get("EXCLUDE_NAMESPACES", "").split(",") if ns.strip()}
MAX_PODS = int(os.environ.get("MAX_PODS", "24"))
MAX_SECRETS = int(os.environ.get("MAX_SECRETS", "16"))
MAX_CLUSTERROLES = int(os.environ.get("MAX_CLUSTERROLES", "16"))
KEEP_DEFAULT_SA = os.environ.get("KEEP_DEFAULT_SA", "false").lower() == "true"

HIGH_VALUE_CLUSTERROLES = {"cluster-admin", "admin", "edit", "view"}
SECRET_KEYWORDS = (
    "db", "database", "mysql", "postgres", "mongo", "redis",
    "credential", "creds", "password", "passwd", "token",
    "key", "admin", "prod", "root"
)

RAW_OUT_DIR.mkdir(parents=True, exist_ok=True)

def load_items(name: str) -> list:
    path = RAW_IN_DIR / f"{name}.json"
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as fh:
        data = json.load(fh)
    return list(data.get("items", []))

def write_items(name: str, items: list) -> None:
    path = RAW_OUT_DIR / f"{name}.json"
    with path.open("w", encoding="utf-8") as fh:
        json.dump({"items": items}, fh, indent=2)

def ns_of(item: dict, default: str = "default") -> str:
    return item.get("metadata", {}).get("namespace", default)

def name_of(item: dict, default: str = "unknown") -> str:
    return item.get("metadata", {}).get("name", default)

def role_is_risky(role: dict) -> bool:
    rules = role.get("rules", []) or []
    for rule in rules:
        verbs = set(rule.get("verbs", []) or [])
        resources = set(rule.get("resources", []) or [])
        if "*" in verbs or "*" in resources:
            return True
        if "secrets" in resources and ("get" in verbs or "list" in verbs or "*" in verbs):
            return True
        if "pods/exec" in resources and ("create" in verbs or "*" in verbs):
            return True
    return False

def pod_score(pod: dict) -> float:
    score = 0.0
    spec = pod.get("spec", {}) or {}
    status = pod.get("status", {}) or {}
    for container in spec.get("containers", []) or []:
        sc = container.get("securityContext", {}) or {}
        if sc.get("privileged"):
            score += 3.5
        if sc.get("allowPrivilegeEscalation"):
            score += 2.0
    psc = spec.get("securityContext", {}) or {}
    if psc.get("runAsUser") == 0 or psc.get("runAsNonRoot") is False:
        score += 1.5
    if spec.get("hostNetwork"):
        score += 2.0
    if spec.get("hostPID"):
        score += 2.0
    if spec.get("serviceAccountName", "default") != "default":
        score += 1.0
    if status.get("phase") == "Running":
        score += 0.5
    return score

def secret_score(secret: dict) -> float:
    name = name_of(secret, "").lower()
    secret_type = secret.get("type", "")
    score = 0.0
    for kw in SECRET_KEYWORDS:
        if kw in name:
            score += 1.0
    if secret_type == "kubernetes.io/service-account-token":
        score += 0.5
    return score

pods = load_items("pods")
serviceaccounts = load_items("serviceaccounts")
roles = load_items("roles")
clusterroles = load_items("clusterroles")
rolebindings = load_items("rolebindings")
clusterrolebindings = load_items("clusterrolebindings")
secrets = load_items("secrets")

if not TARGET_NAMESPACES:
    detected = {ns_of(pod) for pod in pods}
    TARGET_NAMESPACES = {ns for ns in detected if ns and ns not in EXCLUDE_NAMESPACES}
    if not TARGET_NAMESPACES:
        TARGET_NAMESPACES = {"default"}

pods_in_scope = [p for p in pods if ns_of(p) in TARGET_NAMESPACES]
pods_sorted = sorted(
    pods_in_scope,
    key=lambda p: (
        -pod_score(p),
        ns_of(p),
        name_of(p),
    ),
)
pods_kept = pods_sorted[:MAX_PODS]

selected_sas = set()
for pod in pods_kept:
    ns = ns_of(pod)
    sa = pod.get("spec", {}).get("serviceAccountName", "default")
    selected_sas.add((ns, sa))
selected_sas_from_pods = set(selected_sas)

rolebindings_scope = [rb for rb in rolebindings if ns_of(rb) in TARGET_NAMESPACES]
rolebindings_kept = []
selected_roles = set()
selected_clusterroles = set()

for rb in rolebindings_scope:
    rb_ns = ns_of(rb)
    subjects = rb.get("subjects", []) or []
    keep = False
    for subject in subjects:
        kind = subject.get("kind", "")
        name = subject.get("name", "")
        sub_ns = subject.get("namespace", rb_ns)
        if kind == "ServiceAccount":
            selected_sas.add((sub_ns, name))
            if (sub_ns, name) in selected_sas_from_pods or name != "default":
                keep = True
        elif kind == "User":
            keep = True
    if not keep:
        continue
    rolebindings_kept.append(rb)
    role_ref = rb.get("roleRef", {}) or {}
    role_name = role_ref.get("name", "")
    role_kind = role_ref.get("kind", "")
    if role_kind == "Role":
        selected_roles.add((rb_ns, role_name))
    elif role_kind == "ClusterRole":
        selected_clusterroles.add(role_name)

serviceaccounts_scope = [sa for sa in serviceaccounts if ns_of(sa) in TARGET_NAMESPACES]
serviceaccounts_kept = []
for sa in serviceaccounts_scope:
    sa_ns = ns_of(sa)
    sa_name = name_of(sa)
    if (sa_ns, sa_name) in selected_sas:
        serviceaccounts_kept.append(sa)
        continue
    if sa_name == "default" and KEEP_DEFAULT_SA:
        serviceaccounts_kept.append(sa)

roles_scope = [r for r in roles if ns_of(r) in TARGET_NAMESPACES]
roles_kept = []
for role in roles_scope:
    key = (ns_of(role), name_of(role))
    if key in selected_roles or role_is_risky(role):
        roles_kept.append(role)

clusterrolebindings_kept = []
for crb in clusterrolebindings:
    role_ref = crb.get("roleRef", {}) or {}
    role_name = role_ref.get("name", "")
    subjects = crb.get("subjects", []) or []
    keep = role_name in HIGH_VALUE_CLUSTERROLES
    for subject in subjects:
        kind = subject.get("kind", "")
        sub_ns = subject.get("namespace", "")
        if kind == "ServiceAccount" and sub_ns in TARGET_NAMESPACES:
            keep = True
            selected_sas.add((sub_ns, subject.get("name", "")))
    if keep:
        clusterrolebindings_kept.append(crb)
        selected_clusterroles.add(role_name)

clusterroles_prioritized = []
for cr in clusterroles:
    name = name_of(cr)
    if name in selected_clusterroles or name in HIGH_VALUE_CLUSTERROLES or role_is_risky(cr):
        clusterroles_prioritized.append(cr)

clusterroles_prioritized = sorted(
    clusterroles_prioritized,
    key=lambda cr: (
        0 if name_of(cr) in selected_clusterroles else 1,
        0 if name_of(cr) in HIGH_VALUE_CLUSTERROLES else 1,
        0 if role_is_risky(cr) else 1,
        name_of(cr),
    ),
)
clusterroles_kept = clusterroles_prioritized[:MAX_CLUSTERROLES]
clusterroles_kept_names = {name_of(cr) for cr in clusterroles_kept}

clusterrolebindings_kept = [
    crb for crb in clusterrolebindings_kept
    if (crb.get("roleRef", {}) or {}).get("name", "") in clusterroles_kept_names
]

secrets_scope = [s for s in secrets if ns_of(s) in TARGET_NAMESPACES]
secrets_ranked = sorted(
    secrets_scope,
    key=lambda s: (
        -secret_score(s),
        ns_of(s),
        name_of(s),
    ),
)
secrets_kept = [s for s in secrets_ranked if secret_score(s) > 0.0][:MAX_SECRETS]
if not secrets_kept:
    secrets_kept = secrets_ranked[: min(MAX_SECRETS, 6)]

write_items("pods", pods_kept)
write_items("serviceaccounts", serviceaccounts_kept)
write_items("roles", roles_kept)
write_items("clusterroles", clusterroles_kept)
write_items("rolebindings", rolebindings_kept)
write_items("clusterrolebindings", clusterrolebindings_kept)
write_items("secrets", secrets_kept)

summary = {
    "mode": "presentation",
    "namespaces": sorted(TARGET_NAMESPACES),
    "pods": len(pods_kept),
    "serviceaccounts": len(serviceaccounts_kept),
    "roles": len(roles_kept),
    "clusterroles": len(clusterroles_kept),
    "rolebindings": len(rolebindings_kept),
    "clusterrolebindings": len(clusterrolebindings_kept),
    "secrets": len(secrets_kept),
}
print(json.dumps(summary, indent=2))
PYCODE
}

if [[ "${MODE}" == "full" ]]; then
  copy_full_to_output
else
  run_presentation_filter
fi

echo
echo "Fetch complete: ${SUCCESS_COUNT} succeeded, ${FAIL_COUNT} failed."
echo "Files written under: ${OUTPUT_DIR}"

if [[ ${FAIL_COUNT} -gt 0 ]]; then
  echo "Some resources failed. You can still run the analyzer with partial data." >&2
  exit 2
fi

echo "All Kubernetes resources fetched successfully."
