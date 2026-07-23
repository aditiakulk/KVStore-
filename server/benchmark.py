# load generator for kv_node. hits the node directly (not through the
# gateway) so HTTP/JSON overhead doesn't skew the numbers.
#
# usage: python3 benchmark.py [host] [port] [num_threads] [ops_per_thread]
#
# run this once against a build with STRIPE_PAD defined and once with
# it commented out in striped_hashmap.h, compare throughput. needs an
# actual multi-core machine to see a difference -- on a single core
# there's no cache contention to eliminate in the first place.
#
# for a real number instead of wall-clock guessing, run the server under
# `perf stat -e cache-misses,cache-references` for each build.

import socket
import sys
import threading
import time


def worker(host, port, ops, key_prefix, results, idx):
    sock = socket.create_connection((host, port))
    start = time.perf_counter()
    for i in range(ops):
        key = f"{key_prefix}{i % 100}"  # 100 keys per thread, reused
        sock.sendall(f"SET {key} v{i}\n".encode())
        sock.recv(64)
        sock.sendall(f"GET {key}\n".encode())
        sock.recv(64)
    elapsed = time.perf_counter() - start
    results[idx] = elapsed
    sock.close()


def main():
    host = sys.argv[1] if len(sys.argv) > 1 else "127.0.0.1"
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 7070
    num_threads = int(sys.argv[3]) if len(sys.argv) > 3 else 8
    ops_per_thread = int(sys.argv[4]) if len(sys.argv) > 4 else 5000

    results = [0.0] * num_threads
    threads = [
        threading.Thread(target=worker, args=(host, port, ops_per_thread, f"t{i}_", results, i))
        for i in range(num_threads)
    ]

    overall_start = time.perf_counter()
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    overall_elapsed = time.perf_counter() - overall_start

    total_ops = num_threads * ops_per_thread * 2  # SET + GET each iteration
    print(f"threads={num_threads} ops_per_thread={ops_per_thread} total_ops={total_ops}")
    print(f"wall_time={overall_elapsed:.3f}s")
    print(f"throughput={total_ops / overall_elapsed:,.0f} ops/sec")


if __name__ == "__main__":
    main()
