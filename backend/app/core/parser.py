"""
parser.py — Kubernetes JSON Parser
Converts raw kubectl JSON output into a clean internal
list of nodes and edges ready for graph_builder.py.

Handles: pods, serviceaccounts, roles, clusterroles,
         rolebindings, clusterrolebindings, secrets.
"""

from app.utils.logger import get_logger
from app.utils.helpers import sanitize_k8s_name, risk_to_weight

logger = get_logger(__name__)


# ─── Node type constants ───────────────────────────────────────────────────────

class NodeType:
    POD             = "pod"
    SERVICE_ACCOUNT = "service_account"
    ROLE            = "role"
    SECRET          = "secret"
    DATABASE        = "database"
    USER            = "user"
    NAMESPACE       = "namespace"


# ─── Main parser ──────────────────────────────────────────────────────────────

def parse_cluster_data(raw: dict) -> dict:
    """
    Entry point. Accepts a dict of raw kubectl JSON blobs and
    returns a unified list of nodes and edges.

    Args:
        raw = {
            "pods":                <kubectl get pods -A -o json>,
            "serviceaccounts":     <kubectl get serviceaccounts -A -o json>,
            "roles":               <kubectl get roles -A -o json>,
            "clusterroles":        <kubectl get clusterroles -o json>,
            "rolebindings":        <kubectl get rolebindings -A -o json>,
            "clusterrolebindings": <kubectl get clusterrolebindings -o json>,
            "secrets":             <kubectl get secrets -A -o json>,
        }

    Returns:
        {
            "nodes": [ {id, label, type, risk, namespace, metadata}, ... ],
            "edges": [ {source, target, relation, risk, weight}, ... ],
        }
    """
    nodes = {}   # id -> node dict  (dedup by id)
    edges = []

    _parse_pods(raw.get("pods", {}), nodes, edges)
    _parse_serviceaccounts(raw.get("serviceaccounts", {}), nodes)
    _parse_roles(raw.get("roles", {}), nodes)
    _parse_roles(raw.get("clusterroles", {}), nodes, cluster_scoped=True)
    _parse_secrets(raw.get("secrets", {}), nodes, edges)
    _parse_rolebindings(raw.get("rolebindings", {}), nodes, edges)
    _parse_rolebindings(raw.get("clusterrolebindings", {}), nodes, edges, cluster_scoped=True)

    node_list = list(nodes.values())
    logger.info("Parsed %d nodes and %d edges from cluster data", len(node_list), len(edges))

    return {"nodes": node_list, "edges": edges}


# ─── Per-resource parsers ──────────────────────────────────────────────────────

def _parse_pods(data: dict, nodes: dict, edges: list) -> None:
    """
    Extract pod nodes and their serviceAccount edges.
    Pod → uses → ServiceAccount
    """
    for item in data.get("items", []):
        meta = item.get("metadata", {})
        spec = item.get("spec", {})
        status = item.get("status", {})

        name = meta.get("name", "unknown-pod")
        namespace = meta.get("namespace", "default")
        node_id = _make_id(NodeType.POD, name, namespace)

        risk = _pod_risk(spec, status)

        _add_node(nodes, node_id, {
            "id":        node_id,
            "label":     sanitize_k8s_name(name),
            "type":      NodeType.POD,
            "risk":      risk,
            "namespace": namespace,
            "metadata": {
                "image":            _get_images(spec),
                "host_network":     spec.get("hostNetwork", False),
                "host_pid":         spec.get("hostPID", False),
                "phase":            status.get("phase", "Unknown"),
                "privileged":       _is_privileged(spec),
                "run_as_root":      _runs_as_root(spec),
            },
        })

        # Edge: pod → uses → service account
        sa_name = spec.get("serviceAccountName", "default")
        sa_id = _make_id(NodeType.SERVICE_ACCOUNT, sa_name, namespace)
        _add_edge(edges, node_id, sa_id, "uses", risk=risk)


def _parse_serviceaccounts(data: dict, nodes: dict) -> None:
    for item in data.get("items", []):
        meta = item.get("metadata", {})
        name = meta.get("name", "unknown-sa")
        namespace = meta.get("namespace", "default")
        node_id = _make_id(NodeType.SERVICE_ACCOUNT, name, namespace)

        # default SA gets lower base risk; anything else slightly higher
        risk = 3.0 if name == "default" else 5.0

        _add_node(nodes, node_id, {
            "id":        node_id,
            "label":     name,
            "type":      NodeType.SERVICE_ACCOUNT,
            "risk":      risk,
            "namespace": namespace,
            "metadata":  {"secrets": [s.get("name") for s in item.get("secrets", [])]},
        })


