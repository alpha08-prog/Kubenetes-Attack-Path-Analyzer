# Real-Time Monitoring Implementation Checklist

This document provides a step-by-step checklist for implementing real-time Kubernetes monitoring in the Attack Path Analyzer.

**Total Effort:** ~4 weeks | **Complexity:** High | **Risk:** Low (non-breaking changes)

---

## Pre-Implementation

- [ ] Read `MONITORING_ARCHITECTURE.md` to understand the system design
- [ ] Read `BACKEND_AGENT_IMPLEMENTATION.md` for detailed implementation steps
- [ ] Read `MONITORING_API_REFERENCE.md` for API design
- [ ] Review project structure:
  ```bash
  ls -la backend/app/services/
  ls -la backend/app/api/
  cat backend/app/config.py
  ```
- [ ] Verify existing working features:
  - [ ] Can run: `python -m app.main`
  - [ ] Can fetch: `bash backend/app/scripts/fetch_k8s_data.sh`
  - [ ] Can seed: `python backend/app/scripts/seed_graph.py`
  - [ ] Backend API running on http://localhost:8000
  - [ ] Frontend running on http://localhost:3000

---

## Phase 1: Environment & Dependencies (Days 1-2)

### Dependencies
- [ ] Update `backend/requirements.txt` with:
  ```
  kubernetes>=30.0.0
  python-watch>=4.0.0
  aiodns>=3.1.0
  ```
- [ ] Run: `pip install -r backend/requirements.txt`
- [ ] Verify: `python -c "import kubernetes; print(kubernetes.__version__)"`

### Configuration
- [ ] Update `backend/app/config.py` with monitoring settings (see BACKEND_AGENT_IMPLEMENTATION.md Phase 1B)
- [ ] Update `backend/app/.env` with monitoring variables
- [ ] Verify config loads:
  ```bash
  python -c "from app.config import settings; print(settings.ENABLE_WATCH_API)"
  ```

### Environment Variables
- [ ] Confirm in `.env`:
  ```
  MOCK_MODE=false
  ENABLE_WATCH_API=true
  WATCH_DEBOUNCE_MS=2000
  ALERT_RISK_DELTA_THRESHOLD=1.0
  ```

**Verification:** Run backend, should start without errors

---

## Phase 2: Database Schema (Days 2-3)

### New Tables
- [ ] Add to `backend/app/core/database.py`:
  - [ ] `monitoring_events` table
  - [ ] `monitoring_config` table
  - [ ] `event_queue` table
  - [ ] Indexes on all three

- [ ] Add helper functions to `database.py`:
  - [ ] `record_monitoring_event()`
  - [ ] `get_monitoring_config()`
  - [ ] `update_monitoring_config()`

### Testing
- [ ] Delete existing `data/history.db`
- [ ] Run backend, tables should auto-create
- [ ] Verify:
  ```bash
  sqlite3 data/history.db ".tables"
  # Should list: monitoring_events, monitoring_config, event_queue, ...
  ```

**Verification:** `sqlite3 data/history.db ".schema monitoring_events"` shows table

---

## Phase 3: Watch Service (Days 3-7)

### Core Watch Service
- [ ] Create `backend/app/services/watch_service.py` with:
  - [ ] `KubernetesWatcher` class
  - [ ] `start()` method
  - [ ] `stop()` method
  - [ ] `get_status()` method
  - [ ] `_watch_all_resources()` background loop
  - [ ] Error handling and reconnect logic

- [ ] Create `backend/app/services/event_debouncer.py` with:
  - [ ] `EventDebouncer` class
  - [ ] `queue_event()` method
  - [ ] Debounce timer logic (2-second window)
  - [ ] Event deduplication

- [ ] Create `backend/app/services/watch_decision_engine.py` with:
  - [ ] `analyze_changes()` async function
  - [ ] `_check_alert_thresholds()` function
  - [ ] `_send_alerts()` function
  - [ ] Integration with existing services (diff, slack, history)

### Testing
- [ ] Test watch_service initialization:
  ```bash
  python -c "from app.services.watch_service import get_watcher; w = get_watcher(); print('OK')"
  ```

