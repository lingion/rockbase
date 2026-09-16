from __future__ import annotations

import json

from x_kol_discovery.layer2.scrapecreators_client import ScrapeCreatorsClient, load_scrapecreators_env


def main() -> int:
    _, env_source = load_scrapecreators_env()
    client = ScrapeCreatorsClient()
    payload = {
        "env_source": env_source,
        "credit_balance": client.credit_balance(),
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
