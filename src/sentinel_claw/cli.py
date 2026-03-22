import argparse


def main() -> None:
    parser = argparse.ArgumentParser(prog="sentinel-claw")
    parser.add_argument("command", nargs="?", default="status")
    args = parser.parse_args()
    if args.command == "status":
        print("sentinel-claw: scaffold ready")
    else:
        print(f"sentinel-claw: unknown command {args.command}")
        raise SystemExit(2)


if __name__ == "__main__":
    main()
