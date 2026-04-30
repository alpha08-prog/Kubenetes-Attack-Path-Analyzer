"""
generate_mock_data.py — Nokia Telecom Demo Scenario Generator
Generates data/scenarios/nokia_telecom.json

This scenario has:
  - 18 nodes across 6 types (pod, service_account, role, secret, database, user)
  - 22 edges forming a realistic Kubernetes access graph
  - 1 guaranteed 3-hop attack path: web-server → backend-sa → db-secret → billing-db
  - 1 privilege escalation cycle: backend-sa → admin-role → backend-sa
  - 3 high-centrality nodes for the critical node leaderboard

Run from the repo root:
    python scripts/generate_mock_data.py
"""

import json
from pathlib import Path

# ─── Output path ──────────────────────────────────────────────────────────────

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
OUTPUT_PATH = REPO_ROOT / "data" / "scenarios" / "nokia_telecom.json"


# ─── Nodes ────────────────────────────────────────────────────────────────────

NODES = [

    # ── Pods ──────────────────────────────────────────────────────────────────
    {
        "id":        "pod:default:web-server",
        "label":     "web-server",
        "type":      "pod",
        "risk":      7.5,
        "namespace": "default",
        "metadata":  {
            "image":        ["nginx:1.19"],
            "host_network": False,
            "privileged":   False,
            "phase":        "Running",
            "note":         "Public-facing pod — attacker entry point"
        }
    },
    {
        "id":        "pod:default:api-server",
        "label":     "api-server",
        "type":      "pod",
        "risk":      8.0,
        "namespace": "default",
        "metadata":  {
            "image":      ["node:18-alpine"],
            "privileged": False,
            "phase":      "Running",
            "note":       "Internal API pod with overbroad SA"
        }
    },
    {
        "id":        "pod:default:metrics-collector",
        "label":     "metrics-collector",
        "type":      "pod",
        "risk":      6.0,
        "namespace": "default",
        "metadata":  {
            "image":      ["prom/prometheus:v2.40.0"],
            "privileged": False,
            "phase":      "Running"
        }
    },
    {
        "id":        "pod:kube-system:coredns",
        "label":     "coredns",
        "type":      "pod",
        "risk":      5.5,
        "namespace": "kube-system",
        "metadata":  {
            "image": ["registry.k8s.io/coredns/coredns:v1.10.1"],
            "phase": "Running"
        }
    },

    # ── Service Accounts ──────────────────────────────────────────────────────
    {
        "id":        "service_account:default:backend-sa",
        "label":     "backend-sa",
        "type":      "service_account",
        "risk":      8.5,
        "namespace": "default",
        "metadata":  {
            "note": "Overbroad SA — bound to admin-role"
        }
    },
    {
        "id":        "service_account:default:metrics-sa",
        "label":     "metrics-sa",
        "type":      "service_account",
        "risk":      4.5,
        "namespace": "default",
        "metadata":  {}
    },
    {
        "id":        "service_account:kube-system:coredns-sa",
        "label":     "coredns-sa",
        "type":      "service_account",
        "risk":      5.0,
        "namespace": "kube-system",
        "metadata":  {}
    },

    # ── Roles ─────────────────────────────────────────────────────────────────
    {
        "id":        "role:default:admin-role",
        "label":     "admin-role",
        "type":      "role",
        "risk":      9.5,
        "namespace": "default",
        "metadata":  {
            "has_wildcard":   True,
            "cluster_scoped": False,
            "rules": [
                {"verbs": ["*"], "resources": ["*"]}
            ],
            "note": "Wildcard role — can read all secrets"
        }
    },
    {
        "id":        "role:default:secret-reader",
        "label":     "secret-reader",
        "type":      "role",
        "risk":      7.5,
        "namespace": "default",
        "metadata":  {
            "has_wildcard": False,
            "rules": [
                {"verbs": ["get", "list"], "resources": ["secrets"]}
            ]
        }
    },
    {
        "id":        "role:default:metrics-role",
        "label":     "metrics-role",
        "type":      "role",
        "risk":      3.5,
        "namespace": "default",
        "metadata":  {
            "rules": [
                {"verbs": ["get"], "resources": ["pods", "nodes"]}
            ]
        }
    },
    {
        "id":        "role:cluster:cluster-admin",
        "label":     "cluster-admin",
        "type":      "role",
        "risk":      10.0,
        "namespace": "cluster",
        "metadata":  {
            "has_wildcard":   True,
            "cluster_scoped": True,
            "note":           "Full cluster access — maximum risk"
        }
    },

    # ── Secrets ───────────────────────────────────────────────────────────────
    {
        "id":        "secret:default:db-credentials",
        "label":     "db-credentials",
        "type":      "secret",
        "risk":      9.0,
        "namespace": "default",
        "metadata":  {
            "secret_type": "Opaque",
            "is_db_creds": True,
            "note":        "Contains plaintext DB password — critical exposure"
        }
    },
    {
        "id":        "secret:default:tls-cert",
        "label":     "tls-cert",
        "type":      "secret",
        "risk":      5.5,
        "namespace": "default",
        "metadata":  {
            "secret_type": "kubernetes.io/tls",
            "is_db_creds": False
        }
    },
    {
        "id":        "secret:default:api-token",
        "label":     "api-token",
        "type":      "secret",
        "risk":      8.0,
        "namespace": "default",
        "metadata":  {
            "secret_type": "kubernetes.io/service-account-token",
            "is_db_creds": False,
            "note":        "SA token — can be used to impersonate backend-sa"
        }
    },

    # ── Databases ─────────────────────────────────────────────────────────────
    {
        "id":        "database:default:billing-db",
        "label":     "billing-db",
        "type":      "database",
        "risk":      9.5,
        "namespace": "default",
        "metadata":  {
            "engine": "PostgreSQL",
            "note":   "Production billing database — primary target"
        }
    },
    {
        "id":        "database:default:analytics-db",
        "label":     "analytics-db",
        "type":      "database",
        "risk":      7.0,
        "namespace": "default",
        "metadata":  {
            "engine": "ClickHouse",
            "note":   "Telemetry analytics store"
        }
    },

    # ── Users ─────────────────────────────────────────────────────────────────
    {
        "id":        "user:cluster:dev-1",
        "label":     "dev-1",
        "type":      "user",
        "risk":      6.5,
        "namespace": "cluster",
        "metadata":  {
            "note": "Developer with secret-reader binding — lateral move risk"
        }
    },
    {
        "id":        "user:cluster:ci-bot",
        "label":     "ci-bot",
        "type":      "user",
        "risk":      7.5,
        "namespace": "cluster",
        "metadata":  {
            "note": "CI/CD service user bound to cluster-admin — over-privileged"
        }
    },
]


