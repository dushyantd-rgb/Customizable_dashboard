-- GrowthByte Reporting Platform
-- De-identified development data for Phase 4 prototype
-- This file is idempotent and safe to run multiple times
-- Run with: docker exec -i supabase_db_GrowthByte psql -U postgres -d postgres < seed-demo.sql

BEGIN;

-- Fixed demo client UUID for consistent testing
-- Demo client
INSERT INTO public.clients (id, name, slug, reporting_timezone, default_currency, status, created_at, updated_at)
VALUES (
    '11111111-1111-1111-1111-111111111111',
    'Demo Client (Development)',
    'demo-client-dev',
    'America/New_York',
    'USD',
    'active',
    NOW() - INTERVAL '30 days',
    NOW()
) ON CONFLICT (id) DO UPDATE SET
    name = EXCLUDED.name,
    slug = EXCLUDED.slug,
    reporting_timezone = EXCLUDED.reporting_timezone,
    default_currency = EXCLUDED.default_currency,
    status = EXCLUDED.status,
    updated_at = NOW();

-- Client knowledge
INSERT INTO public.client_knowledge (id, client_id, category, knowledge_key, value, status, source_type, version, created_at, updated_at)
VALUES
    ('11111111-1111-1111-1111-111111111101', '11111111-1111-1111-1111-111111111111', 'targeting', 'target_audience', '"Small business owners in retail"', 'approved', 'manual', 1, NOW(), NOW()),
    ('11111111-1111-1111-1111-111111111102', '11111111-1111-1111-1111-111111111111', 'brand', 'brand_voice', '"Professional yet approachable"', 'approved', 'manual', 1, NOW(), NOW()),
    ('11111111-1111-1111-1111-111111111103', '11111111-1111-1111-1111-111111111111', 'positioning', 'unique_selling_proposition', '"Affordable point-of-sale solutions"', 'approved', 'manual', 1, NOW(), NOW())
ON CONFLICT (id) DO UPDATE SET
    category = EXCLUDED.category,
    knowledge_key = EXCLUDED.knowledge_key,
    value = EXCLUDED.value,
    status = EXCLUDED.status,
    source_type = EXCLUDED.source_type,
    updated_at = NOW();

-- Client KPIs
INSERT INTO public.client_kpis (id, client_id, metric_key, label, target_value, unit, direction, attribution_level, active_from, created_at, updated_at)
VALUES
    ('11111111-1111-1111-1111-111111111111', '11111111-1111-1111-1111-111111111111', 'cost_per_lead', 'Target Cost Per Lead', 50.00, 'currency', 'decrease', 'client', '2024-01-01', NOW(), NOW()),
    ('11111111-1111-1111-1111-111111111112', '11111111-1111-1111-1111-111111111111', 'leads_generated', 'Leads Generated', 100, 'count', 'increase', 'client', '2024-01-01', NOW(), NOW()),
    ('11111111-1111-1111-1111-111111111113', '11111111-1111-1111-1111-111111111111', 'conversion_rate', 'Conversion Rate', 15, 'percent', 'increase', 'client', '2024-01-01', NOW(), NOW())
ON CONFLICT (id) DO UPDATE SET
    metric_key = EXCLUDED.metric_key,
    label = EXCLUDED.label,
    target_value = EXCLUDED.target_value,
    unit = EXCLUDED.unit,
    direction = EXCLUDED.direction,
    attribution_level = EXCLUDED.attribution_level,
    active_from = EXCLUDED.active_from,
    updated_at = NOW();

-- Integration connections
INSERT INTO public.integration_connections (id, client_id, provider, source_identifier, display_name, status, created_at, updated_at)
VALUES
    ('11111111-1111-1111-1111-111111111122', '11111111-1111-1111-1111-111111111111', 'meta', 'act_123456789', 'Demo Meta Account', 'connected', NOW() - INTERVAL '30 days', NOW()),
    ('11111111-1111-1111-1111-111111111123', '11111111-1111-1111-1111-111111111111', 'google_sheets', NULL, 'Demo Google Sheets', 'connected', NOW() - INTERVAL '30 days', NOW())
ON CONFLICT (client_id, id) DO UPDATE SET
    provider = EXCLUDED.provider,
    source_identifier = EXCLUDED.source_identifier,
    display_name = EXCLUDED.display_name,
    status = EXCLUDED.status,
    updated_at = NOW();

