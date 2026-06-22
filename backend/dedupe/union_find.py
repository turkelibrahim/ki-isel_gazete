"""Small Union-Find implementation used to build duplicate clusters."""

from __future__ import annotations


class UnionFind:
    """Disjoint-set data structure with path compression and union by rank."""

    def __init__(self, size: int) -> None:
        self.parent = list(range(size))
        self.rank = [0] * size

    def find(self, item: int) -> int:
        """Return the representative parent for an item."""
        if self.parent[item] != item:
            self.parent[item] = self.find(self.parent[item])
        return self.parent[item]

    def union(self, left: int, right: int) -> int:
        """Merge two sets and return their representative parent."""
        root_left = self.find(left)
        root_right = self.find(right)
        if root_left == root_right:
            return root_left
        if self.rank[root_left] < self.rank[root_right]:
            self.parent[root_left] = root_right
            return root_right
        if self.rank[root_left] > self.rank[root_right]:
            self.parent[root_right] = root_left
            return root_left
        self.parent[root_right] = root_left
        self.rank[root_left] += 1
        return root_left

    def groups(self) -> dict[int, list[int]]:
        """Return all current groups keyed by representative id."""
        grouped: dict[int, list[int]] = {}
        for index in range(len(self.parent)):
            grouped.setdefault(self.find(index), []).append(index)
        return grouped
