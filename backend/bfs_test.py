import json
import networkx as nx
from collections import deque

def load_graph():
    data = json.load(open("docs/mock-cluster-graph.json"))
    G = nx.DiGraph()
    for n in data["nodes"]:
        label = n.get("name") or n.get("label") or n["id"]
        G.add_node(n["id"], label=label, type=n.get("type", ""))
    for e in data["edges"]:
        if "source" in e and "target" in e:
            G.add_edge(e["source"], e["target"])
    return G

G = load_graph()
undirected_G = G.to_undirected()

def bfs(graph, source, hops):
    visited = {source: 0}
    q = deque([source])
    while q:
        u = q.popleft()
        if visited[u] >= hops:
            continue
        for v in graph.neighbors(u):
            if v not in visited:
                visited[v] = visited[u] + 1
                q.append(v)
    res = {}
    for k, v in visited.items():
        if v > 0:
            res.setdefault(v, []).append(graph.nodes[k]["label"])
    return res

print("DIRECTED BFS:")
print(bfs(G, "pod-webfront", 3))
print("UNDIRECTED BFS:")
print(bfs(undirected_G, "pod-webfront", 3))