def _parse_roles(data: dict, nodes: dict, cluster_scoped: bool = False) -> None:
    for item in data.get("items", []):
        meta = item.get("metadata", {})
        rules = item.get("rules", [])
        name = meta.get("name", "unknown-role")
        namespace = meta.get("namespace", "cluster" if cluster_scoped else "default")
        node_id = _make_id(NodeType.ROLE, name, namespace)

        risk = _role_risk(rules, name)

        _add_node(nodes, node_id, {
            "id":        node_id,
            "label":     name,
            "type":      NodeType.ROLE,
            "risk":      risk,
            "namespace": namespace,
            "metadata": {
                "cluster_scoped": cluster_scoped,
                "rules":          rules,
                "rule_count":     len(rules),
                "has_wildcard":   _has_wildcard(rules),
            },
        })


def _parse_secrets(data: dict, nodes: dict, edges: list) -> None:
    for item in data.get("items", []):
        meta = item.get("metadata", {})
        name = meta.get("name", "unknown-secret")
        namespace = meta.get("namespace", "default")
        secret_type = item.get("type", "Opaque")
        node_id = _make_id(NodeType.SECRET, name, namespace)

        risk = _secret_risk(name, secret_type)

        _add_node(nodes, node_id, {
            "id":        node_id,
            "label":     name,
            "type":      NodeType.SECRET,
            "risk":      risk,
            "namespace": namespace,
            "metadata": {
                "secret_type":   secret_type,
                "is_db_creds":   _looks_like_db_creds(name),
                "is_tls":        secret_type == "kubernetes.io/tls",
                "is_token":      secret_type == "kubernetes.io/service-account-token",
            },
        })

        # If it looks like DB credentials, also create a database node
        if _looks_like_db_creds(name):
            db_id = _make_id(NodeType.DATABASE, f"db-{name}", namespace)
            _add_node(nodes, db_id, {
                "id":        db_id,
                "label":     f"db-inferred-from-{sanitize_k8s_name(name)}",
                "type":      NodeType.DATABASE,
                "risk":      9.0,
                "namespace": namespace,
                "metadata":  {"inferred": True, "source_secret": name},
            })
            # Secret -> exposes -> inferred database
            _add_edge(edges, node_id, db_id, "exposes", risk=max(risk, 8.5))


def _parse_rolebindings(
    data: dict, nodes: dict, edges: list, cluster_scoped: bool = False
) -> None:
    """
    Extract edges from role bindings:
        ServiceAccount → bound-to → Role
        Role           → can-read → Secret  (inferred from role rules)
    """
    for item in data.get("items", []):
        meta = item.get("metadata", {})
        role_ref = item.get("roleRef", {})
        subjects = item.get("subjects", [])
        namespace = meta.get("namespace", "cluster" if cluster_scoped else "default")

        role_name = role_ref.get("name", "unknown-role")
        role_ns = "cluster" if cluster_scoped else namespace
        role_id = _make_id(NodeType.ROLE, role_name, role_ns)

        # Ensure the role node exists (may not have been in roles list)
        if role_id not in nodes:
            _add_node(nodes, role_id, {
                "id":        role_id,
                "label":     role_name,
                "type":      NodeType.ROLE,
                "risk":      _role_risk([], role_name),
                "namespace": role_ns,
                "metadata":  {"cluster_scoped": cluster_scoped, "inferred": True},
            })

        for subject in subjects:
            subject_kind = subject.get("kind", "")
            subject_name = subject.get("name", "unknown")
            subject_ns = subject.get("namespace", namespace)

            if subject_kind == "ServiceAccount":
                sa_id = _make_id(NodeType.SERVICE_ACCOUNT, subject_name, subject_ns)
                if sa_id not in nodes:
                    _add_node(nodes, sa_id, {
                        "id":        sa_id,
                        "label":     subject_name,
                        "type":      NodeType.SERVICE_ACCOUNT,
                        "risk":      5.0,
                        "namespace": subject_ns,
                        "metadata":  {"inferred": True},
                    })
                # SA → bound-to → Role
                binding_risk = nodes[role_id]["risk"]
                _add_edge(edges, sa_id, role_id, "bound-to", risk=binding_risk)

            elif subject_kind == "User":
                user_id = _make_id(NodeType.USER, subject_name, subject_ns)
                if user_id not in nodes:
                    _add_node(nodes, user_id, {
                        "id":        user_id,
                        "label":     subject_name,
                        "type":      NodeType.USER,
                        "risk":      4.0,
                        "namespace": subject_ns,
                        "metadata":  {},
                    })
                _add_edge(edges, user_id, role_id, "bound-to", risk=4.0)

        # Infer Role -> can-read -> Secret edges when role rules allow secret access.
        role_rules = nodes.get(role_id, {}).get("metadata", {}).get("rules", [])
        if _can_read_secrets(role_rules) or _has_wildcard(role_rules):
            for secret in nodes.values():
                if secret.get("type") != NodeType.SECRET:
                    continue
                if not cluster_scoped and secret.get("namespace") != namespace:
                    continue
                _add_edge(
                    edges,
                    role_id,
                    secret["id"],
                    "can-read",
                    risk=max(nodes[role_id].get("risk", 5.0), secret.get("risk", 5.0)),
                )


