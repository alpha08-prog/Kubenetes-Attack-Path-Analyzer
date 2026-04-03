"""
remediation_service.py — Automated Remediation Suggestion Service
Analyzes attack paths and cycles to suggest concrete RBAC changes and mitigations.
"""

from app.utils.logger import get_logger

logger = get_logger(__name__)


class RemediationStep:
    """Represents one actionable fix to break an attack chain."""

    def __init__(
        self,
        title: str,
        description: str,
        action_type: str,  # "rbac", "network_policy", "pod_hardening", "secret_isolation"
        target_resource: str,  # e.g., "admin-role", "web-sa", "db-secret"
        target_resource_type: str,  # e.g., "role", "serviceaccount", "secret"
        change: str,  # e.g., "Remove from RoleBinding", "Add NetworkPolicy", "Encrypt at rest"
        yaml_snippet: str,  # YAML code to implement the fix
        impact_count: int = 1,  # How many attack paths this breaks
        difficulty: str = "medium",  # low, medium, high
    ):
        self.title = title
        self.description = description
        self.action_type = action_type
        self.target_resource = target_resource
        self.target_resource_type = target_resource_type
        self.change = change
        self.yaml_snippet = yaml_snippet
        self.impact_count = impact_count
        self.difficulty = difficulty

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "description": self.description,
            "action_type": self.action_type,
            "target_resource": self.target_resource,
            "target_resource_type": self.target_resource_type,
            "change": self.change,
            "yaml_snippet": self.yaml_snippet,
            "impact_count": self.impact_count,
            "difficulty": self.difficulty,
        }


def analyze_attack_path_for_remediation(attack_path: dict) -> list[RemediationStep]:
    """
    Given an attack path response, identify critical edges that could be broken.
    Returns list of remediation steps ordered by impact.
    """
    if not attack_path.get("found") or not attack_path.get("hops"):
        return []

    remediations = []
    hops = attack_path.get("hops", [])

    # Identify the most critical edge (highest risk)
    if hops:
        # Find the hop with highest edge_risk
        highest_risk_hop = max(hops, key=lambda h: h.get("edge_risk", 0))

        from_label = highest_risk_hop.get("from_label", "unknown")
        to_label = highest_risk_hop.get("to_label", "unknown")
        from_type = highest_risk_hop.get("from_type", "unknown")
        to_type = highest_risk_hop.get("to_type", "unknown")
        relation = highest_risk_hop.get("relation", "unknown")

        # Common K8s attack patterns and mitigations
        if relation == "can_use_secret" or "secret" in to_type.lower():
            # Secrets are being accessed — suggest isolation
            yaml_fix = f"""apiVersion: v1
kind: Secret
metadata:
  name: {to_label}
type: Opaque
data:
  # Encrypted at rest; consider SecretsProvider encryption
  # Remove all unnecessary RBAC that allows reading this secret
  """
            remediations.append(
                RemediationStep(
                    title=f"Remove secret access from {from_label}",
                    description=f"ServiceAccount '{from_label}' should not have access to secret '{to_label}'",
                    action_type="rbac",
                    target_resource=to_label,
                    target_resource_type="secret",
                    change=f"Remove RoleBinding that grants 'get' on secrets to {from_label}",
                    yaml_snippet=yaml_fix,
                    impact_count=len(hops),
                    difficulty="low",
                )
            )

        if relation == "has_role" or "role" in to_type.lower():
            # Role binding is allowing escalation
            yaml_fix = f"""apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: fix-{from_label}-binding
  namespace: default
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: Role
  name: restricted-role
subjects:
- kind: ServiceAccount
  name: {from_label}
  namespace: default
            """
            remediations.append(
                RemediationStep(
                    title=f"Restrict {from_label} RBAC permissions",
                    description=f"'{from_label}' has overly broad role '{to_label}' that enables escalation",
                    action_type="rbac",
                    target_resource=from_label,
                    target_resource_type="serviceaccount",
                    change=f"Bind {from_label} to a minimal role instead of admin",
                    yaml_snippet=yaml_fix,
                    impact_count=len(hops),
                    difficulty="medium",
                )
            )

        if relation == "can_become":
            # User/pod can assume another identity
            yaml_fix = f"""# Add service account impersonation restrictions
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: no-impersonate
rules:
- apiGroups: [""]
  resources: ["serviceaccounts"]
  verbs: []  # Remove impersonate verb
            """
            remediations.append(
                RemediationStep(
                    title=f"Prevent impersonation of {to_label}",
                    description=f"'{from_label}' can impersonate '{to_label}' — remove this capability",
                    action_type="rbac",
                    target_resource=from_label,
                    target_resource_type="serviceaccount",
                    change=f"Remove 'impersonate' verb for {to_label} from {from_label}'s role",
                    yaml_snippet=yaml_fix,
                    impact_count=len(hops),
                    difficulty="low",
                )
            )

    # Add general hardening suggestions for critical path length
    hop_count = attack_path.get("hop_count", 0)
    if hop_count <= 2:
        # Short path = very dangerous
        remediations.append(
            RemediationStep(
                title="Separate privilege levels with network policies",
                description="Attack path is only 2 hops — network segmentation would significantly increase difficulty",
                action_type="network_policy",
                target_resource="cluster-policy",
                target_resource_type="networkpolicy",
                change="Implement zero-trust network policies to isolate sensitive resources",
                yaml_snippet="""apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: deny-cross-namespace
  namespace: default
spec:
  podSelector: {}
  policyTypes:
  - Ingress
  ingress:
  - from:
    - podSelector: {}
            """,
                impact_count=1,
                difficulty="high",
            )
        )

    return sorted(remediations, key=lambda r: (-r.impact_count, r.difficulty != "low"))


