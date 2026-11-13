"""bev-edge: run the temperature forecaster on a stream of one-second readings.

AI-assisted (Claude, 13 November 2026); see docs/PROVENANCE.md.

    bev-edge info --bundle BUNDLE
    bev-edge run  --bundle BUNDLE --capacity-kwh 354 --rr-pct 3 --input readings.csv
    sensor-reader | bev-edge run --bundle BUNDLE --capacity-kwh 354 --rr-pct 3 --input -

Input is CSV with a header row and the columns
    time_s, temperature_c, air_c, and either equivalent_current_a or pack_power_kw
(pack power is converted with Equation (2)). Output is one JSON object per line.
"""
import argparse
import csv
import json
import os
import sys

from .bundle import Bundle
from .forecaster import Forecaster
from .thermal import equivalent_current


def readings(stream, capacity_kwh):
    reader = csv.DictReader(stream)
    fields = set(reader.fieldnames or ())
    missing = {"time_s", "temperature_c", "air_c"} - fields
    if missing or not fields & {"equivalent_current_a", "pack_power_kw"}:
        raise SystemExit(f"Input needs time_s, temperature_c, air_c and equivalent_current_a or pack_power_kw; "
                         f"missing {sorted(missing) or 'a current column'}")
    for row in reader:
        if row.get("equivalent_current_a", "") != "":
            current = float(row["equivalent_current_a"])
        else:
            current = equivalent_current(float(row["pack_power_kw"]), capacity_kwh)
        yield float(row["time_s"]), current, float(row["temperature_c"]), float(row["air_c"])


def main(argv=None):
    parser = argparse.ArgumentParser(prog="bev-edge", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    info = sub.add_parser("info", help="check a bundle's hashes and describe it")
    info.add_argument("--bundle", required=True)
    run = sub.add_parser("run", help="forecast from a CSV file or standard input")
    run.add_argument("--bundle", required=True)
    run.add_argument("--capacity-kwh", type=float, required=True, help="pack capacity, an input to the model")
    run.add_argument("--rr-pct", type=float, required=True, help="rolling resistance in percent, an input to the model")
    run.add_argument("--input", default="-", help="CSV path, or - for standard input (default)")
    run.add_argument("--every", type=int, default=10, help="seconds between forecasts (default 10, as in the paper)")
    args = parser.parse_args(argv)

    bundle = Bundle(args.bundle)
    if args.command == "info":
        print(json.dumps({**bundle.describe(), "hashes_checked": True}, indent=2))
        return 0
    forecaster = Forecaster(bundle, args.capacity_kwh, args.rr_pct, args.every)
    stream = sys.stdin if args.input == "-" else open(args.input, newline="", encoding="utf-8")
    try:
        with stream:
            for reading in readings(stream, args.capacity_kwh):
                result = forecaster.push(*reading)
                if result is not None:
                    print(json.dumps(result), flush=True)
    except BrokenPipeError:   # the reader closed the pipe (e.g. `| head`); stop quietly
        os.dup2(os.open(os.devnull, os.O_WRONLY), sys.stdout.fileno())
    return 0


if __name__ == "__main__":
    sys.exit(main())
