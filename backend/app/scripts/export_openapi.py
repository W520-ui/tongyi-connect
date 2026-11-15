import argparse
import json
from pathlib import Path

from app.core.config import Settings
from app.main import create_app


def export_openapi(output: Path, settings: Settings | None = None) -> Path:
    schema = create_app(settings).openapi()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(schema, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return output


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Export the API schema without starting the server"
    )
    parser.add_argument(
        "--output", type=Path, default=Path(__file__).absolute().parents[2] / "openapi.json"
    )
    args = parser.parse_args()
    print(export_openapi(args.output))


if __name__ == "__main__":
    main()
