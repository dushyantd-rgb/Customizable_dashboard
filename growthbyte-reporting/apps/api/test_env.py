import os
print("=== Environment Variables ===")
print("REPORTING_SUPABASE_URL:", os.getenv("REPORTING_SUPABASE_URL"))
print("REPORTING_SUPABASE_SERVICE_ROLE_KEY:", os.getenv("REPORTING_SUPABASE_SERVICE_ROLE_KEY", "")[:20] + "...")