-- Meta account
INSERT INTO public.meta_accounts (
    id, client_id, integration_connection_id, external_account_id, name, currency, account_timezone, status, last_seen_at
) VALUES (
    '11111111-1111-1111-1111-111111111133',
    '11111111-1111-1111-1111-111111111111',
    '11111111-1111-1111-1111-111111111122',
    'act_123456789',
    'Demo Ad Account',
    'USD',
    'America/New_York',
    'active',
    NOW()
) ON CONFLICT (client_id, id) DO UPDATE SET
    integration_connection_id = EXCLUDED.integration_connection_id,
    external_account_id = EXCLUDED.external_account_id,
    name = EXCLUDED.name,
    currency = EXCLUDED.currency,
    account_timezone = EXCLUDED.account_timezone,
    status = EXCLUDED.status,
    last_seen_at = EXCLUDED.last_seen_at;

-- Meta campaign
INSERT INTO public.meta_campaigns (
    id, client_id, meta_account_id, external_campaign_id, name, objective, status, effective_status
) VALUES (
    '22222222-2222-2222-2222-222222222201',
    '11111111-1111-1111-1111-111111111111',
    '11111111-1111-1111-1111-111111111133',
    '234567890123',
    'Demo Campaign - January 2024',
    'LEAD_GENERATION',
    'active',
    'active'
) ON CONFLICT (client_id, id) DO UPDATE SET
    meta_account_id = EXCLUDED.meta_account_id,
    external_campaign_id = EXCLUDED.external_campaign_id,
    name = EXCLUDED.name,
    objective = EXCLUDED.objective,
    status = EXCLUDED.status,
    effective_status = EXCLUDED.effective_status;

-- Meta ad set
INSERT INTO public.meta_ad_sets (
    id, client_id, meta_account_id, campaign_id, external_ad_set_id, name, status, effective_status
) VALUES (
    '22222222-2222-2222-2222-222222222202',
    '11111111-1111-1111-1111-111111111111',
    '11111111-1111-1111-1111-111111111133',
    '22222222-2222-2222-2222-222222222201',
    '345678901234',
    'Demo Ad Set - East Coast',
    'active',
    'active'
) ON CONFLICT (client_id, id) DO UPDATE SET
    meta_account_id = EXCLUDED.meta_account_id,
    campaign_id = EXCLUDED.campaign_id,
    external_ad_set_id = EXCLUDED.external_ad_set_id,
    name = EXCLUDED.name,
    status = EXCLUDED.status,
    effective_status = EXCLUDED.effective_status;

-- Meta ad
INSERT INTO public.meta_ads (
    id, client_id, meta_account_id, campaign_id, ad_set_id, external_ad_id, name, status, effective_status
) VALUES (
    '22222222-2222-2222-2222-222222222203',
    '11111111-1111-1111-1111-111111111111',
    '11111111-1111-1111-1111-111111111133',
    '22222222-2222-2222-2222-222222222201',
    '22222222-2222-2222-2222-222222222202',
    '456789012345',
    'Demo Ad - Free Trial',
    'active',
    'active'
) ON CONFLICT (client_id, id) DO UPDATE SET
    meta_account_id = EXCLUDED.meta_account_id,
    campaign_id = EXCLUDED.campaign_id,
    ad_set_id = EXCLUDED.ad_set_id,
    external_ad_id = EXCLUDED.external_ad_id,
    name = EXCLUDED.name,
    status = EXCLUDED.status,
    effective_status = EXCLUDED.effective_status;

-- Current period Meta insights (January 15, 2024)
INSERT INTO public.meta_daily_insights (
    id, client_id, meta_account_id, report_date, entity_level, entity_id, external_entity_id,
    spend, currency, impressions, reach, clicks, meta_leads, meta_conversions
) VALUES
    -- Campaign level
    ('33333333-3333-3333-3333-333333333301',
     '11111111-1111-1111-1111-111111111111',
     '11111111-1111-1111-1111-111111111133',
     '2024-01-15', 'campaign',
     '22222222-2222-2222-2222-222222222201',
     '234567890123',
     1000.00, 'USD', 15000, 12000, 450, 50, 5),
    -- Ad set level
    ('33333333-3333-3333-3333-333333333302',
     '11111111-1111-1111-1111-111111111111',
     '11111111-1111-1111-1111-111111111133',
     '2024-01-15', 'ad_set',
     '22222222-2222-2222-2222-222222222202',
     '345678901234',
     1000.00, 'USD', 15000, 12000, 450, 50, 5),
    -- Ad level
    ('33333333-3333-3333-3333-333333333303',
     '11111111-1111-1111-1111-111111111111',
     '11111111-1111-1111-1111-111111111133',
     '2024-01-15', 'ad',
     '22222222-2222-2222-2222-222222222203',
     '456789012345',
     1000.00, 'USD', 15000, 12000, 450, 50, 5)
