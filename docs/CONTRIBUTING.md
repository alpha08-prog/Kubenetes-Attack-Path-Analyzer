# Contributing Guidelines

> How to extend and contribute to Attack Path Analyzer

---

## Getting Started

### Prerequisites

- Python 3.10+
- Node.js 20+
- Git
- Docker (optional, for testing)

### Setup Development Environment

**1. Clone repository:**
```bash
git clone https://github.com/your-team/attack-path-analyzer.git
cd attack-path-analyzer
```

**2. Backend setup:**
```bash
cd backend
python -m venv venv
source venv/bin/activate          # Mac/Linux
# venv\Scripts\activate           # Windows
pip install -r requirements.txt
pip install -r requirements-dev.txt  # For testing/linting
```

**3. Frontend setup:**
```bash
cd frontend
npm install
```

**4. Verify setup:**
```bash
cd backend
pytest tests -v --tb=short      # Should see "passed"

cd ../frontend
npm run build                    # Should complete without errors
```

---

## Code Style & Standards

### Python (Backend)

**Style:** PEP-8 via Black

```bash
# Format code
black backend/app --line-length 100

# Check style
flake8 backend/app

# Type checking
mypy backend/app
```

**Requirements:**
- [ ] Functions have docstrings (at minimum: what it does, return type)
- [ ] Classes have docstrings
- [ ] Variable names are descriptive (not `x`, `y`, `z`)
- [ ] No magic numbers (use named constants)
- [ ] Imports organized: standard library, third-party, local

**Example:**
```python
def blast_radius(G: nx.DiGraph, source: str, max_hops: int = 3) -> dict:
    """
    Find all reachable nodes from source within max_hops using BFS.

    Args:
        G: NetworkX directed graph
        source: Starting node ID
        max_hops: Maximum hop distance (default: 3)

    Returns:
        Dictionary with zones, total_reachable, all_reachable
    """
    # Implementation...
    return result
```

### JavaScript/React (Frontend)

**Style:** Prettier + ESLint

```bash
# Format
prettier --write frontend/src

# Lint
eslint frontend/src
```

**Requirements:**
- [ ] Component names are PascalCase
- [ ] Props are validated via PropTypes or TypeScript
- [ ] Hooks follow React rules (dependencies arrays, etc.)
- [ ] No console.log in production code
- [ ] Comments explain *why*, not *what*

---

## Adding New Features

### 1. New Algorithm

**Example: Add a new graph algorithm**

**File structure:**
```
backend/app/algorithm/
├── your_algorithm.py  # NEW
└── __init__.py        # Update to import your_algorithm
```

**Implementation template:**
```python
"""
your_algorithm.py - Brief description of algorithm

Algorithm: Name, complexity, rationale
"""

from __future__ import annotations
import networkx as nx

def your_algorithm(G: nx.DiGraph, **kwargs) -> dict:
    """
    Describe what this algorithm computes.

    Args:
        G: NetworkX directed graph
        **kwargs: Algorithm-specific parameters

    Returns:
        Structured result dict
    """
    # Validate input
    if not G.nodes():
        raise ValueError("Graph is empty")

    # Core algorithm implementation
    result = {}

    return result
```

**Add tests:**
```python
# backend/tests/test_your_algorithm.py
def test_your_algorithm_basic():
    G = load_test_graph()
    result = your_algorithm(G)
    assert 'key' in result
    assert result['key'] == expected_value

def test_your_algorithm_edge_case():
    G = nx.DiGraph()  # Empty graph
    with pytest.raises(ValueError):
        your_algorithm(G)
```

**Add API route:**
```python
# backend/app/api/routes_your_algorithm.py
from fastapi import APIRouter
from app.algorithm.your_algorithm import your_algorithm

router = APIRouter(prefix="/api/your-endpoint", tags=["your-feature"])

@router.post("/")
async def your_endpoint(request: YourRequest) -> dict:
    """Endpoint description"""
    G = get_graph()  # Get current graph
    result = your_algorithm(G, **request.dict())
    return result
```

**Register route in main.py:**
```python
# backend/app/main.py
from app.api import routes_your_algorithm
app.include_router(routes_your_algorithm.router)
```

### 2. New API Endpoint

**Template:**
```python
# backend/app/api/routes_new_feature.py
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/api/new-feature", tags=["new-feature"])

class NewFeatureRequest(BaseModel):
    param1: str
    param2: int = 10  # Optional with default

@router.post("/analyze")
async def analyze_feature(request: NewFeatureRequest) -> dict:
    """Analyze something using new feature"""
    try:
        result = do_something(request.param1, request.param2)
        return {"status": "success", "result": result}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
```

**Test it:**
```bash
curl -X POST http://localhost:8000/api/new-feature/analyze \
  -H "Content-Type: application/json" \
  -d '{"param1": "value", "param2": 20}'
```

### 3. New React Component

**File structure:**
```
frontend/src/components/
├── NewFeature/
│   ├── NewFeature.jsx       # Component
│   ├── NewFeature.module.css # Styles
│   └── index.js             # Export
```

**Implementation:**
```jsx
// frontend/src/components/NewFeature/NewFeature.jsx
import React, { useState, useEffect } from 'react';
import styles from './NewFeature.module.css';
import { api } from '../../api/client';

const NewFeature = ({ data }) => {
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);

  const handleAnalyze = async () => {
    setLoading(true);
    try {
      const response = await api.post('/new-feature/analyze', { param1: data });
      setResult(response.data);
    } catch (error) {
      console.error('Error:', error);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className={styles.container}>
      <button onClick={handleAnalyze} disabled={loading}>
        {loading ? 'Analyzing...' : 'Analyze'}
      </button>
      {result && <div>{/* Display result */}</div>}
    </div>
  );
};

export default NewFeature;
```

