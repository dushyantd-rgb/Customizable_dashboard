"""Presence-only local configuration diagnostic.

Never print credential values, including prefixes: partial service-role keys are still secrets.
"""

import os


def _state(name: str) -> str:
    return "configured" if os.getenv(name, "").strip() else "missing"


if __name__ == "__main__":
    print("=== Environment Configuration ===")
    print("REPORTING_SUPABASE_URL:", _state("REPORTING_SUPABASE_URL"))
    print(
        "REPORTING_SUPABASE_SERVICE_ROLE_KEY:",
        _state("REPORTING_SUPABASE_SERVICE_ROLE_KEY"),
    )