ON CONFLICT (client_id, id) DO UPDATE SET
    report_date = EXCLUDED.report_date,
    entity_level = EXCLUDED.entity_level,
    entity_id = EXCLUDED.entity_id,
    external_entity_id = EXCLUDED.external_entity_id,
    spend = EXCLUDED.spend,
    impressions = EXCLUDED.impressions,
    reach = EXCLUDED.reach,
    clicks = EXCLUDED.clicks,
    meta_leads = EXCLUDED.meta_leads,
    meta_conversions = EXCLUDED.meta_conversions;

-- Previous period Meta insights (December 15, 2023)
INSERT INTO public.meta_daily_insights (
    id, client_id, meta_account_id, report_date, entity_level, entity_id, external_entity_id,
    spend, currency, impressions, reach, clicks, meta_leads, meta_conversions
) VALUES (
    '44444444-4444-4444-4444-444444444401',
    '11111111-1111-1111-1111-111111111111',
    '11111111-1111-1111-1111-111111111133',
    '2023-12-15', 'campaign',
    '22222222-2222-2222-2222-222222222201',
    '234567890123',
    800.00, 'USD', 12000, 10000, 360, 40, 4
) ON CONFLICT (client_id, id) DO UPDATE SET
    report_date = EXCLUDED.report_date,
    entity_level = EXCLUDED.entity_level,
    entity_id = EXCLUDED.entity_id,
    external_entity_id = EXCLUDED.external_entity_id,
    spend = EXCLUDED.spend,
    impressions = EXCLUDED.impressions,
    reach = EXCLUDED.reach,
    clicks = EXCLUDED.clicks,
    meta_leads = EXCLUDED.meta_leads,
    meta_conversions = EXCLUDED.meta_conversions;

-- Google Sheet config
INSERT INTO public.google_sheet_configs (
    client_id, id, spreadsheet_id, worksheet_name, header_row, data_start_row, source_timezone, status
) VALUES (
    '11111111-1111-1111-1111-111111111111',
    '55555555-5555-5555-5555-555555555501',
    'sheet_1234567890abcdef',
    'Sheet1',
    1,
    2,
    'America/New_York',
    'active'
) ON CONFLICT (client_id, id) DO UPDATE SET
    spreadsheet_id = EXCLUDED.spreadsheet_id,
    worksheet_name = EXCLUDED.worksheet_name,
    header_row = EXCLUDED.header_row,
    data_start_row = EXCLUDED.data_start_row,
    source_timezone = EXCLUDED.source_timezone,
    status = EXCLUDED.status;

-- Sync run
INSERT INTO public.sync_runs (
    client_id, id, google_sheet_config_id, source_type, status, started_at, finished_at, rows_read, rows_written
) VALUES (
    '11111111-1111-1111-1111-111111111111',
    '66666666-6666-6666-6666-666666666601',
    '55555555-5555-5555-5555-555555555501',
    'google_sheets',
    'completed',
    '2024-01-15 10:00:00+00',
    '2024-01-15 10:05:00+00',
    10,
    10
) ON CONFLICT (client_id, id) DO UPDATE SET
    google_sheet_config_id = EXCLUDED.google_sheet_config_id,
    source_type = EXCLUDED.source_type,
    status = EXCLUDED.status,
    started_at = EXCLUDED.started_at,
    finished_at = EXCLUDED.finished_at,
    rows_read = EXCLUDED.rows_read,
    rows_written = EXCLUDED.rows_written;

-- Raw sheet rows (for lead records)
INSERT INTO public.raw_sheet_rows (
    client_id, id, google_sheet_config_id, sync_run_id, worksheet_name, row_number, source_row_key,
    raw_values, row_hash, observed_at
) VALUES
    -- Qualified lead
    ('11111111-1111-1111-1111-111111111111',
     '77777777-7777-7777-7777-777777777701',
     '55555555-5555-5555-5555-555555555501',
     '66666666-6666-6666-6666-666666666601',
     'Sheet1', 2, 'row_2',
     '{"Email": "user1@example.com", "Name": "John Doe", "Phone": "+1234567890", "Campaign": "Demo Campaign", "Status": "qualified", "Created": "2024-01-15"}',
     'hash_0001', '2024-01-15 10:00:00+00'),
    -- Disqualified lead
    ('11111111-1111-1111-1111-111111111111',
     '77777777-7777-7777-7777-777777777702',
     '55555555-5555-5555-5555-555555555501',
     '66666666-6666-6666-6666-666666666601',
     'Sheet1', 3, 'row_3',
     '{"Email": "user2@example.com", "Name": "Jane Smith", "Phone": "+0987654321", "Campaign": "Demo Campaign", "Status": "disqualified", "Created": "2024-01-15"}',
     'hash_0002', '2024-01-15 10:00:00+00'),
    -- Ambiguous lead (multiple candidates)
    ('11111111-1111-1111-1111-111111111111',
     '77777777-7777-7777-7777-777777777703',
     '55555555-5555-5555-5555-555555555501',
     '66666666-6666-6666-6666-666666666601',
     'Sheet1', 4, 'row_4',
     '{"Email": "user3@example.com", "Name": "Bob Johnson", "Phone": "+1122334455", "Campaign": "Campaign", "Status": "new", "Created": "2024-01-15"}',
     'hash_0003', '2024-01-15 10:00:00+00'),
    -- Unmatched lead (no candidate)
    ('11111111-1111-1111-1111-111111111111',
     '77777777-7777-7777-7777-777777777704',
     '55555555-5555-5555-5555-555555555501',
     '66666666-6666-6666-6666-666666666601',
     'Sheet1', 5, 'row_5',
     '{"Email": "user4@example.com", "Name": "Alice Brown", "Phone": "+5544332211", "Campaign": "Unknown Campaign", "Status": "new", "Created": "2024-01-15"}',
     'hash_0004', '2024-01-15 10:00:00+00')
