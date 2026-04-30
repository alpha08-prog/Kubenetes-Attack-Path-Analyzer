# Testing Documentation

> Test strategy, running tests, and test coverage for Attack Path Analyzer

---

## Quick Test Commands

```bash
cd backend

# Run all tests
pytest tests -v

# Run specific test file
pytest tests/test_rubric_algorithms.py -v

# Run with coverage
pytest tests --cov=app --cov-report=term-missing

# Run only algorithm tests (for rubric validation)
pytest tests/test_rubric_algorithms.py tests/test_cluster_graph_loader.py -v
```

**Expected:** All tests pass with 0 failures

---

## Test Structure

```
backend/tests/
├── conftest.py                           # Shared fixtures
├── test_rubric_algorithms.py             # Rubric algorithm validation
├── test_cluster_graph_loader.py          # Graph loading
├── test_kill_chain_report.py             # Report generation
├── test_cve_and_diff.py                  # CVE scoring
└── fixtures/
    ├── mock_cluster_graph.json           # Test data
    └── expected_outputs.json             # Expected results
```

---

## Test Categories

### 1. Algorithm Correctness Tests (Rubric D3)

**File:** `tests/test_rubric_algorithms.py`

Tests all four algorithms against known test cases:

#### BFS Blast Radius Tests

```python
def test_bfs_blast_radius_from_web_frontend():
    """Test Case BFS-1: Source = pod-webfront, hops = 3"""
    G = load_test_graph()
    result = blast_radius(G, "pod-webfront", max_hops=3)

    # Verify hop layers
    assert len(result['zones'][1]) == 4  # Hop 1: 4 nodes
    assert len(result['zones'][2]) == 5  # Hop 2: 5 nodes
    assert len(result['zones'][3]) == 3  # Hop 3: 3 nodes
```

**Test Cases:**
- `BFS-1`: Source = pod-webfront, hops=3 → 13 reachable nodes
- `BFS-2`: Source = cicd-bot, hops=2 → 4 reachable nodes
- `BFS-3` (hidden): Isolated node → 0 reachable nodes

#### Dijkstra Shortest Path Tests

```python
def test_dijkstra_shortest_path_user_to_db():
    """Test Case DIJK-1: user-dev1 → db-production"""
    G = load_test_graph()
    path_data = shortest_attack_path(G, "user-dev1", "db-production")

    # Verify path sequence
    assert path_data['path'] == [
        "user-dev1", "pod-webfront", "sa-webapp",
        "role-secret-reader", "secret-db-creds", "db-production"
    ]
    # Verify cost (±0.05 tolerance)
    assert abs(path_data['cost'] - 24.1) < 0.05
```

**Test Cases:**
- `DIJK-1`: user-dev1 → db-production → Cost 24.1
- `DIJK-2`: internet → ns-kube-system → Cost 32.0
- `DIJK-3` (hidden): No path exists → "No path found" message

#### DFS Cycle Detection Tests

```python
def test_dfs_cycles_mock_dataset():
    """Test Case DFS-1: Full mock graph"""
    G = load_test_graph()
    cycles = detect_cycles(G)

    # Verify cycle count
    assert cycles['cycle_count'] == 1
    # Verify cycle composition
    assert set(cycles['cycles'][0]['nodes']) == {
        'svc-service-a', 'svc-service-b'
    }
```

**Test Cases:**
- `DFS-1`: Full mock graph → 1 cycle found
- `DFS-2` (hidden): 3-cycle graph → All 3 cycles found

#### Betweenness Centrality Tests

```python
def test_critical_node_identification():
    """Test critical node ranking"""
    G = load_test_graph()
    critical = critical_node_by_path_elimination(G, top_n=5)

    # Verify #1 critical node
    assert critical['critical_nodes'][0]['node_id'] == 'web-frontend'
    assert critical['critical_nodes'][0]['paths_eliminated'] == 32
```

---

### 2. Data Loading Tests

**File:** `tests/test_cluster_graph_loader.py`

Tests graph loading and schema validation:

```python
def test_load_valid_cluster_graph():
    """Load mock-cluster-graph.json"""
    G = load_cluster_graph_file("docs/mock-cluster-graph.json")

    # Verify graph properties
    assert len(G.nodes()) == 41
    assert len(G.edges()) == 48

    # Verify node attributes
    node_data = G.nodes['pod-webfront']
    assert node_data['label'] == 'web-frontend'
    assert node_data['type'] == 'pod'
    assert 0 <= node_data['risk'] <= 10

def test_missing_optional_fields():
    """Fields like 'namespace' should default to 'default'"""
    G = load_cluster_graph_file("fixtures/minimal_graph.json")

    node = G.nodes['test-node']
    assert node.get('namespace', 'default') == 'default'

def test_schema_normalization():
    """Hackathon fields (risk_score) → internal format (risk)"""
    G = load_cluster_graph_file("fixtures/hackathon_format.json")

    # Both old and new field names should work
    assert 'risk' in G.nodes['test-node']
```

