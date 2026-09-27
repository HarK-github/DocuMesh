"""Concurrent load test script for read endpoints."""

import argparse
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
import httpx
import numpy as np


def run_load_test(base_url: str, requests_count: int, concurrency: int) -> dict:
    """Execute concurrent requests against read endpoints and collect timing metrics."""
    endpoints = ["/health", "/taxonomy"]
    latencies = []
    errors = 0

    print(f"Starting load test on {base_url} with {requests_count} requests (concurrency: {concurrency})...")
    start_time = time.perf_counter()

    def make_request(idx: int):
        endpoint = endpoints[idx % len(endpoints)]
        url = f"{base_url.rstrip('/')}{endpoint}"
        t0 = time.perf_counter()
        try:
            with httpx.Client(timeout=10.0) as client:
                res = client.get(url)
                duration = time.perf_counter() - t0
                if res.status_code == 200:
                    return duration, None
                return duration, f"Status {res.status_code}"
        except Exception as exc:
            return time.perf_counter() - t0, str(exc)

    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        futures = [executor.submit(make_request, i) for i in range(requests_count)]
        for f in as_completed(futures):
            dur, err = f.result()
            latencies.append(dur * 1000.0)  # ms
            if err:
                errors += 1

    total_time = time.perf_counter() - start_time
    rps = requests_count / total_time if total_time > 0 else 0

    results = {
        "total_requests": requests_count,
        "concurrency": concurrency,
        "total_time_seconds": round(total_time, 2),
        "requests_per_second": round(rps, 1),
        "errors": errors,
        "p50_ms": round(float(np.percentile(latencies, 50)), 2),
        "p95_ms": round(float(np.percentile(latencies, 95)), 2),
        "p99_ms": round(float(np.percentile(latencies, 99)), 2),
        "min_ms": round(float(np.min(latencies)), 2),
        "max_ms": round(float(np.max(latencies)), 2),
    }

    print("\n--- Load Test Results ---")
    print(f"Total Requests:      {results['total_requests']}")
    print(f"Concurrency:         {results['concurrency']}")
    print(f"Time Taken:          {results['total_time_seconds']}s")
    print(f"Throughput:          {results['requests_per_second']} req/s")
    print(f"Failed Requests:     {results['errors']}")
    print(f"Latency P50:         {results['p50_ms']} ms")
    print(f"Latency P95:         {results['p95_ms']} ms")
    print(f"Latency P99:         {results['p99_ms']} ms")
    print("-------------------------\n")

    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run load tests against PDF Annotator API")
    parser.add_argument("--url", default="http://localhost:8000", help="API base URL")
    parser.add_argument("-n", "--requests", type=int, default=100, help="Number of requests")
    parser.add_argument("-c", "--concurrency", type=int, default=10, help="Concurrency level")
    args = parser.parse_args()

    run_load_test(args.url, args.requests, args.concurrency)