ON CONFLICT (client_id, id) DO UPDATE SET
    raw_values = EXCLUDED.raw_values,
    row_hash = EXCLUDED.row_hash,
    observed_at = EXCLUDED.observed_at;

-- Lead records
INSERT INTO public.lead_records (
    client_id, id, raw_sheet_row_id, source_lead_id, lead_at, source_status_raw, canonical_status, is_reviewed, mapping_version
) VALUES
    -- Qualified lead
    ('11111111-1111-1111-1111-111111111111',
     '88888888-8888-8888-8888-888888888801',
     '77777777-7777-7777-7777-777777777701',
     'lead_001',
     '2024-01-15 12:00:00+00',
     'qualified',
     'qualified',
     true,
     1),
    -- Disqualified lead
    ('11111111-1111-1111-1111-111111111111',
     '88888888-8888-8888-8888-888888888802',
     '77777777-7777-7777-7777-777777777702',
     'lead_002',
     '2024-01-15 12:00:00+00',
     'disqualified',
     'disqualified',
     true,
     1),
    -- Ambiguous lead (needs matching)
    ('11111111-1111-1111-1111-111111111111',
     '88888888-8888-8888-8888-888888888803',
     '77777777-7777-7777-7777-777777777703',
     'lead_003',
     '2024-01-15 12:00:00+00',
     'new',
     'pending',
     false,
     1),
    -- Unmatched lead (no match found)
    ('11111111-1111-1111-1111-111111111111',
     '88888888-8888-8888-8888-888888888804',
     '77777777-7777-7777-7777-777777777704',
     'lead_004',
     '2024-01-15 12:00:00+00',
     'new',
     'pending',
     false,
     1)
ON CONFLICT (client_id, id) DO UPDATE SET
    source_lead_id = EXCLUDED.source_lead_id,
    lead_at = EXCLUDED.lead_at,
    source_status_raw = EXCLUDED.source_status_raw,
    canonical_status = EXCLUDED.canonical_status,
    is_reviewed = EXCLUDED.is_reviewed,
    mapping_version = EXCLUDED.mapping_version;

-- Lead matches for qualified lead (matched to campaign)
INSERT INTO public.lead_matches (
    client_id, id, lead_record_id, integration_connection_id,
    external_campaign_id, campaign_display_name,
    method, confidence, rule_version, review_status, is_active
) VALUES (
    '11111111-1111-1111-1111-111111111111',
    '99999999-9999-9999-9999-999999999901',
    '88888888-8888-8888-8888-888888888801',
    '11111111-1111-1111-1111-111111111122',
    '234567890123',
    'Demo Campaign - January 2024',
    'automatic',
    0.95,
    'v1',
    'approved',
    true
) ON CONFLICT (client_id, id) DO UPDATE SET
    external_campaign_id = EXCLUDED.external_campaign_id,
    campaign_display_name = EXCLUDED.campaign_display_name,
    method = EXCLUDED.method,
    confidence = EXCLUDED.confidence,
    rule_version = EXCLUDED.rule_version,
    review_status = EXCLUDED.review_status,
    is_active = EXCLUDED.is_active;

COMMIT;

-- Print confirmation
DO $$
BEGIN
    RAISE NOTICE 'Demo data seeded successfully!';
    RAISE NOTICE 'Demo client ID: 11111111-1111-1111-1111-111111111111';
    RAISE NOTICE 'Client name: Demo Client (Development)';
    RAISE NOTICE 'Data includes: client, knowledge, KPIs, integration connections, Meta campaign/ad set/ad, insights, Sheet rows, and lead records';
END $$;
