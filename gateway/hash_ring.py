import os
import socket
from contextlib import contextmanager
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from hash_ring import HashRing

app = FastAPI(title="KV Store Gateway")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def _load_nodes() -> dict:
    raw = os.environ.get("KV_NODES", "127.0.0.1:7070")
    nodes = {}
    for entry in raw.split(","):
        host, port = entry.strip().split(":")
        nodes[entry.strip()] = {"host": host, "port": int(port)}
    return nodes


NODES = _load_nodes()
ring = HashRing(nodes=list(NODES.keys()))
REPLICATION_FACTOR = min(int(os.environ.get("REPLICATION_FACTOR", 2)), len(NODES))


def preference_list(key: str) -> list[dict]:
    node_ids = ring.get_preference_list(key, REPLICATION_FACTOR)
    return [NODES[nid] for nid in node_ids]


def node_addr(node: dict) -> str:
    return f"{node['host']}:{node['port']}"


@contextmanager
def node_connection(node: dict):
    sock = socket.create_connection((node["host"], node["port"]), timeout=2)
    try:
        yield sock
    finally:
        sock.close()


def send_command(node: dict, command: str) -> str:
    with node_connection(node) as sock:
        sock.sendall((command + "\n").encode())
        response = sock.recv(4096).decode()
        return response.strip()


class SetRequest(BaseModel):
    key: str
    value: str


@app.get("/kv/{key}")
def get_key(key: str):
    last_error = None
    for node in preference_list(key):
        try:
            response = send_command(node, f"GET {key}")
        except OSError as e:
            last_error = e
            continue
        if response.startswith("-NOTFOUND"):
            raise HTTPException(status_code=404, detail="Key not found")
        if response.startswith("+"):
            return {"key": key, "value": response[1:], "node": node_addr(node)}
        raise HTTPException(status_code=500, detail=response)
    raise HTTPException(status_code=503, detail=f"all replicas unreachable: {last_error}")


@app.put("/kv")
def set_key(req: SetRequest):
    nodes = preference_list(req.key)
    primary, replicas = nodes[0], nodes[1:]

    response = send_command(primary, f"SET {req.key} {req.value}")
    if not response.startswith("+OK"):
        raise HTTPException(status_code=500, detail=response)

    replicated_to = []
    for node in replicas:
        try:
            send_command(node, f"SET {req.key} {req.value}")
            replicated_to.append(node_addr(node))
        except OSError:
            pass

    return {
        "key": req.key,
        "value": req.value,
        "node": node_addr(primary),
        "replicated_to": replicated_to,
    }


@app.delete("/kv/{key}")
def delete_key(key: str):
    nodes = preference_list(key)
    primary, replicas = nodes[0], nodes[1:]

    response = send_command(primary, f"DEL {key}")
    if response.startswith("-NOTFOUND"):
        raise HTTPException(status_code=404, detail="Key not found")
    if not response.startswith("+OK"):
        raise HTTPException(status_code=500, detail=response)

    for node in replicas:
        try:
            send_command(node, f"DEL {key}")
        except OSError:
            pass

    return {"key": key, "deleted": True}


@app.get("/health")
def health():
    results = []
    for node in NODES.values():
        try:
            with node_connection(node):
                results.append({"node": f"{node['host']}:{node['port']}", "status": "up"})
        except OSError:
            results.append({"node": f"{node['host']}:{node['port']}", "status": "down"})
    return {"nodes": results}
