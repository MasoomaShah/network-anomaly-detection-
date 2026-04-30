"""
main.py — Agentic AI Network Troubleshooter Entry Point
========================================================
Usage:
    python main.py                  # rule-based monitoring
    python main.py --mode lstm      # watch for LSTM alerts
    python main.py --mode demo --scenario dns_failure   # fire a demo

Dashboard (separate terminal):
    streamlit run dashboard/app.py
"""

import argparse
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)-12s  %(message)s",
    datefmt="%H:%M:%S",
)

from agent.trigger import run_rule_based, run_lstm_watcher, trigger_demo, DEMO_SCENARIOS


def main():
    parser = argparse.ArgumentParser(
        description="Agentic AI Network Troubleshooter",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument(
        "--mode",
        choices=["rules", "lstm", "demo"],
        default="rules",
        help=(
            "rules  — collect metrics + rule-based anomaly detection (default)\n"
            "lstm   — watch alerts.json for LSTM-generated alerts\n"
            "demo   — fire a single demo scenario and exit"
        ),
    )
    parser.add_argument(
        "--scenario",
        choices=list(DEMO_SCENARIOS.keys()),
        default="dns_failure",
        help="Demo scenario to trigger (only used with --mode demo)",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=10,
        help="Seconds between metric collections in rules mode (default: 10)",
    )
    args = parser.parse_args()

    print("=" * 60)
    print("   Agentic AI Network Troubleshooter")
    print(f"   Mode: {args.mode}")
    print("=" * 60)

    if args.mode == "rules":
        run_rule_based(interval=args.interval)
    elif args.mode == "lstm":
        run_lstm_watcher()
    elif args.mode == "demo":
        print(f"\n   Triggering demo: {args.scenario}\n")
        result = trigger_demo(args.scenario)
        print("\n" + "=" * 60)
        print("   AGENT RESULT")
        print("=" * 60)
        print(f"   Outcome: {result['outcome']}")
        print(f"   Steps:   {len(result['steps'])}")
        print(f"\n   {result['final_answer']}")


if __name__ == "__main__":
    main()
