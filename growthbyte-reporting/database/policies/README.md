# Policy workflow

No executable policies are included in Phase 1 because there are no business tables and RLS-based user authorization is deferred. Future client-owned tables must include `client_id`; the trusted backend remains responsible for rejecting mixed-client operations.