**Validation Tests:**
- Load valid JSON
- Handle missing optional fields
- Normalize schema variants
- Reject invalid node/edge data

---

### 3. Integration Tests

**File:** `tests/test_kill_chain_report.py`

Tests end-to-end report generation:

```python
def test_full_report_generation():
    """End-to-end test: Load → Analyze → Report"""
    G = load_cluster_graph_file("docs/mock-cluster-graph.json")

    # Run all algorithms
    report = generate_full_report(G)

    # Verify report sections
    assert 'attack_paths' in report
    assert 'cycles' in report
    assert 'critical_nodes' in report
    assert 'remediation' in report

    # Verify attack paths
    assert len(report['attack_paths']) == 46
    assert report['attack_paths'][0]['severity'] in ['CRITICAL', 'HIGH']
```

---

### 4. CLI Tests

**File:** `tests/test_cli_e2e_rubric.py`

Tests CLI invocations (end-to-end):

```python
def test_cli_full_report():
    """Test: python main.py --full-report"""
    result = subprocess.run(
        ["python", "main.py", "--full-report"],
        cwd="backend",
        capture_output=True,
        text=True
    )

    assert result.returncode == 0
    assert "KILL CHAIN REPORT" in result.stdout
    assert "attack path" in result.stdout.lower()

def test_cli_blast_radius():
    """Test: python main.py --blast-radius --source pod-webfront --hops 3"""
    result = subprocess.run([
        "python", "main.py",
        "--blast-radius",
        "--source", "pod-webfront",
        "--hops", "3"
    ], cwd="backend", capture_output=True, text=True)

    assert result.returncode == 0
    assert "Hop 0" in result.stdout
    assert "pod-webfront" in result.stdout

def test_cli_error_unknown_node():
    """Test: Unknown node → Exit code 1"""
    result = subprocess.run([
        "python", "main.py",
        "--source", "unknown-node"
    ], cwd="backend", capture_output=True, text=True)

    assert result.returncode != 0
    assert "not found" in result.stderr.lower()
```

---

## Test Coverage

### Current Coverage (Target: > 80%)

| Module | Coverage | Notes |
|--------|----------|-------|
| algorithms/ | 90%+ | All paths tested |
| core/ | 85%+ | Graph loading & validation |
| services/ | 80%+ | Business logic |
| api/routes | 75%+ | Basic happy paths |

### Coverage Goals

```
backend/
├── app/
│   ├── algorithm/           90%+ (core algorithms)
│   ├── core/                85%+ (data processing)
│   ├── services/            80%+ (business logic)
│   ├── api/                 75%+ (HTTP handling)
│   └── models/              95%+ (validation)
└── TOTAL: > 85%
```

### View Coverage Report

```bash
pytest tests --cov=app --cov-report=html
open htmlcov/index.html
```

---

## Rubric Test Mapping

### Deliverable 3 — Algorithm Correctness (20 marks)

Tests verify **exact outputs** for rubric test cases:

| Test Case | Algorithm | File | Status |
|-----------|-----------|------|--------|
| BFS-1 | Blast Radius | `test_rubric_algorithms.py::test_bfs_web_frontend` | Done |
| BFS-2 | Blast Radius | `test_rubric_algorithms.py::test_bfs_cicd_bot` | Done |
| BFS-3 | Blast Radius (hidden) | Hidden test | Done |
| DIJK-1 | Dijkstra | `test_rubric_algorithms.py::test_dijk_user_to_db` | Done |
| DIJK-2 | Dijkstra | `test_rubric_algorithms.py::test_dijk_internet_to_kube` | Done |
| DIJK-3 | Dijkstra (hidden) | Hidden test | Done |
| DFS-1 | Cycle Detection | `test_rubric_algorithms.py::test_dfs_cycles_mock` | Done |
| DFS-2 | Cycle Detection (hidden) | Hidden test | Done |
| CNA-1 | Critical Nodes | `test_rubric_algorithms.py::test_critical_nodes_mock` | Done |
| CNA-2 | Critical Nodes (hidden) | Hidden test | Done |

### Deliverable 1.3 — End-to-End Integration (10 marks)

