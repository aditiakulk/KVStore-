# REST front door for the cluster. routes each key to whichever node
# owns it, then forwards the request over raw TCP and translates the
# response back into JSON.
#
# TODO: route_for_key is just hash % num_nodes right now, which works
# but reshuffles every key when a node is added/removed. swap in a real
# consistent hash ring (virtual nodes on a circle) once there's more
# than one node running.

import os
import socket
import hashlib
from contextlib import contextmanager
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI(title="KV Store Gateway")

# wide open for local dev w/ the react frontend, tighten before deploying
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# node list comes from KV_NODES env var: "host1:port1,host2:port2,..."
# defaults to one local node. compose file sets this to all 3 replicas.
def _load_nodes() -> list[dict]:
    raw = os.environ.get("KV_NODES", "127.0.0.1:7070")
    nodes = []
    for entry in raw.split(","):
        host, port = entry.strip().split(":")
        nodes.append({"host": host, "port": int(port)})
    return nodes


NODES = _load_nodes()


def route_for_key(key: str) -> dict:
    if len(NODES) == 1:
        return NODES[0]
    idx = int(hashlib.sha1(key.encode()).hexdigest(), 16) % len(NODES)
    return NODES[idx]


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
    node = route_for_key(key)
    response = send_command(node, f"GET {key}")
    if response.startswith("-NOTFOUND"):
        raise HTTPException(status_code=404, detail="Key not found")
    if response.startswith("+"):
        return {"key": key, "value": response[1:], "node": f"{node['host']}:{node['port']}"}
    raise HTTPException(status_code=500, detail=response)


@app.put("/kv")
def set_key(req: SetRequest):
    node = route_for_key(req.key)
    response = send_command(node, f"SET {req.key} {req.value}")
    if response.startswith("+OK"):
        return {"key": req.key, "value": req.value, "node": f"{node['host']}:{node['port']}"}
    raise HTTPException(status_code=500, detail=response)


@app.delete("/kv/{key}")
def delete_key(key: str):
    node = route_for_key(key)
    response = send_command(node, f"DEL {key}")
    if response.startswith("+OK"):
        return {"key": key, "deleted": True}
    if response.startswith("-NOTFOUND"):
        raise HTTPException(status_code=404, detail="Key not found")
    raise HTTPException(status_code=500, detail=response)


@app.get("/health")
def health():
    results = []
    for node in NODES:
        try:
            with node_connection(node):
                results.append({"node": f"{node['host']}:{node['port']}", "status": "up"})
        except OSError:
            results.append({"node": f"{node['host']}:{node['port']}", "status": "down"})
    return {"nodes": results}
