"""
Batch validation script for 20 VN30 stocks sequential workload.

Purpose: Validate SRVC-06 — prove the system handles a realistic 20-stock
workload within Docker memory limits without OOM kills.

Usage:
    python scripts/batch-validate.py --base-url http://localhost:8001
    python scripts/batch-validate.py --base-url http://localhost:8001 --timeout 600

Dependencies: httpx (project dependency), subprocess (stdlib), argparse (stdlib)
"""
import argparse
import subprocess
import sys
import time

import httpx

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

VN30_TICKERS = [
    "VHM", "VNM", "VCB", "BID", "VPB",
    "TCB", "MBB", "CTG", "HPG", "MSN",
    "VIC", "GAS", "SAB", "FPT", "MWG",
    "REE", "VJC", "HDB", "STB", "ACB",
]

SERVICES = [
    "stratum-postgres-1",
    "stratum-neo4j-1",
    "stratum-qdrant-1",
    "stratum-reasoning-engine-1",
]

POLL_INTERVAL_SECONDS = 5
HEALTH_CHECK_INTERVAL_SECONDS = 3


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------


def wait_for_health(base_url: str, timeout: int = 60) -> None:
    """Poll GET /health until 200 or timeout.

    Raises SystemExit if the reasoning engine is not reachable within timeout.
    """
    health_url = f"{base_url}/health"
    deadline = time.monotonic() + timeout
    first_attempt = True

    while time.monotonic() < deadline:
        try:
            response = httpx.get(health_url, timeout=5)
            if response.status_code == 200:
                print(f"reasoning-engine healthy at {base_url}")
                return
        except httpx.ConnectError:
            if first_attempt:
                print(
                    f"Cannot connect to reasoning-engine at {base_url}. "
                    "Is the Docker stack running?"
                )
                first_attempt = False
        except httpx.RequestError:
            pass

        print("Waiting for reasoning-engine health...")
        time.sleep(HEALTH_CHECK_INTERVAL_SECONDS)

    print(
        f"ERROR: reasoning-engine did not become healthy within {timeout}s at {base_url}"
    )
    sys.exit(1)


# ---------------------------------------------------------------------------
# Job submission and polling
# ---------------------------------------------------------------------------


def submit_and_poll(
    client: httpx.Client,
    base_url: str,
    ticker: str,
    timeout: int,
) -> tuple[str, int | None, str, float]:
    """Submit a report generation job and poll until completion.

    Returns:
        (ticker, job_id, status, elapsed_seconds) tuple

    Status values: "completed", "failed", "timeout", "error"

    Raises:
        Nothing — all errors are captured as status strings.
    """
    start = time.monotonic()

    # Submit job
    try:
        response = client.post(
            f"{base_url}/reports/generate",
            json={"ticker": ticker, "asset_type": "equity"},
            timeout=30,
        )
    except httpx.RequestError as exc:
        elapsed = time.monotonic() - start
        print(f"  [{ticker}] Connection error during submit: {exc}")
        return (ticker, None, "error", round(elapsed, 1))

    if response.status_code == 409:
        # Duplicate job — should not happen with sequential processing but handle gracefully
        detail = response.json().get("detail", "")
        print(f"  [{ticker}] 409 Conflict (duplicate job): {detail} — skipping")
        elapsed = time.monotonic() - start
        return (ticker, None, "skipped", round(elapsed, 1))

    if response.status_code != 202:
        elapsed = time.monotonic() - start
        print(f"  [{ticker}] Unexpected HTTP {response.status_code} on submit — skipping")
        return (ticker, None, "error", round(elapsed, 1))

    data = response.json()
    job_id: int = data["job_id"]
    print(f"  [{ticker}] Submitted — job_id={job_id}")

    # Poll until settled
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        time.sleep(POLL_INTERVAL_SECONDS)

        try:
            poll_response = client.get(f"{base_url}/reports/{job_id}", timeout=30)
        except httpx.RequestError as exc:
            print(f"  [{ticker}] Poll error: {exc}")
            continue

        if poll_response.status_code == 202:
            poll_data = poll_response.json()
            status = poll_data.get("status", "unknown")
            elapsed = round(time.monotonic() - start, 1)
            print(f"  [{ticker}] Still {status} (job_id={job_id}, {elapsed}s elapsed)")
            continue

        if poll_response.status_code == 200:
            poll_data = poll_response.json()
            final_status = poll_data.get("status", "unknown")
            elapsed = round(time.monotonic() - start, 1)
            print(f"  [{ticker}] {final_status.upper()} — job_id={job_id}, elapsed={elapsed}s")
            return (ticker, job_id, final_status, elapsed)

        # Unexpected status
        elapsed = round(time.monotonic() - start, 1)
        print(f"  [{ticker}] Unexpected poll HTTP {poll_response.status_code}")
        return (ticker, job_id, "error", elapsed)

    # Timeout
    elapsed = round(time.monotonic() - start, 1)
    print(f"  [{ticker}] TIMEOUT after {elapsed}s (job_id={job_id})")
    return (ticker, job_id, "timeout", elapsed)