# ─── Edges ────────────────────────────────────────────────────────────────────
# Edge `weight` is exploitability cost (lower = easier to exploit, see
# docs/CLUSTER_GRAPH_SCHEMA.md). This generator derives it from `risk` so that
# high-risk edges become low-cost — letting Dijkstra (which minimizes sum of
# weights) naturally prefer the attacker's easiest path. Hand-authored
# scenarios can set `weight` directly under the same convention.

def w(risk: float) -> float:
    return round(10.0 - risk, 1)


EDGES = [

    # ── Pod → Service Account (uses) ──────────────────────────────────────────
    {
        "source": "pod:default:web-server",
        "target": "service_account:default:backend-sa",
        "relation": "uses", "risk": 7.5, "weight": w(7.5)
    },
    {
        "source": "pod:default:api-server",
        "target": "service_account:default:backend-sa",
        "relation": "uses", "risk": 8.0, "weight": w(8.0)
    },
    {
        "source": "pod:default:metrics-collector",
        "target": "service_account:default:metrics-sa",
        "relation": "uses", "risk": 4.5, "weight": w(4.5)
    },
    {
        "source": "pod:kube-system:coredns",
        "target": "service_account:kube-system:coredns-sa",
        "relation": "uses", "risk": 5.0, "weight": w(5.0)
    },

    # ── Service Account → Role (bound-to) ─────────────────────────────────────
    {
        "source": "service_account:default:backend-sa",
        "target": "role:default:admin-role",
        "relation": "bound-to", "risk": 9.5, "weight": w(9.5)
    },
    {
        "source": "service_account:default:metrics-sa",
        "target": "role:default:metrics-role",
        "relation": "bound-to", "risk": 3.5, "weight": w(3.5)
    },

    # ── Role → Secret (can-read) ──────────────────────────────────────────────
    {
        "source": "role:default:admin-role",
        "target": "secret:default:db-credentials",
        "relation": "can-read", "risk": 9.0, "weight": w(9.0)
    },
    {
        "source": "role:default:admin-role",
        "target": "secret:default:api-token",
        "relation": "can-read", "risk": 8.0, "weight": w(8.0)
    },
    {
        "source": "role:default:admin-role",
        "target": "secret:default:tls-cert",
        "relation": "can-read", "risk": 5.5, "weight": w(5.5)
    },
    {
        "source": "role:default:secret-reader",
        "target": "secret:default:db-credentials",
        "relation": "can-read", "risk": 7.5, "weight": w(7.5)
    },

    # ── Secret → Database (unlocks) ───────────────────────────────────────────
    {
        "source": "secret:default:db-credentials",
        "target": "database:default:billing-db",
        "relation": "unlocks", "risk": 9.5, "weight": w(9.5)
    },
    {
        "source": "secret:default:db-credentials",
        "target": "database:default:analytics-db",
        "relation": "unlocks", "risk": 7.0, "weight": w(7.0)
    },

    # ── User → Role (bound-to) ────────────────────────────────────────────────
    {
        "source": "user:cluster:dev-1",
        "target": "role:default:secret-reader",
        "relation": "bound-to", "risk": 7.5, "weight": w(7.5)
    },
    {
        "source": "user:cluster:ci-bot",
        "target": "role:cluster:cluster-admin",
        "relation": "bound-to", "risk": 10.0, "weight": w(10.0)
    },

    # ── Privilege escalation CYCLE ────────────────────────────────────────────
    # backend-sa → admin-role → backend-sa
    # This is the cycle DFS detects as a privilege escalation loop
    {
        "source": "role:default:admin-role",
        "target": "service_account:default:backend-sa",
        "relation": "can-impersonate", "risk": 9.0, "weight": w(9.0)
    },

    # ── API token lateral move ─────────────────────────────────────────────────
    {
        "source": "secret:default:api-token",
        "target": "service_account:default:backend-sa",
        "relation": "authenticates-as", "risk": 8.0, "weight": w(8.0)
    },

    # ── Cluster admin reaches everything ──────────────────────────────────────
    {
        "source": "role:cluster:cluster-admin",
        "target": "secret:default:db-credentials",
        "relation": "can-read", "risk": 10.0, "weight": w(10.0)
    },
    {
        "source": "role:cluster:cluster-admin",
        "target": "database:default:billing-db",
        "relation": "accesses", "risk": 10.0, "weight": w(10.0)
    },

    # ── Metrics collector passive reach ───────────────────────────────────────
    {
        "source": "role:default:metrics-role",
        "target": "pod:default:web-server",
        "relation": "can-read", "risk": 4.0, "weight": w(4.0)
    },
    {
        "source": "role:default:metrics-role",
        "target": "pod:default:api-server",
        "relation": "can-read", "risk": 4.0, "weight": w(4.0)
    },
]


