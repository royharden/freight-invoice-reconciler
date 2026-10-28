"""Future builder-only CLI wrapper. Not executed in Dirty construction."""

import argparse

from freightrec.cli import main


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    raise SystemExit(main(["demo", "--builder-only", "--input", args.input, "--out", args.out]))
