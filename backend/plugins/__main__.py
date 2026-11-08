"""Inspect an assembled backend without downloading weights."""
import argparse
import json

from backend.application import create_application


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check-imports", action="store_true")
    args = parser.parse_args()
    with create_application() as app:
        report = {name: {"state": state.value, "detail": detail}
            for name, (state, detail) in app.states.items()}
        if args.check_imports:
            for name, capability in app.capabilities.items():
                if not hasattr(capability, "module"):
                    continue
                try:
                    missing = capability.missing_dependencies()
                    if missing:
                        report[name] = {"state": "missing_dependency", "detail": ", ".join(missing)}
                        continue
                    capability.module()
                except ModuleNotFoundError as exc:
                    report[name] = {"state": "missing_dependency", "detail": str(exc)}
                except Exception as exc:
                    report[name] = {"state": "failed", "detail": f"{type(exc).__name__}: {exc}"}
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return int(any(item["state"] != "available" for item in report.values()))


if __name__ == "__main__":
    raise SystemExit(main())