# ─── Scenario metadata ────────────────────────────────────────────────────────

SCENARIO_META = {
    "name":         "Nokia Telecom Cluster",
    "description":  "Simulated Nokia telecom Kubernetes cluster with realistic misconfigurations",
    "attack_path":  "web-server → backend-sa → admin-role → db-credentials → billing-db (4 hops)",
    "cycle":        "backend-sa → admin-role → backend-sa (privilege escalation loop)",
    "entry_points": ["pod:default:web-server", "user:cluster:dev-1", "user:cluster:ci-bot"],
    "targets":      ["database:default:billing-db", "database:default:analytics-db"],
    "generated_by": "scripts/generate_mock_data.py",
}


# ─── Write output ─────────────────────────────────────────────────────────────

def generate():
    output = {
        "meta":  SCENARIO_META,
        "nodes": NODES,
        "edges": EDGES,
    }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)

    print(f"Generated {OUTPUT_PATH}")
    print(f"  Nodes : {len(NODES)}")
    print(f"  Edges : {len(EDGES)}")
    print(f"  Attack path  : web-server → backend-sa → admin-role → db-credentials → billing-db")
    print(f"  Cycle        : backend-sa → admin-role → backend-sa")
    print(f"  Entry points : {len(SCENARIO_META['entry_points'])}")
    print(f"  Targets      : {len(SCENARIO_META['targets'])}")
    print()
    print("Run the server and visit http://localhost:8000/docs to verify.")


if __name__ == "__main__":
    generate()
