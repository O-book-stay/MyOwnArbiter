import json
from collections import deque

d = json.load(open('src/macro/arbchain_routing.json'))
by = {}
for s in d:
    by.setdefault(tuple(s['layer']), []).append(s['box'])

boxes = []
lay = []
for L, bs in by.items():
    if L in ((235, 4), (236, 0)):
        continue
    for b in bs:
        boxes.append(b)
        lay.append(L)
n = len(boxes)

def touch(a, b):
    return not (a[2] <= b[0] or b[2] <= a[0] or a[3] <= b[1] or b[3] <= a[1])

STACK = {(67, 44): ((67, 20), (68, 20)),
         (68, 44): ((68, 20), (69, 20)),
         (69, 44): ((69, 20), (70, 20)),
         (70, 44): ((70, 20), (71, 20))}

met = {L: [] for L in ((67, 20), (68, 20), (69, 20), (70, 20), (71, 20))}
cuts = {L: [] for L in STACK}
for i in range(n):
    if lay[i] in met:
        met[lay[i]].append(i)
    if lay[i] in cuts:
        cuts[lay[i]].append(i)

adj = [[] for _ in range(n)]
for L, idxs in met.items():
    for a in range(len(idxs)):
        i = idxs[a]
        bi = boxes[i]
        for b2 in range(a + 1, len(idxs)):
            j = idxs[b2]
            bj = boxes[j]
            if touch(bi, bj):
                adj[i].append(j)
                adj[j].append(i)
for cut, (la, lb) in STACK.items():
    for ci in cuts[cut]:
        bc = boxes[ci]
        for i in met[la]:
            if touch(bc, boxes[i]):
                adj[ci].append(i)
                adj[i].append(ci)
        for i in met[lb]:
            if touch(bc, boxes[i]):
                adj[ci].append(i)
                adj[i].append(ci)

def idx_of(layer, x, y):
    for i in met.get(layer, []):
        b = boxes[i]
        if b[0] <= x <= b[2] and b[1] <= y <= b[3]:
            return i
    return None

s = idx_of((69, 20), 5.0, 3.59)    # top[1] LOW line (gap 1)
t = idx_of((69, 20), 6.0, 4.04)    # bot[1] HIGH line
print('s', s, 't', t)
prev = {s: None}
q = deque([s])
while q:
    u = q.popleft()
    if u == t:
        break
    for v in adj[u]:
        if v not in prev:
            prev[v] = u
            q.append(v)
if t not in prev:
    print('NOT CONNECTED')
else:
    path = []
    u = t
    while u is not None:
        path.append(u)
        u = prev[u]
    path.reverse()
    print(f'path len {len(path)}:')
    for u in path:
        b = boxes[u]
        print(f"  {lay[u]} x=[{b[0]:7.3f},{b[2]:7.3f}] y=[{b[1]:7.3f},{b[3]:7.3f}]")