- [ ] Test K8s connection (with cluster running):
  ```bash
  kubectl cluster-info  # Should succeed
  ```

- [ ] Test debouncer:
  ```bash
  python -c "
  from app.services.event_debouncer import EventDebouncer
  d = EventDebouncer()
  print(f'Initial queue size: {d.get_queue_size()}')
  "
  ```

**Verification:** No import errors, debouncer works

---

## Phase 4: Broadcast Service & Frontend Integration (Days 7-10)

### Broadcast Service
- [ ] Create `backend/app/services/broadcast_service.py` with:
  - [ ] `register_client()` function
  - [ ] `unregister_client()` function
  - [ ] `broadcast_graph_update()` async function
  - [ ] SSE client queue management

### API Endpoints
- [ ] Create `backend/app/api/routes_monitor.py` with:
  - [ ] `POST /monitor/start`
  - [ ] `POST /monitor/stop`
  - [ ] `GET /monitor/status`
  - [ ] `GET /monitor/events/stream` (SSE)

- [ ] Register routes in `backend/app/main.py`:
  ```python
  from app.api import routes_monitor
  app.include_router(routes_monitor.router, prefix="/api")
  ```

### Lifespan Integration
- [ ] Update `backend/app/main.py` lifespan context manager:
  - [ ] Import `start_watching`, `stop_watching`
  - [ ] Call `start_watching()` in startup
  - [ ] Call `stop_watching()` in shutdown

### Testing
- [ ] Start backend
- [ ] Test endpoints:
  ```bash
  # Start monitoring
  curl -X POST http://localhost:8000/api/monitor/start

  # Check status
  curl http://localhost:8000/api/monitor/status

  # Stream events (in background)
  curl -N http://localhost:8000/api/monitor/events/stream
  ```

- [ ] Should show: `{"status":"watching","resources":7}`

**Verification:** All endpoints return 200 OK

---

## Phase 5: Frontend Integration (Days 10-14)

### React Hook
- [ ] Create `frontend/src/hooks/useMonitoring.ts`:
  - [ ] `useMonitoring()` hook
  - [ ] EventSource subscription
  - [ ] Connection state management
  - [ ] Error handling

- [ ] Test hook:
  ```bash
  npm test -- useMonitoring  # or manually in Dashboard
  ```

### Dashboard Updates
- [ ] Update `frontend/src/pages/Dashboard.tsx`:
  - [ ] Import `useMonitoring`
  - [ ] Add SSE listener with custom event
  - [ ] Auto-refresh graph on update
  - [ ] Show live status indicator
  - [ ] Switch to diff panel on alert

- [ ] Test:
  ```bash
  # Open dashboard in browser
  # Check Network tab for EventSource stream
  # Deploy a pod: kubectl create deployment test --image=nginx
  # Should see SSE message within 2 seconds
  ```

**Verification:** Browser shows live indicator, receives SSE messages

---

## Phase 6: Fallback & Resilience (Days 14-21)

### Fallback Poller
- [ ] Create `backend/app/services/fallback_poller.py`:
  - [ ] `FallbackPoller` class
  - [ ] `start()` background loop
  - [ ] `_poll_once()` method
  - [ ] Cluster state hashing

- [ ] Update `watch_service.py`:
  - [ ] Add fallback trigger logic (3 failures = switch to polling)
  - [ ] Graceful degradation

### Error Handling
- [ ] Add comprehensive logging:
  - [ ] All connection attempts
  - [ ] All errors
  - [ ] Fallback activation

- [ ] Test failure scenarios:
  - [ ] Kill K8s API server, watch should reconnect
  - [ ] Disable network, fallback to polling should activate

**Verification:** Logs show graceful fallback to polling

---

## Phase 7: Testing & Validation (Days 21-25)

### Unit Tests
- [ ] Create `backend/tests/test_watch_service.py`:
  - [ ] Test debouncer accumulation
  - [ ] Test watcher singleton
  - [ ] Test alert threshold logic

- [ ] Run:
  ```bash
  cd backend
  pytest tests/test_watch_service.py -v
  ```

