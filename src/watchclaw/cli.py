import argparse


def main() -> None:
    parser = argparse.ArgumentParser(prog="watchclaw")
    parser.add_argument("command", nargs="?", default="status")
    args = parser.parse_args()
    if args.command == "status":
        print("watchclaw: scaffold ready")
    else:
        print(f"watchclaw: unknown command {args.command}")
        raise SystemExit(2)


if __name__ == "__main__":
    main()