---

## Submitting Changes

### 1. Create Feature Branch

```bash
git checkout -b feature/your-feature-name
git checkout -b fix/bug-description
```

### 2. Commit Changes

```bash
# Stage changes
git add backend/app/algorithm/new.py tests/test_new.py

# Commit with descriptive message
git commit -m "Add new algorithm for X analysis

- Implements Y algorithm
- Includes unit tests (5 test cases)
- Adds API endpoint /api/x
- Performance: O(V+E) on 500-node graph

Closes #123"
```

### 3. Run Tests Before Pushing

```bash
# Backend tests
cd backend && pytest tests -v --tb=short

# Frontend tests
cd frontend && npm test

# Linting
cd backend && black . && flake8 . && mypy .
cd frontend && prettier --check src && eslint src
```

### 4. Push and Create PR

```bash
git push origin feature/your-feature-name
```

**PR Template:**
```markdown
## Description
Brief description of what this PR does.

## Type of Change
- [ ] New algorithm
- [ ] Bug fix
- [ ] New API endpoint
- [ ] Documentation
- [ ] Performance improvement

## Test Coverage
- [ ] Unit tests added/updated
- [ ] Integration tests added/updated
- [ ] Manual testing completed

## Checklist
- [ ] Code follows style guidelines (PEP-8, Prettier)
- [ ] Docstrings added
- [ ] Tests pass locally
- [ ] Documentation updated (if applicable)
```

---

## Code Review Checklist

When reviewing PRs, check:

**Functionality:**
- [ ] Does it do what the PR description says?
- [ ] Are edge cases handled?
- [ ] Are errors handled gracefully?

**Code Quality:**
- [ ] Is code readable and maintainable?
- [ ] Are variable names descriptive?
- [ ] Are there docstrings?
- [ ] Is there duplicate code?

**Testing:**
- [ ] Are tests comprehensive?
- [ ] Do tests pass?
- [ ] Is coverage > 80%?

**Performance:**
- [ ] Could this slow down the application?
- [ ] Are there algorithmic improvements?

**Documentation:**
- [ ] Are new features documented?
- [ ] Are algorithm changes documented?
- [ ] Is the README updated (if needed)?

---

## Documentation

### When to Update Docs

**Update these files when:**

1. **Adding new algorithm:**
   - `algorithms.md` — Add algorithm explanation
   - `API_DOCUMENTATION.md` — Document endpoint
   - `CLI_COMMAND_REFERENCE.md` — Add CLI usage

2. **Adding new feature:**
   - `ARCHITECTURE.md` — Update component diagram if needed
   - `README.md` — Add to features table
   - Create new doc file if complex feature

3. **Fixing a bug:**
   - Update any relevant docs if behavior changed
   - No docs needed for internal fixes

4. **Changing API/CLI:**
   - Update `API_DOCUMENTATION.md`
   - Update `CLI_COMMAND_REFERENCE.md`
   - Update `README.md` examples if needed

### Documentation Standards

```markdown
# Heading

Brief paragraph explaining what this is.

## Sub-section

### Details
- Bullet point
- Another point

Code examples:
\`\`\`python
def example():
    return "code"
\`\`\`

Expected output:
\`\`\`
output here
\`\`\`
```

---

## Performance Considerations

### Before Submitting

**Check algorithm complexity:**
- O(V+E) — Good 
- O(V²) — Acceptable for < 1000 nodes 
- O(2^V) — Not acceptable 

**Benchmark on large graph:**
```bash
# Run on 500-node test graph
time python main.py --full-report

# Should complete in < 1 second
```

**Profile if needed:**
```bash
pip install line_profiler
kernprof -l -v backend/app/algorithm/your_algorithm.py
```

---

## Common Patterns

### Error Handling

```python
# DON'T
result = nx.dijkstra_path(G, source, target)

# DO
try:
    result = nx.dijkstra_path(G, source, target)
except nx.NodeNotFound as e:
    raise ValueError(f"Node not found: {e}")
except nx.NetworkXNoPath as e:
    return {"status": "error", "message": "No path exists"}
```

### Type Hints

```python
# DO
def blast_radius(G: nx.DiGraph, source: str, max_hops: int = 3) -> dict:
    pass

# DON'T
def blast_radius(G, source, max_hops=3):
    pass
```

### Constants

```python
# DON'T (magic numbers)
for i in range(3):
    # ...

# DO
MAX_DEFAULT_HOPS = 3
for i in range(MAX_DEFAULT_HOPS):
    # ...
```

---

## Asking for Help

**Can't figure out something?**
1. Check existing docs: `docs/` directory
2. Check similar code: `backend/app/algorithm/` or `frontend/src/components/`
3. Read algorithm docstrings carefully
4. Check test files for usage examples

**Still stuck?**
- Create an issue with:
  - What you're trying to do
  - What you've already tried
  - Error message (if applicable)
  - Code snippet (if applicable)

---

## Release Process (For Maintainers)

```bash
# 1. Update version
echo "1.2.0" > VERSION

# 2. Update CHANGELOG
# Add section with new features, fixes, etc.

# 3. Commit
git commit -m "Release v1.2.0"
git tag v1.2.0

# 4. Push
git push origin main --tags

# 5. Create release on GitHub
# Copy changelog to release notes
```

---

## See Also
- [README.md](../README.md) — Project overview
- [TESTING.md](TESTING.md) — Test guidelines
- [ARCHITECTURE.md](ARCHITECTURE.md) — System design
- [algorithms.md](algorithms.md) — Algorithm documentation
