# kv-store

A sharded, multi-threaded key-value store, built as three services:

```
React dashboard  --HTTP-->  FastAPI gateway  --TCP-->  C++ kv_node (x N)
```

- **server/** — the actual store. C++ TCP server backed by a hash table
  with striped locking (splits the map into N independently-locked
  chunks instead of one global lock, so threads on different chunks
  don't block each other).
- **gateway/** — FastAPI service that routes each key to the node that
  owns it. Right now it's just `hash(key) % num_nodes`; real consistent
  hashing is next on the list.
- **frontend/** — React dashboard for running commands and watching
  which node handles each request.

## why

Wanted to build something that actually uses the computer architecture
background from my RISC-V/RTL work instead of keeping hardware and
software projects totally separate. The `STRIPE_PAD` flag in
`striped_hashmap.h` is the connection: padding each lock to a cache line
stops "false sharing" (two unrelated locks getting bounced between cores
because they happen to share a 64-byte line), which is the same
memory-hierarchy reasoning as cache design in a CPU, just applied to a
backend system instead.

## running it

**node:**
```
cd server
g++ -std=c++17 -O2 -pthread src/main.cpp -o kv_node
./kv_node 7070 64
```

**gateway** (separate terminal):
```
cd gateway
pip install -r requirements.txt
KV_NODES="127.0.0.1:7070" uvicorn gateway:app --reload --port 8000
```

**frontend** (separate terminal):
```
cd frontend
npm install
npm run dev
```

or run the whole thing with docker:
```
docker compose -f docker/docker-compose.yml up --build
```

## todo

- [x] single node, striped locks, TCP server
- [ ] real consistent hashing in `route_for_key` (hash ring w/ virtual
      nodes, so adding/removing a node doesn't reshuffle every key)
- [ ] replication — write to next node in the ring too, so one node
      dying doesn't lose data
- [ ] actually benchmark the padding difference on a real multi-core
      machine (tested this on a 1-core sandbox while building it, no
      difference showed up for obvious reasons — need real hardware).
      `perf stat -e cache-misses,cache-references` for a real number
      instead of just wall clock
- [ ] deploy the compose setup somewhere (EC2 free tier / fly.io)

## layout
```
kvstore/
├── server/       C++ node — striped hash table + TCP server
├── gateway/      FastAPI routing layer
├── frontend/     React dashboard
└── docker/       compose file for running the whole cluster
```