### Integration Tests
- [ ] Create `backend/tests/test_watch_integration.py`:
  - [ ] Test with minikube cluster
  - [ ] Test alert triggering
  - [ ] Test SSE message format

- [ ] Run against live cluster:
  ```bash
  minikube start
  pytest tests/test_watch_integration.py -v -s
  ```

### End-to-End Test Scenarios

#### Scenario 1: Deploy Pod
```bash
# Terminal 1: Start backend
cd backend && python -m app.main

# Terminal 2: Watch browser
open http://localhost:3000

# Terminal 3: Deploy
kubectl create deployment test --image=nginx

# Expected: Graph updates within 2-5 seconds
# Expected: Toast notification appears
# Expected: Slack alert sent
```

**Checklist:**
- [ ] Graph refreshes
- [ ] Toast notification appears
- [ ] Slack alert received
- [ ] history.db updated
- [ ] Network tab shows SSE event

#### Scenario 2: Create Dangerous Binding
```bash
# Bind admin role to service account
kubectl create rolebinding danger --clusterrole=admin --serviceaccount=default:default

# Expected: Risk increases
# Expected: NEW_ATTACK_PATHS alert
# Expected: Critical severity alert
```

**Checklist:**
- [ ] Risk score increases
- [ ] Slack shows "CRITICAL"
- [ ] New paths detected in diff
- [ ] monitoring_events table has entry

#### Scenario 3: Fallback to Polling
```bash
# Simulate watch failure (stop API server)
kubectl stop kubeapi  # or equivalent

# Expected: logs show "Watch failed, using fallback polling"
# Expected: Still get updates every 5 minutes

# Resume API server
kubectl start kubeapi

# Expected: Watch API resumes
```

**Checklist:**
- [ ] Fallback activates (check logs)
- [ ] Updates continue via polling
- [ ] Watch resumes when API available

**Verification:** All 3 scenarios pass

---

## Phase 8: Documentation & Finalization (Days 25-28)

### Generated Documentation
- [ ] `MONITORING_ARCHITECTURE.md` ✓ (already created)
- [ ] `BACKEND_AGENT_IMPLEMENTATION.md` ✓ (already created)
- [ ] `MONITORING_API_REFERENCE.md` ✓ (already created)
- [ ] Create `SETUP_GUIDE.md` with quick start
- [ ] Create `TROUBLESHOOTING.md` with common issues

### Code Quality
- [ ] All functions have docstrings
- [ ] Error messages are clear and actionable
- [ ] Logging is comprehensive
- [ ] No hardcoded values (use config)

### Performance
- [ ] Load test with 100+ pod deployment (check response time)
- [ ] Monitor memory usage (graph rebuild)
- [ ] Check SSE broadcast latency

### Security
- [ ] K8s RBAC role is minimal (read-only)
- [ ] No hardcoded credentials
- [ ] Validate all inputs
- [ ] Rate limiting on Slack alerts

**Verification:** Code review passes, all docs complete

---

## Deployment Checklist

### Pre-Deployment
- [ ] All tests passing
- [ ] No hardcoded values
- [ ] Error handling comprehensive
- [ ] Logging enabled
- [ ] Documentation complete

### Deployment
- [ ] Update `backend/requirements.txt` in prod environment
- [ ] Install dependencies: `pip install -r requirements.txt`
- [ ] Run migrations: (automatic on startup)
- [ ] Update `.env` with monitoring settings
- [ ] Set `MOCK_MODE=false` for production
- [ ] Restart backend service

### Post-Deployment Verification
- [ ] Backend starts without errors
- [ ] Frontend connects to monitor endpoint
- [ ] K8s watch starts automatically
- [ ] `/api/monitor/status` returns `watching: true`
- [ ] Test with real cluster change
- [ ] Verify Slack alerts work
- [ ] Check history.db has monitoring events

**Verification:** System monitoring real cluster changes

---

## Success Criteria

✅ **Latency:** Graph updates within 2-5 seconds of cluster change
✅ **Alerts:** Slack receives alerts on risk increase, new paths, new cycles
✅ **Frontend:** Auto-refreshes, shows diff panel, live indicator works
✅ **Resilience:** Falls back to polling if watch API fails
✅ **Reliability:** No missed events, zero data loss
✅ **Performance:** <500ms per analysis, no memory leaks
✅ **Documentation:** Complete, clear, actionable
✅ **Testing:** All scenarios pass

