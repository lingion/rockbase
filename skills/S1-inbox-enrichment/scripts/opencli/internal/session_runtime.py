#!/usr/bin/env python3
import json
import subprocess
import time


class OpenCliEasykolRuntime:
    def __init__(self, session: str, probe_js: str, max_wait_seconds: int = 25, poll_seconds: int = 3):
        self.session = session
        self.probe_js = probe_js
        self.max_wait_seconds = max_wait_seconds
        self.poll_seconds = poll_seconds

    def run(self, cmd: list[str]) -> subprocess.CompletedProcess:
        return subprocess.run(cmd, check=True, capture_output=True, text=True)

    def open(self, url: str) -> None:
        self.run(["opencli", "browser", self.session, "open", url])

    def wait(self, seconds: int) -> None:
        self.run(["opencli", "browser", self.session, "wait", "time", str(seconds)])

    def eval_probe(self) -> dict:
        return json.loads(self.run(["opencli", "browser", self.session, "eval", self.probe_js]).stdout)

    def probe_row(self, url: str) -> tuple[dict, list[dict]]:
        self.open(url)
        start = time.time()
        attempts = []

        while True:
            payload = self.eval_probe()
            payload["elapsedSeconds"] = round(time.time() - start, 1)
            attempts.append(payload)

            if payload["status"] == "hit":
                return payload, attempts

            if time.time() - start >= self.max_wait_seconds:
                if payload["status"] == "pending_empty":
                    payload["status"] = "no_email"
                return payload, attempts

            self.wait(self.poll_seconds)