# ---------------------------------------------------------------------------
# Docker monitoring
# ---------------------------------------------------------------------------


def capture_docker_stats() -> str:
    """Run docker stats --no-stream and return output string.

    Prints the table to console and returns the raw stdout string.
    """
    result = subprocess.run(
        [
            "docker", "stats", "--no-stream",
            "--format", "table {{.Name}}\t{{.MemUsage}}\t{{.MemPerc}}",
        ],
        capture_output=True,
        text=True,
    )
    output = result.stdout.strip()
    if output:
        print(output)
    else:
        print("(docker stats returned no output)")
    return output


def check_oom_status(services: list[str]) -> dict[str, bool]:
    """Check OOMKilled status for each named Docker service.

    Returns:
        dict mapping service_name -> bool (True means OOM killed)

    Prints per-service OOM status to console.
    """
    oom_status: dict[str, bool] = {}

    print("\nOOM Kill Status:")
    for service in services:
        result = subprocess.run(
            ["docker", "inspect", service, "--format", "{{.State.OOMKilled}}"],
            capture_output=True,
            text=True,
        )
        raw = result.stdout.strip().lower()
        if result.returncode != 0:
            # Container not found or docker error
            print(f"  {service}: UNKNOWN (inspect failed: {result.stderr.strip()})")
            oom_status[service] = False
        elif raw == "true":
            oom_status[service] = True
            print(f"  {service}: OOM KILLED")
        else:
            oom_status[service] = False
            print(f"  {service}: OK")

    return oom_status


# ---------------------------------------------------------------------------
# Batch orchestrator
# ---------------------------------------------------------------------------


def run_batch(base_url: str, timeout_per_job: int) -> int:
    """Run sequential batch validation for all 20 VN30 tickers.

    Returns:
        0 — PASS (no OOM kills detected)
        1 — FAIL (one or more OOM kills detected)
    """
    wait_for_health(base_url, timeout=60)

    print()
    print("Starting batch validation: 20 VN30 tickers (sequential)")
    print(f"Base URL: {base_url}")
    print(f"Timeout per job: {timeout_per_job}s")
    print()

    # Initial memory snapshot
    print("--- Initial Docker Stats Snapshot ---")
    capture_docker_stats()
    print()

    results: list[tuple[str, int | None, str, float]] = []

    with httpx.Client() as client:
        for i, ticker in enumerate(VN30_TICKERS, start=1):
            print(f"\n[{i}/{len(VN30_TICKERS)}] Processing {ticker}...")
            result = submit_and_poll(client, base_url, ticker, timeout_per_job)
            results.append(result)

            # Capture intermediate docker stats every 5 tickers
            if i % 5 == 0:
                print(f"\n--- Intermediate Docker Stats (after {i} tickers) ---")
                capture_docker_stats()
                print()

    # Final memory snapshot
    print("\n--- Final Docker Stats Snapshot ---")
    capture_docker_stats()
    print()

    # OOM kill check
    oom_map = check_oom_status(SERVICES)
    oom_killed_count = sum(1 for v in oom_map.values() if v)

    # Summary table
    print()
    print("=" * 60)
    print("Batch Validation Summary")
    print("=" * 60)
    print(f"{'Ticker':<8} | {'Job ID':<6} | {'Status':<10} | {'Elapsed (s)':<12}")
    print(f"{'-' * 8}-+-{'-' * 6}-+-{'-' * 10}-+-{'-' * 12}")
    for ticker, job_id, status, elapsed in results:
        job_id_str = str(job_id) if job_id is not None else "N/A"
        print(f"{ticker:<8} | {job_id_str:<6} | {status:<10} | {elapsed:<12}")

    print("=" * 60)

    completed = sum(1 for _, _, s, _ in results if s == "completed")
    failed = sum(1 for _, _, s, _ in results if s in ("failed", "timeout", "error", "skipped"))

    print(f"Completed: {completed}  Failed: {failed}  OOM Kills: {oom_killed_count}")

    if oom_killed_count == 0:
        print("Result: PASS (no OOM kills detected)")
        print("=" * 60)
        return 0
    else:
        killed_services = [name for name, killed in oom_map.items() if killed]
        print(f"Result: FAIL (OOM kills detected in: {', '.join(killed_services)})")
        print("=" * 60)
        return 1


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Batch validation script for 20 VN30 stocks (SRVC-06).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/batch-validate.py --base-url http://localhost:8001
  python scripts/batch-validate.py --base-url http://localhost:8001 --timeout 900
        """,
    )
    parser.add_argument(
        "--base-url",
        default="http://localhost:8001",
        help="Base URL of the reasoning-engine API (default: http://localhost:8001)",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=600,
        help="Per-job timeout in seconds (default: 600)",
    )

    args = parser.parse_args()

    exit_code = run_batch(base_url=args.base_url, timeout_per_job=args.timeout)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
