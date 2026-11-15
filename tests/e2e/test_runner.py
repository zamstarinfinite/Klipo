#!/usr/bin/env python3
"""
Klipo E2E Standalone Test Runner CLI
Supports tier filtering, live/mock gateway switching, and formatted test execution summaries.
"""

import argparse
import os
import sys
import time
import pytest


def parse_args():
    parser = argparse.ArgumentParser(
        description="Klipo E2E Test Suite Runner",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--tier",
        type=str,
        default="all",
        help="Test tier to execute: '1', '2', '3', '4', '5', '1,2', or 'all'",
    )
    parser.add_argument(
        "--base-url",
        type=str,
        default=None,
        help="Base URL for live SUT (e.g. http://localhost:8000). If omitted, runs in-process ASGI.",
    )
    parser.add_argument(
        "--live-pey",
        action="store_true",
        help="Use live Pey API from apiPey.txt instead of local mock server.",
    )
    parser.add_argument(
        "-k",
        "--expression",
        type=str,
        default=None,
        help="Pytest substring expression filter for test names.",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable verbose pytest output.",
    )
    return parser.parse_args()


class SummaryCollector:
    """Pytest plugin to collect test execution counts and durations."""

    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.skipped = 0
        self.errors = 0
        self.start_time = 0.0
        self.duration = 0.0

    def pytest_sessionstart(self, session):
        self.start_time = time.time()

    def pytest_sessionfinish(self, session, exitstatus):
        self.duration = time.time() - self.start_time

    def pytest_runtest_logreport(self, report):
        if report.when == "call":
            if report.passed:
                self.passed += 1
            elif report.failed:
                self.failed += 1
            elif report.skipped:
                self.skipped += 1
        elif report.failed:  # Setup or teardown error
            self.errors += 1


def main():
    args = parse_args()

    # Configure environment
    if args.base_url:
        os.environ["BASE_URL"] = args.base_url

    if args.live_pey:
        api_pey_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "apiPey.txt")
        if os.path.isfile(api_pey_path):
            with open(api_pey_path, "r", encoding="utf-8") as f:
                os.environ["PEY_API_KEY"] = f.read().strip()
            os.environ["PEY_API_BASE_URL"] = "https://api.pey.mx"
            os.environ["PEY_BASE_URL"] = "https://api.pey.mx"
            print("Running tests against LIVE Pey API gateway (https://api.pey.mx)...")
        else:
            print(f"Error: {api_pey_path} not found for --live-pey.", file=sys.stderr)
            sys.exit(1)

    tier_map = {
        "1": "tests/e2e/tier1_feature_coverage",
        "2": "tests/e2e/tier2_boundaries_corners",
        "3": "tests/e2e/tier3_pairwise_combinations",
        "4": "tests/e2e/tier4_real_world_scenarios",
        "5": "tests/e2e/tier5_adversarial",
    }

    tier_input = args.tier.strip().lower()
    if tier_input == "all":
        selected_paths = list(tier_map.values())
        tier_label = "All Tiers (1, 2, 3, 4, 5)"
    else:
        selected_tiers = [t.strip() for t in tier_input.split(",") if t.strip()]
        if not selected_tiers:
            print("Error: No valid tiers specified. Valid options: 1, 2, 3, 4, 5, all", file=sys.stderr)
            sys.exit(1)
        selected_paths = []
        for t in selected_tiers:
            if t in tier_map:
                selected_paths.append(tier_map[t])
            else:
                print(f"Unknown tier: {t}. Valid options: 1, 2, 3, 4, 5, all", file=sys.stderr)
                sys.exit(1)
        tier_label = f"Tiers {','.join(selected_tiers)}"

    pytest_args = list(selected_paths)
    if args.verbose:
        pytest_args.append("-v")
    if args.expression:
        pytest_args.extend(["-k", args.expression])

    print("=" * 72)
    print(" KLIPO E2E TEST RUNNER")
    print("=" * 72)
    print(f" Target: {tier_label}")
    print(f" Paths:  {', '.join(selected_paths)}")
    print(f" Mode:   {'Live Server (' + os.environ['BASE_URL'] + ')' if args.base_url else 'In-Process ASGI'}")
    print(f" Pey:    {'Live API' if args.live_pey else 'Deterministic Mock Server'}")
    print("-" * 72)

    collector = SummaryCollector()
    exit_code = pytest.main(pytest_args, plugins=[collector])

    total_tests = collector.passed + collector.failed + collector.skipped + collector.errors
    success_rate = (collector.passed / total_tests * 100) if total_tests > 0 else 0.0

    print("\n" + "=" * 72)
    print(" EXECUTION SUMMARY")
    print("=" * 72)
    print(f" Total Tests Executed: {total_tests}")
    print(f" Passed:               {collector.passed}")
    print(f" Failed:               {collector.failed}")
    print(f" Skipped:              {collector.skipped}")
    print(f" Errors:               {collector.errors}")
    print(f" Pass Rate:            {success_rate:.1f}%")
    print(f" Total Duration:       {collector.duration:.2f}s")
    print("-" * 72)
    if exit_code == 0:
        print(" RESULT: ALL TESTS PASSED (EXIT CODE 0)")
    else:
        print(f" RESULT: FAILURES DETECTED (EXIT CODE {exit_code})")
    print("=" * 72)

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
