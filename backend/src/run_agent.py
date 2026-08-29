"""
Run the recovery agent against cases from sample_cases.json.

Usage:
    uv run src/run_agent.py                   # runs case #0 (default)
    uv run src/run_agent.py --index 4         # runs case at index 4
    uv run src/run_agent.py --all             # runs all cases with throttle
    uv run src/run_agent.py --type failed     # runs all failed_payment cases only

Throttle config (THROTTLE section below):
    Set THROTTLE_ENABLED = False to disable all delays.
    Set THROTTLE_BETWEEN_CASES to control seconds between calls.
"""

import json
import sys
import time
import uuid
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from agent.graph import build_agent
from core.models import RecoveryState

# ---------------------------------------------------------------------------
# THROTTLE CONFIG — change here to tune or disable
# ---------------------------------------------------------------------------
THROTTLE_ENABLED      = True   # set False to remove all delays
THROTTLE_BETWEEN_CASES = 5     # seconds between cases in --all / --type runs
# ---------------------------------------------------------------------------

DATA_FILE = Path(__file__).parent.parent / "data" / "sample_cases.json"

HARD_DECLINES = {"card expired", "card lost", "stolen", "do not honour", "invalid cvv"}


def throttle(label: str = ""):
    """Sleep between API calls if throttling is enabled."""
    if THROTTLE_ENABLED:
        msg = f"  [throttle] waiting {THROTTLE_BETWEEN_CASES}s"
        if label:
            msg += f" ({label})"
        print(msg)
        time.sleep(THROTTLE_BETWEEN_CASES)


def case_to_state(raw: dict) -> RecoveryState:
    failure = (raw.get("failure_reason") or "").lower()
    decline_type = "hard" if any(h in failure for h in HARD_DECLINES) else "soft"

    return RecoveryState(
        case_id=str(uuid.uuid4()),
        source_id=raw.get("order_id") or raw.get("subscription_id") or raw.get("invoice_id") or "unknown",
        case_type=raw["type"],
        decline_type=decline_type if raw["type"] == "failed_payment" else None,
        failure_reason=raw.get("failure_reason"),
        amount_inr=raw["amount_inr"],
        customer=raw["customer"],
        first_seen_at=datetime.fromisoformat(raw["created_at"]),
    )


from db import save_state, load_state

def run_case(raw: dict, index: int):
    # For testing, we use a deterministic UUID so it's consistent across runs
    case_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"case-{index}"))
    
    # Check if state exists, otherwise create it
    state = load_state(case_id)
    if not state:
        state = case_to_state(raw)
        state.case_id = case_id
        save_state(state)

    print("\n" + "=" * 60)
    print(f"  CASE #{index}  —  {state.case_type.upper()}")
    print("=" * 60)
    print(f"  Customer : {state.customer['name']} ({state.customer['email']})")
    print(f"  Amount   : ₹{state.amount_inr}")
    print(f"  Failure  : {state.failure_reason or 'N/A'}")
    print(f"  Decline  : {state.decline_type or 'N/A'}")
    print(f"  Attempts : {state.attempt_count}")
    print("-" * 60)
    print("  Agent thinking...\n")

    agent = build_agent(state)

    config = {"configurable": {"thread_id": state.case_id}}
    result = agent.invoke(
        {"messages": [], "recovery_state": state},
        config=config,
    )

    print("\n" + "-" * 60)
    print("  AGENT FINAL RESPONSE:")
    print("-" * 60)
    for msg in result.get("messages", []):
        if hasattr(msg, "content") and msg.content and not getattr(msg, "tool_calls", None):
            print(f"  {msg.content}")
            
    print("\n" + "-" * 60)
    print("  UPDATED DB STATE:")
    print("-" * 60)
    final_state = load_state(state.case_id)
    print(f"  Attempts: {final_state.attempt_count}")
    print(f"  Next Retry: {final_state.next_retry_at}")
    print("  Audit Log:")
    for entry in final_state.audit_log:
        print(f"    - [{entry.get('event_triggered')}] Amount: {entry.get('amount')}, Next Contact: {entry.get('next_contact')}")
    print("=" * 60)


def main():
    cases = json.loads(DATA_FILE.read_text())

    # --- run all ---
    if "--all" in sys.argv:
        for i, case in enumerate(cases):
            run_case(case, i)
            if i < len(cases) - 1:                          # no sleep after last one
                throttle(f"before case #{i + 1}")
        return

    # --- filter by type prefix ---
    if "--type" in sys.argv:
        idx = sys.argv.index("--type")
        prefix = sys.argv[idx + 1]
        filtered = [(i, c) for i, c in enumerate(cases) if c["type"].startswith(prefix)]
        print(f"\nRunning {len(filtered)} cases matching type '{prefix}'")
        for j, (i, case) in enumerate(filtered):
            run_case(case, i)
            if j < len(filtered) - 1:
                throttle(f"before next '{prefix}' case")
        return

    # --- single case by index (default: 0) ---
    index = 0
    if "--index" in sys.argv:
        idx = sys.argv.index("--index")
        index = int(sys.argv[idx + 1])

    run_case(cases[index], index)


if __name__ == "__main__":
    main()
