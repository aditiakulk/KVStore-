# from the kvstore root
cat > gateway/hash_ring.py << 'EOF'
import bisect
import hashlib


class HashRing:
    """
    consistent hash ring w/ virtual nodes.

    each real node gets hashed to `vnodes` points scattered around a
    circle (0 to 2^128, since we're using md5). a key is looked up by
    hashing it onto the same circle and walking clockwise to the first
    node point. bisect keeps lookup O(log n) instead of scanning the
    whole ring.

    note: even w/ 150+ vnodes, load isn't perfectly even (~5pts off
    from a perfect split in my testing) -- that's expected, not a bug.
    """

    def __init__(self, nodes=None, vnodes=150):
        self.vnodes = vnodes
        self.ring = {}
        self.sorted_points = []
        self._nodes = set()
        for node in nodes or []:
            self.add_node(node)

    def _hash(self, key: str) -> int:
        return int(hashlib.md5(key.encode()).hexdigest(), 16)

    def add_node(self, node: str):
        if node in self._nodes:
            return
        self._nodes.add(node)
        for i in range(self.vnodes):
            point = self._hash(f"{node}#{i}")
            self.ring[point] = node
        self.sorted_points = sorted(self.ring.keys())

    def remove_node(self, node: str):
        if node not in self._nodes:
            return
        self._nodes.discard(node)
        for i in range(self.vnodes):
            point = self._hash(f"{node}#{i}")
            self.ring.pop(point, None)
        self.sorted_points = sorted(self.ring.keys())

    def get_node(self, key: str) -> str:
        if not self.ring:
            raise ValueError("hash ring is empty")
        point = self._hash(key)
        idx = bisect.bisect(self.sorted_points, point)
        if idx == len(self.sorted_points):
            idx = 0
        return self.ring[self.sorted_points[idx]]
EOF