---

## Rollback Plan

If issues arise in production:

1. **Disable watch API** (quick fix):
   ```bash
   # In .env
   ENABLE_WATCH_API=false
   # Restart backend
   ```

2. **Revert code** (if needed):
   ```bash
   git revert <commit-hash>  # Revert the implementation commit
   pip install -r requirements.txt  # Original dependencies
   # Restart backend
   ```

3. **Clear monitoring data** (optional):
   ```bash
   sqlite3 data/history.db "DROP TABLE monitoring_events"
   # Restart backend (will recreate table)
   ```

---

## Timeline

| Phase | Days | Owner | Dependency |
|-------|------|-------|-----------|
| 1. Env & Deps | 1-2 | Backend | None |
| 2. Database | 2-3 | Backend | Phase 1 |
| 3. Watch Service | 3-7 | Backend | Phase 2 |
| 4. Broadcast | 7-10 | Backend | Phase 3 |
| 5. Frontend | 10-14 | Frontend | Phase 4 |
| 6. Resilience | 14-21 | Backend | Phase 5 |
| 7. Testing | 21-25 | QA | All |
| 8. Finalization | 25-28 | All | Phase 7 |

**Critical Path:** 28 days total (backend 21 days, frontend 14 days, parallel after day 7)

---

## Questions to Answer Before Starting

1. **Kubernetes Access:** Does the container/pod have access to K8s API?
   - [ ] Test: `kubectl cluster-info` succeeds
   - [ ] Test: Service account has RBAC permissions

2. **K8s Version:** Which version of K8s?
   - [ ] Check: `kubectl version --short`
   - [ ] Watch API available in all versions (v1.0+)

3. **Network:** Is K8s API accessible from backend?
   - [ ] Test: `curl https://kubernetes.default:443` (in-cluster)
   - [ ] Test: `curl $(kubectl cluster-info | grep -o 'https://[^/]*')` (external)

4. **Slack Integration:** Is Slack webhook configured?
   - [ ] Check: `echo $SLACK_WEBHOOK_URL` in backend env
   - [ ] Test: Send test message via `send_critical_alert()`

5. **Frontend Ready:** Is frontend able to handle SSE?
   - [ ] Check: EventSource API available in supported browsers
   - [ ] Test: Open browser console, check for errors

---

## Success Stories

Once implemented, the system enables:

✅ **Incident Response:** Detect attacks within seconds
✅ **Compliance:** Continuous monitoring for audit logs
✅ **Development:** Auto-refresh during local testing
✅ **Security:** Alert on dangerous role bindings instantly
✅ **Research:** Collect data on real cluster changes

---

## Support & Escalation

### Issues During Implementation

**Q: Watch API not connecting**
- A: Check K8s cluster is running (`kubectl cluster-info`)
- A: Check kubeconfig path or in-cluster auth
- A: See TROUBLESHOOTING.md

**Q: Events not arriving at frontend**
- A: Check SSE endpoint: `curl -N http://localhost:8000/api/monitor/events/stream`
- A: Check browser DevTools → Network → EventSource
- A: Check backend logs

**Q: Slack alerts not sending**
- A: Check `SLACK_WEBHOOK_URL` is set
- A: Test: `send_critical_alert()` directly in Python
- A: Check webhook is still valid (Slack webhooks expire)

**Q: Performance issues**
- A: Check cluster size (1000+ nodes may need optimization)
- A: Increase debounce window: `WATCH_DEBOUNCE_MS=5000`
- A: Use fallback polling during peak load

---

## Getting Help

1. **Architecture Questions:** Read `MONITORING_ARCHITECTURE.md`
2. **Implementation Details:** Read `BACKEND_AGENT_IMPLEMENTATION.md`
3. **API Usage:** Read `MONITORING_API_REFERENCE.md`
4. **Troubleshooting:** Check `TROUBLESHOOTING.md` or logs
5. **Code Issues:** Check test files for examples

---