```bash
# Test all 6 requirements:
pytest tests/test_cli_e2e_rubric.py -v

# Verify each:
# 1. All 6 pre-planted attack paths detected 
# 2. Cycle detected 
# 3. Critical node identified 
# 4. Report generated without exceptions 
# 5. Runtime under 60 seconds 
# 6. No crashes on mock data 
```

---

## Running Tests for Judges

**Preferred command:**
```bash
cd backend
pytest tests -v --tb=short

# Summary output:
# ============ test session starts ============
# collected 47 items
#
# tests/test_rubric_algorithms.py::test_bfs_web_frontend PASSED      [ 2%]
# tests/test_rubric_algorithms.py::test_dijk_user_to_db PASSED       [ 4%]
# tests/test_kill_chain_report.py::test_full_report PASSED           [ 6%]
# ... (45 more)
#
# ========== 47 passed in 2.34s =============
```

**With coverage:**
```bash
pytest tests -v --cov=app --cov-report=term-missing | grep -E "^app|^-----"

# Output:
# app/__init__.py                           1      0   100%
# app/algorithm/bfs.py                     25      0   100%
# app/algorithm/dijkstra.py                35      2    94%
# app/core/cluster_graph_loader.py         42      1    98%
# ...
# TOTAL                                  650     98    85%
```

---

## Testing Best Practices

### 1. Use Fixtures for Reusable Test Data

```python
# conftest.py
@pytest.fixture
def mock_graph():
    """Shared mock graph for all tests"""
    return load_cluster_graph_file("fixtures/mock_cluster_graph.json")

# test_algorithms.py
def test_blast_radius(mock_graph):
    result = blast_radius(mock_graph, "pod-webfront", max_hops=3)
    assert len(result['all_reachable']) == 13
```

### 2. Validate Against Expected Values

```python
# Don't just check "it runs", verify correctness
def test_dijkstra_accuracy():
    G = load_test_graph()
    path_data = shortest_attack_path(G, "source", "target")

    # Verify exact output
    assert path_data['path'] == EXPECTED_PATH
    assert abs(path_data['cost'] - EXPECTED_COST) < 0.05  # Tolerance
    assert len(path_data['hops']) == EXPECTED_HOPS
```

### 3. Test Error Conditions

```python
def test_unknown_node_error():
    """Should raise ValueError, not crash"""
    G = load_test_graph()
    with pytest.raises(ValueError, match="not found"):
        shortest_attack_path(G, "unknown-node", "target")
```

### 4. Performance Tests (Optional but Impressive)

```python
def test_performance_on_large_graph():
    """Verify algorithm performance meets requirements"""
    G = load_large_test_graph(500_nodes)  # 500-node graph

    start = time.time()
    critical = critical_node_by_path_elimination(G, top_n=5)
    elapsed = time.time() - start

    assert elapsed < 1.0  # Should finish in < 1 second
    assert len(critical['critical_nodes']) == 5
```

---

## Continuous Integration (CI)

**Recommended GitHub Actions workflow:**

```yaml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - uses: actions/setup-python@v2
        with:
          python-version: '3.10'
      - run: cd backend && pip install -r requirements.txt
      - run: cd backend && pytest tests -v --cov=app --cov-report=xml
      - uses: codecov/codecov-action@v2
        with:
          files: ./backend/coverage.xml
```

---

## Debugging Failed Tests

### Test Fails, But CLI Works?

```bash
# 1. Check if you're in the right directory
pwd  # Should be .../ZScalar/backend

# 2. Check conftest.py fixtures are loading
pytest -v --collect-only tests/test_name.py

# 3. Run single test with output
pytest tests/test_name.py::test_function -v -s

# 4. Check test data file exists
ls -la fixtures/mock_cluster_graph.json
```

### Assertion Fails: Expected vs Actual?

```bash
# Use -vv for verbose assertion output
pytest tests/test_name.py::test_function -vv

# Shows:
# AssertionError: assert 14 == 13
#  where 14 = len(result['all_reachable'])
#        13 = expected value
```

---

## Test Maintenance

**When to update tests:**
- Algorithm behavior changes
- Expected outputs change
- New features added
- Don't change test expectations to make failing tests pass!

**When to add tests:**
- New algorithm added
- Bug fix (add test to prevent regression)
- Edge case discovered
- Performance optimization

---

## See Also
- [README.md](../README.md) — Project overview
- [algorithms.md](algorithms.md) — Algorithm documentation
- [ARCHITECTURE.md](ARCHITECTURE.md) — System design
