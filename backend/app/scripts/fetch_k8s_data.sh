#!/bin/bash
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# fetch_k8s_data.sh â€” Fetch live Kubernetes cluster data
# Saves all resources to data/raw/ as JSON files
#
# Usage (from backend/ directory):
#   bash scripts/fetch_k8s_data.sh
#   bash scripts/fetch_k8s_data.sh --context minikube
#   bash scripts/fetch_k8s_data.sh --namespace default
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"


# â”€â”€ Defaults â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
CONTEXT=""
NAMESPACE="--all-namespaces"
OUTPUT_DIR="$REPO_ROOT/data/raw"
TIMEOUT=30
KUBECTL_BIN="${KUBECTL_BIN:-}"

# â”€â”€ Parse arguments â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
while [[ "$#" -gt 0 ]]; do
    case $1 in
        --context)   CONTEXT="--context $2";   shift ;;
        --namespace) NAMESPACE="--namespace $2"; shift ;;
        --output)    OUTPUT_DIR="$2";            shift ;;
        *) echo "Unknown parameter: $1"; exit 1 ;;
    esac
    shift
done

# â”€â”€ Colors for output â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_ok()   { echo -e "${GREEN}  âœ“${NC} $1"; }
print_err()  { echo -e "${RED}  âœ—${NC} $1"; }
print_warn() { echo -e "${YELLOW}  âš ${NC} $1"; }
print_info() { echo -e "${BLUE}  â†’${NC} $1"; }

# â”€â”€ Header â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
echo ""
echo -e "${BLUE}â•”â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•—${NC}"
echo -e "${BLUE}â•‘     Attack Path Analyzer â€” K8s Fetch    â•‘${NC}"
echo -e "${BLUE}â•šâ•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•${NC}"
echo ""

# â”€â”€ Check kubectl is available â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
if [[ -z "$KUBECTL_BIN" ]]; then
    # On Windows shells (Git Bash/WSL interop), kubectl.exe usually has the
    # right kubeconfig/cert path behavior for Minikube.
    if command -v kubectl.exe &> /dev/null; then
        KUBECTL_BIN="kubectl.exe"
    elif command -v kubectl &> /dev/null; then
        KUBECTL_BIN="kubectl"
    fi
fi

if [[ -z "$KUBECTL_BIN" ]]; then
    print_err "kubectl not found. Install it from: https://kubernetes.io/docs/tasks/tools/"
    exit 1
fi

print_ok "kubectl found: $($KUBECTL_BIN version --client --short 2>/dev/null || echo 'installed')"
print_info "Using kubectl binary: ${KUBECTL_BIN}"

# â”€â”€ Check cluster is reachable â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
print_info "Checking cluster connectivity..."
if ! $KUBECTL_BIN $CONTEXT cluster-info &> /dev/null; then
    print_err "Cannot reach cluster. Is minikube running?"
    echo ""
    echo "  Start minikube:  minikube start"
    echo "  Check status:    minikube status"
    exit 1
fi

CURRENT_CONTEXT=$($KUBECTL_BIN $CONTEXT config current-context 2>/dev/null || echo "unknown")
print_ok "Connected to cluster: ${CURRENT_CONTEXT}"

# â”€â”€ Create output directory â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
mkdir -p "$OUTPUT_DIR"
print_ok "Output directory: $OUTPUT_DIR"
echo ""

# â”€â”€ Fetch function â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
fetch_resource() {
    local resource=$1
    local flags=$2
    local outfile="$OUTPUT_DIR/${resource}.json"

    printf "  Fetching %-25s " "${resource}..."

    if $KUBECTL_BIN $CONTEXT get $resource $flags -o json \
        --request-timeout="${TIMEOUT}s" \
        > "$outfile" 2>/dev/null; then

        COUNT=$(python3 -c "import json,sys; d=json.load(open('$outfile')); print(len(d.get('items',[])))" 2>/dev/null || echo "?")
        print_ok "${COUNT} items â†’ ${outfile}"
    else
        print_warn "Failed â€” saving empty list to ${outfile}"
        echo '{"apiVersion":"v1","items":[],"kind":"List"}' > "$outfile"
    fi
}

# â”€â”€ Fetch all resources â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
echo -e "${BLUE}Fetching cluster resources...${NC}"
echo ""

fetch_resource "pods"                "$NAMESPACE"
fetch_resource "serviceaccounts"     "$NAMESPACE"
fetch_resource "secrets"             "$NAMESPACE"
fetch_resource "roles"               "$NAMESPACE"
fetch_resource "clusterroles"        ""
fetch_resource "rolebindings"        "$NAMESPACE"
fetch_resource "clusterrolebindings" ""

echo ""

# â”€â”€ Summary â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
echo -e "${BLUE}Fetch complete. Summary:${NC}"
echo ""
TOTAL=0
for f in "$OUTPUT_DIR"/*.json; do
    resource=$(basename "$f" .json)
    count=$(python3 -c "import json; d=json.load(open('$f')); print(len(d.get('items',[])))" 2>/dev/null || echo "0")
    printf "  %-30s %s items\n" "$resource" "$count"
    TOTAL=$((TOTAL + count))
done
echo ""
print_ok "Total resources fetched: ${TOTAL}"

# â”€â”€ Next step â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
echo ""
echo -e "${YELLOW}Next steps:${NC}"
echo "  1. Set MOCK_MODE=false in your .env"
echo "  2. Run: python scripts/seed_graph.py"
echo "  3. Restart the backend server"
echo ""
