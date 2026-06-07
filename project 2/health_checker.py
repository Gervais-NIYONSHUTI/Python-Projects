import json
import os
import smtplib
import time
import urllib.error
import urllib.request
from pathlib import Path

SERVER_CONFIG = Path(__file__).resolve().parent / "servers.json"
TIMEOUT_SECONDS = 5
MAX_RETRIES = 2
SLOW_THRESHOLD_MS = 500


def load_servers():
    env = os.getenv("SERVERS")
    if env:
        servers = [url.strip() for url in env.split(",") if url.strip()]
        print(f"Loaded {len(servers)} servers from SERVERS\n")
        return servers

    if SERVER_CONFIG.exists():
        with SERVER_CONFIG.open("r", encoding="utf-8") as f:
            data = json.load(f)
        servers = data.get("servers", [])
        print(f"Loaded {len(servers)} servers from servers.json\n")
        return servers

    raise RuntimeError(f"No servers found. Set SERVERS or create {SERVER_CONFIG}")


def check_server(url):
    for attempt in range(MAX_RETRIES + 1):
        try:
            start = time.time()
            with urllib.request.urlopen(url, timeout=TIMEOUT_SECONDS) as resp:
                elapsed = int((time.time() - start) * 1000)
                code = resp.getcode()
                return {
                    "url": url,
                    "statusCode": code,
                    "elapsedMs": elapsed,
                    "isHealthy": 200 <= code <= 299,
                    "isSlow": elapsed > SLOW_THRESHOLD_MS,
                    "error": None,
                }
        except urllib.error.HTTPError as exc:
            error = f"HTTP {exc.code}"
            status = exc.code
        except urllib.error.URLError as exc:
            error = str(exc.reason)
            status = None
        except Exception as exc:
            error = str(exc)
            status = None

        if attempt < MAX_RETRIES:
            time.sleep(1)

    return {
        "url": url,
        "statusCode": status,
        "elapsedMs": None,
        "isHealthy": False,
        "isSlow": False,
        "error": error,
    }


def send_email_alert(url, reason):
    user = os.getenv("ALERT_EMAIL_USER")
    pwd = os.getenv("ALERT_EMAIL_PASSWORD")
    to = os.getenv("ALERT_EMAIL_TO")
    if not all([user, pwd, to]):
        print("  (alert skipped — set ALERT_EMAIL_USER, ALERT_EMAIL_PASSWORD, ALERT_EMAIL_TO)")
        return

    msg = f"Subject: [ALERT] Service Down: {url}\n\n{url} is down.\nReason: {reason}"
    try:
        host = os.getenv("ALERT_EMAIL_HOST", "smtp.gmail.com")
        port = int(os.getenv("ALERT_EMAIL_PORT", "587"))
        with smtplib.SMTP(host, port) as smtp:
            smtp.starttls()
            smtp.login(user, pwd)
            smtp.sendmail(user, to, msg)
        print(f"  Alert sent to {to}")
    except Exception as exc:
        print(f"  Could not send alert: {exc}")


def main():
    try:
        servers = load_servers()
    except RuntimeError as exc:
        print(exc)
        return

    if not servers:
        print("No servers to check.")
        return

    failed = []
    for url in servers:
        result = check_server(url)
        if result["error"]:
            print(f"{url} — {result['error']}")
        elif result["isHealthy"]:
            slow = " [slow]" if result["isSlow"] else ""
            print(f"{url} — OK ({result['statusCode']}) — {result['elapsedMs']}ms{slow}")
        else:
            print(f"{url} — DOWN ({result['statusCode']})")

        if result["error"] or not result["isHealthy"]:
            failed.append(url)
            send_email_alert(url, result["error"] or f"HTTP {result['statusCode']}")

    print()
    print(f"Failed services: {', '.join(failed)}" if failed else "All services are healthy!")


if __name__ == "__main__":
    main()
