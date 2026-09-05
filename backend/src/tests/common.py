"""
Shared test utilities and formatting helpers for Renvue tests.
"""

GREEN = "\033[92m"
RED = "\033[91m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"


def print_banner(title: str):
    print(f"\n{CYAN}{BOLD}{'='*70}{RESET}")
    print(f"{CYAN}{BOLD} TEST: {title}{RESET}")
    print(f"{CYAN}{BOLD}{'='*70}{RESET}")
