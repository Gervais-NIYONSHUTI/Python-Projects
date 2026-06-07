import argparse
import csv
import json
from datetime import datetime
from pathlib import Path

DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
SHORT_DATE_FORMAT = "%Y-%m-%d %H:%M"


def parseArgs():
    parser = argparse.ArgumentParser(description="Analyze a log file.")
    parser.add_argument(
        "file",
        nargs="?",
        default=None,
        help="Log file path (default: ./app.log)",
    )
    parser.add_argument("--level", help="Filter by log level")
    parser.add_argument("--from", dest="fromTime", help="Start time YYYY-MM-DD HH:MM")
    parser.add_argument("--to", dest="toTime", help="End time YYYY-MM-DD HH:MM")
    parser.add_argument("--export", dest="exportPath", help="CSV export path")
    return parser.parse_args()


def parseLogLine(line):
    line = line.strip()
    if not line:
        return None

    try:
        record = json.loads(line)
        timestamp = record["timestamp"]
        level = record["level"].upper()
        message = record["message"]
    except Exception:
        parts = line.split()
        if len(parts) < 4:
            return None
        timestamp = f"{parts[0]} {parts[1]}"
        level = parts[2].upper()
        message = " ".join(parts[3:])

    return {"timestamp": timestamp, "level": level, "message": message}


def parseTime(text):
    if not text:
        return None
    try:
        return datetime.strptime(text, SHORT_DATE_FORMAT)
    except ValueError:
        return datetime.strptime(text, DATE_FORMAT)


def main():
    args = parseArgs()
    fromTime = parseTime(args.fromTime)
    toTime = parseTime(args.toTime)

    if args.file:
        filePath = Path(args.file)
    else:
        filePath = Path(__file__).resolve().parent / "app.log"

    if not filePath.exists():
        print(f"Log file not found: {filePath}")
        print("Please provide a log file path or create app.log in the script folder.")
        return

    errorCount = 0
    warningCount = 0
    infoCount = 0
    errorMessages = {}
    errorTimes = []

    with open(filePath, encoding="utf-8") as log_file:
        for line in log_file:
            entry = parseLogLine(line)
            if not entry:
                continue

            if args.level and entry["level"] != args.level.upper():
                continue

            entryTime = parseTime(entry["timestamp"])
            if entryTime is None:
                continue
            if fromTime and entryTime < fromTime:
                continue
            if toTime and entryTime > toTime:
                continue

            if entry["level"] == "ERROR":
                errorCount += 1
                errorMessages[entry["message"]] = errorMessages.get(entry["message"], 0) + 1
                errorTimes.append(entryTime.strftime("%H:%M:%S"))
            elif entry["level"] == "WARNING":
                warningCount += 1
            elif entry["level"] == "INFO":
                infoCount += 1

    totalLogs = errorCount + warningCount + infoCount
    topError = max(errorMessages, key=errorMessages.get) if errorMessages else "none"
    shownTimes = ", ".join(errorTimes[:10])
    if len(errorTimes) > 10:
        shownTimes += f" (+{len(errorTimes) - 10} more)"

    print(f"Total logs:          {totalLogs}")
    print(f"Errors:              {errorCount}")
    print(f"Warnings:            {warningCount}")
    print(f"Info:                {infoCount}")
    print(f"Most frequent error: \"{topError}\"")
    print(f"Failure timestamps:  {shownTimes or 'none'}")

    if args.exportPath:
        with open(args.exportPath, "w", newline="", encoding="utf-8") as csv_file:
            writer = csv.writer(csv_file)
            writer.writerow(["metric", "value"])
            writer.writerow(["total_logs", totalLogs])
            writer.writerow(["errors", errorCount])
            writer.writerow(["warnings", warningCount])
            writer.writerow(["info", infoCount])
            writer.writerow(["most_common_error", topError])
        print(f"Saved summary to {args.exportPath}")


if __name__ == "__main__":
    main()
