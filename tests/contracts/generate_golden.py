import json

from tests.contracts.dto_contract_helpers import GOLDEN_PATH, discover_snapshot


def main():
    GOLDEN_PATH.write_text(
        json.dumps(discover_snapshot(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"updated {GOLDEN_PATH}")


if __name__ == "__main__":
    main()