def analyze_cycles_for_remediation(cycles: dict) -> list[RemediationStep]:
    """
    Given privilege escalation cycles, suggest how to break them.
    """
    if not cycles.get("cycles"):
        return []

    remediations = []
    cycles_list = cycles.get("cycles", [])

    # Most dangerous cycles are those with highest max_risk and shortest length
    for cycle in sorted(
        cycles_list, key=lambda c: (-c.get("max_risk", 0), c.get("length", 999))
    )[:2]:  # Top 2 cycles
        chain = cycle.get("chain", "unknown")
        length = cycle.get("length", 0)

        remediations.append(
            RemediationStep(
                title=f"Break privilege escalation cycle (length {length})",
                description=f"Cycle detected: {chain}. Breaking one link prevents infinite privilege gain.",
                action_type="rbac",
                target_resource=f"cycle-{cycle.get('id', 0)}",
                target_resource_type="rolebinding",
                change="Remove or restrict one link in the cycle to prevent escalation",
                yaml_snippet="""# Edit the RoleBinding that completes the cycle:
# Change:
# - apiGroup: rbac.authorization.k8s.io
#   kind: ServiceAccount
#   name: <attacking-sa>
# To:
# (remove this entry entirely)
            """,
                impact_count=1,
                difficulty="low",
            )
        )

    return remediations


def suggest_remediations_for_analysis(analysis_result: dict) -> dict:
    """
    High-level function: given full analysis, suggest all remediations.
    Called by API route to enrich response.
    """
    remediations = []

    # From attack paths
    attack_path = analysis_result.get("attack_path", {})
    if attack_path.get("found"):
        remediations.extend(analyze_attack_path_for_remediation(attack_path))

    # From cycles
    cycles = analysis_result.get("cycles", {})
    if cycles.get("cycle_count", 0) > 0:
        remediations.extend(analyze_cycles_for_remediation(cycles))

    # Deduplicate and sort by impact
    unique_remediations = {r.title: r for r in remediations}
    sorted_remediations = sorted(
        unique_remediations.values(),
        key=lambda r: (-r.impact_count, r.difficulty != "low"),
    )

    return {
        "remediation_count": len(sorted_remediations),
        "remediations": [r.to_dict() for r in sorted_remediations[:5]],  # Top 5 suggestions
    }