# ─── Risk Scoring Helpers ──────────────────────────────────────────────────────

def _pod_risk(spec: dict, status: dict) -> float:
    """
    Score a pod's risk based on security misconfigurations.
    Each flag adds to a base score of 3.0, capped at 10.0.
    """
    score = 3.0
    if _is_privileged(spec):       score += 3.0
    if spec.get("hostNetwork"):    score += 1.5
    if spec.get("hostPID"):        score += 1.5
    if _runs_as_root(spec):        score += 1.0
    if status.get("phase") == "Running": score += 0.5
    return min(round(score, 1), 10.0)


def _role_risk(rules: list, name: str) -> float:
    """
    Score a role's risk based on its permission rules.
    cluster-admin and wildcard roles are maximum risk.
    """
    if name in ("cluster-admin", "admin"):
        return 9.5
    score = 3.0
    if _has_wildcard(rules):       score += 4.0
    if _can_exec(rules):           score += 2.0
    if _can_read_secrets(rules):   score += 1.5
    if len(rules) > 10:            score += 0.5
    return min(round(score, 1), 10.0)


def _secret_risk(name: str, secret_type: str) -> float:
    """Score a secret's risk based on name patterns and type."""
    score = 4.0
    if _looks_like_db_creds(name): score += 3.5
    if secret_type == "kubernetes.io/service-account-token": score += 2.0
    if any(kw in name.lower() for kw in ("admin", "master", "root", "prod")): score += 1.5
    if secret_type == "kubernetes.io/tls": score += 1.0
    return min(round(score, 1), 10.0)


# ─── Rule Inspection Helpers ───────────────────────────────────────────────────

def _has_wildcard(rules: list) -> bool:
    return any(
        "*" in rule.get("verbs", []) or "*" in rule.get("resources", [])
        for rule in rules
    )

def _can_exec(rules: list) -> bool:
    return any("create" in rule.get("verbs", []) and "pods/exec" in rule.get("resources", [])
               for rule in rules)

def _can_read_secrets(rules: list) -> bool:
    return any("secrets" in rule.get("resources", []) and
               any(v in rule.get("verbs", []) for v in ("get", "list", "*"))
               for rule in rules)

def _is_privileged(spec: dict) -> bool:
    for container in spec.get("containers", []):
        sc = container.get("securityContext", {})
        if sc.get("privileged") or sc.get("allowPrivilegeEscalation"):
            return True
    return False

def _runs_as_root(spec: dict) -> bool:
    sc = spec.get("securityContext", {})
    return sc.get("runAsUser") == 0 or sc.get("runAsNonRoot") is False

def _looks_like_db_creds(name: str) -> bool:
    keywords = ("db", "database", "mysql", "postgres", "mongo", "redis",
                "credentials", "creds", "password", "passwd")
    return any(kw in name.lower() for kw in keywords)

def _get_images(spec: dict) -> list:
    return [c.get("image", "") for c in spec.get("containers", [])]


# ─── Node / Edge Factory Helpers ──────────────────────────────────────────────

def _make_id(node_type: str, name: str, namespace: str) -> str:
    """Create a stable, unique node ID."""
    return f"{node_type}:{namespace}:{sanitize_k8s_name(name)}"


def _make_edge(source: str, target: str, relation: str, risk: float = 5.0) -> dict:
    return {
        "source":   source,
        "target":   target,
        "relation": relation,
        "risk":     round(risk, 1),
        "weight":   risk_to_weight(risk),
    }


def _add_node(nodes: dict, node_id: str, node_data: dict) -> None:
    """Add node only if not already present (deduplication)."""
    if node_id not in nodes:
        nodes[node_id] = node_data


def _add_edge(edges: list, source: str, target: str, relation: str, risk: float = 5.0) -> None:
    """Add edge only if an identical source-target-relation triple is not present."""
    for edge in edges:
        if (
            edge.get("source") == source
            and edge.get("target") == target
            and edge.get("relation") == relation
        ):
            return
    edges.append(_make_edge(source, target, relation, risk=risk))
