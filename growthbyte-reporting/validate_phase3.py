#!/usr/bin/env python3
"""Quick validation script for Phase 3 prototype."""

import sys
from pathlib import Path

# Add apps/api to path
sys.path.insert(0, str(Path(__file__).parent / "apps" / "api"))

def test_imports():
    """Test all critical imports."""
    print("Testing imports...")

    try:
        from app.integrations.meta import models, client, repository, service, router
        print("[OK] Meta integration imports")
    except Exception as e:
        print(f"[FAIL] Meta import failed: {e}")
        return False

    try:
        from app.integrations.google import models, oauth, client, repository, service, router
        print("[OK] Google integration imports")
    except Exception as e:
        print(f"[FAIL] Google import failed: {e}")
        return False

    try:
        from app.core import encryption
        print("[OK] Encryption service imports")
    except Exception as e:
        print(f"[FAIL] Encryption import failed: {e}")
        return False

    try:
        from app.integrations.google.dependencies import (
            GoogleRepositoryDependency,
            GoogleServiceDependency,
        )
        print("[OK] Google dependencies")
    except Exception as e:
        print(f"[FAIL] Google dependencies failed: {e}")
        return False

    try:
        from app.integrations.meta.dependencies import (
            MetaClientDependency,
            MetaRepositoryDependency,
            MetaSyncServiceDependency,
        )
        print("[OK] Meta dependencies")
    except Exception as e:
        print(f"[FAIL] Meta dependencies failed: {e}")
        return False

    return True


def test_app_creation():
    """Test FastAPI app creation."""
    print("\nTesting app creation...")

    try:
        from app.main import create_app
        from app.core.config import Settings

        settings = Settings()
        app = create_app(application_settings=settings)

        routes = [r.path for r in app.routes if hasattr(r, 'path')]
        meta_routes = [r for r in routes if '/meta' in r]
        google_routes = [r for r in routes if '/google' in r]

        print(f"[OK] App created with {len(routes)} total routes")
        print(f"  - {len(meta_routes)} Meta routes")
        print(f"  - {len(google_routes)} Google routes")

        if len(meta_routes) < 5:
            print(f"[FAIL] Expected at least 5 Meta routes, got {len(meta_routes)}")
            return False

        if len(google_routes) < 10:
            print(f"[FAIL] Expected at least 10 Google routes, got {len(google_routes)}")
            return False

        return True
    except Exception as e:
        print(f"[FAIL] App creation failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_encryption():
    """Test encryption service."""
    print("\nTesting encryption...")

    try:
        from app.core.encryption import encrypt_token, decrypt_token
        from pydantic import SecretStr

        test_token = "test_google_token_12345"
        # Generate a proper 32-byte key for testing
        import base64
        test_key_bytes = base64.b64encode(b"a" * 32).decode()
        test_key = SecretStr(test_key_bytes)

        encrypted = encrypt_token(test_token, test_key)
        print(f"[OK] Token encrypted (length: {len(encrypted)})")

        decrypted = decrypt_token(encrypted, test_key)
        print(f"[OK] Token decrypted")

        if decrypted != test_token:
            print(f"[FAIL] Decryption mismatch: expected '{test_token}', got '{decrypted}'")
            return False

        print("[OK] Encryption roundtrip successful")
        return True
    except Exception as e:
        print(f"[FAIL] Encryption test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_models():
    """Test Pydantic models."""
    print("\nTesting models...")

    try:
        from app.integrations.meta.models import (
            MetaAdAccountSummary,
            MetaSyncRequest,
        )
        from app.integrations.google.models import (
            SpreadsheetSummary,
            GoogleSheetConfig,
        )
        from datetime import date

        # Test Meta models
        account = MetaAdAccountSummary(
            external_account_id="123456789",
            name="Test Account",
            currency="USD",
        )
        print(f"[OK] Meta account model: {account.external_account_id}")

        sync_req = MetaSyncRequest(
            date_from=date(2026, 1, 1),
            date_to=date(2026, 1, 31),
        )
        print(f"[OK] Meta sync request: {sync_req.date_from} to {sync_req.date_to}")

        # Test Google models
        spreadsheet = SpreadsheetSummary(
            id="abc123",
            name="Test Spreadsheet",
        )
        print(f"[OK] Spreadsheet model: {spreadsheet.name}")

        config = GoogleSheetConfig(
            spreadsheet_id="abc123",
            worksheet_name="Sheet1",
            header_row=1,
            data_start_row=2,
            source_timezone="UTC",
        )
        print(f"[OK] Sheet config: {config.worksheet_name}")

        return True
    except Exception as e:
        print(f"[FAIL] Model test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all validation tests."""
    print("=" * 60)
    print("Phase 3 Prototype Validation")
    print("=" * 60)

    results = []

    results.append(("Imports", test_imports()))
    results.append(("App Creation", test_app_creation()))
    results.append(("Encryption", test_encryption()))
    results.append(("Models", test_models()))

    print("\n" + "=" * 60)
    print("Validation Summary")
    print("=" * 60)

    for name, passed in results:
        status = "PASS" if passed else "FAIL"
        print(f"{name:.<40} {status}")

    all_passed = all(result[1] for result in results)

    print("=" * 60)
    if all_passed:
        print("[SUCCESS] ALL VALIDATIONS PASSED")
        print("=" * 60)
        return 0
    else:
        print("[ERROR] SOME VALIDATIONS FAILED")
        print("=" * 60)
        return 1


if __name__ == "__main__":
    sys.exit(main())
