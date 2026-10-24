"""Remote client for the organizer-hosted mystery simulator.

This module intentionally contains no noise-model parameters. The service URL
and optional event token are supplied by the organizer at runtime.
"""

from __future__ import annotations

import json
import os
from collections import Counter
from dataclasses import dataclass
from urllib.request import Request, urlopen

from qiskit import qasm2


@dataclass
class _MysteryResult:
    counts: dict[str, int]

    def get_counts(self):
        return self.counts


@dataclass
class _MysteryJob:
    counts: dict[str, int]

    def result(self):
        return _MysteryResult(self.counts)


class RemoteMysteryBackend:
    def __init__(self, url: str | None = None, token: str | None = None):
        self.url = url or os.environ.get("MYSTERY_BACKEND_URL", "")
        self.token = token or os.environ.get("MYSTERY_BACKEND_TOKEN", "")

    def run(self, circuit, shots: int = 256):
        if not self.url:
            raise RuntimeError("Set MYSTERY_BACKEND_URL before using the mystery backend.")
        payload = {"qasm": qasm2.dumps(circuit), "shots": int(shots)}
        headers = {"Content-Type": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        request = Request(self.url.rstrip("/") + "/run", data=json.dumps(payload).encode(), headers=headers, method="POST")
        with urlopen(request, timeout=45) as response:
            reply = json.loads(response.read().decode())
        if not reply.get("ok"):
            raise RuntimeError(reply.get("error", "Mystery backend request failed."))
        return _MysteryJob(dict(Counter(reply["memory"])))


mystery_backend = RemoteMysteryBackend()
