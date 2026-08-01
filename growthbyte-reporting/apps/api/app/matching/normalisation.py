"""Lead normalisation from raw Sheet rows to canonical lead records."""

import unicodedata
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from app.data.supabase import ReportingSupabaseClientProtocol
from app.matching.models import (
    CanonicalLeadStatus,
    NormalisationSummary,
)


class NormalisationError(Exception):
    """Base error for normalisation failures."""

    pass


class ClientNotFoundError(NormalisationError):
    """Client does not exist."""

    pass


class NoSheetConfigError(NormalisationError):
    """No active Sheet configuration for client."""

    pass


class NoSyncRunError(NormalisationError):
    """No sync run found for client."""

    pass


MATCHING_VERSION = "2026-08-01-v1"


class LeadNormaliser:
    """Normalises raw Sheet rows into canonical lead records."""

    def __init__(self, client: ReportingSupabaseClientProtocol) -> None:
        self._client = client

    async def normalise(
        self,
        *,
        client_id: UUID,
        sync_run_id: UUID | None = None,
    ) -> NormalisationSummary:
        """Normalise all unprocessed raw rows for a client."""
        # Get client details for timezone
        client_rows = await self._client.select(
            table="clients",
            columns=("id", "reporting_timezone", "default_currency"),
            filters={"id": str(client_id)},
            limit=1,
        )
        if not client_rows:
            raise ClientNotFoundError(f"Client {client_id} not found")

        client_row = client_rows[0]
        client_timezone = client_row.get("reporting_timezone", "UTC")

        # Get active Sheet config
        config_rows = await self._client.select(
            table="google_sheet_configs",
            columns=("id", "mapping_version"),
            filters={"client_id": str(client_id), "status": "active"},
            limit=1,
        )
        if not config_rows:
            raise NoSheetConfigError(f"No active Sheet config for client {client_id}")

        config = config_rows[0]
        config_id = UUID(config["id"])
        mapping_version = int(config["mapping_version"])

        # Get column and status mappings
        mappings = await self._get_mappings(
            client_id=client_id, config_id=config_id, version=mapping_version
        )
        column_mappings = mappings["column_mappings"]
        status_mappings = mappings["status_mappings"]

        # Get raw rows to process
        if sync_run_id:
            raw_rows = await self._client.select(
                table="raw_sheet_rows",
                columns=(
                    "id",
                    "client_id",
                    "google_sheet_config_id",
                    "sync_run_id",
                    "worksheet_name",
                    "row_number",
                    "raw_values",
                    "row_hash",
                    "observed_at",
                ),
                filters={
                    "client_id": str(client_id),
                    "google_sheet_config_id": str(config_id),
                    "sync_run_id": str(sync_run_id),
                },
                limit=1000,
            )
        else:
            # Get latest sync run
            sync_rows = await self._client.select(
                table="sync_runs",
                columns=("id",),
                filters={
                    "client_id": str(client_id),
                    "source_type": "google_sheets",
                    "status": "succeeded",
                },
                limit=1,
            )
            if not sync_rows:
                raise NoSyncRunError(f"No successful sync run for client {client_id}")
            latest_sync_id = sync_rows[0]["id"]
            raw_rows = await self._client.select(
                table="raw_sheet_rows",
                columns=(
                    "id",
                    "client_id",
                    "google_sheet_config_id",
                    "sync_run_id",
                    "worksheet_name",
                    "row_number",
                    "raw_values",
                    "row_hash",
                    "observed_at",
                ),
                filters={
                    "client_id": str(client_id),
                    "google_sheet_config_id": str(config_id),
                    "sync_run_id": str(latest_sync_id),
                },
                limit=1000,
            )

        # Get existing normalized rows to check for duplicates
        existing_rows = await self._client.select(
            table="lead_records",
            columns=("raw_sheet_row_id",),
            filters={"client_id": str(client_id), "mapping_version": str(mapping_version)},
            limit=5000,
        )
        existing_raw_ids = {UUID(r["raw_sheet_row_id"]) for r in existing_rows}

        rows_processed = 0
        rows_normalised = 0
        rows_rejected = 0
        total_warnings = 0
        finished_at = datetime.now(UTC)

        for raw_row in raw_rows:
            raw_row_id = UUID(raw_row["id"])
            if raw_row_id in existing_raw_ids:
                # Skip already processed
                continue

            rows_processed += 1
            raw_values = raw_row["raw_values"] if isinstance(raw_row["raw_values"], list) else []

            try:
                normalised = self._normalise_row(
                    raw_row_id=raw_row_id,
                    client_id=client_id,
                    raw_values=raw_values,
                    column_mappings=column_mappings,
                    status_mappings=status_mappings,
                    mapping_version=mapping_version,
                    client_timezone=client_timezone,
                )

                # Insert into lead_records
                await self._client.insert(
                    table="lead_records",
                    row={
                        "client_id": str(client_id),
                        "raw_sheet_row_id": str(raw_row_id),
                        "source_lead_id": normalised.get("source_lead_id"),
                        "meta_lead_id": normalised.get("meta_lead_id"),
                        "lead_at": normalised.get("lead_at").isoformat()
                        if normalised.get("lead_at")
                        else None,
                        "source_status_raw": normalised.get("source_status_raw"),
                        "canonical_status": normalised.get(
                            "canonical_status", CanonicalLeadStatus.NOT_REVIEWED.value
                        ),
                        "is_reviewed": normalised.get("is_reviewed", False),
                        "qualification_at": normalised.get("qualification_at").isoformat()
                        if normalised.get("qualification_at")
                        else None,
                        "conversion_at": normalised.get("conversion_at").isoformat()
                        if normalised.get("conversion_at")
                        else None,
                        "mapping_version": mapping_version,
                    },
                )
                rows_normalised += 1
                total_warnings += len(normalised.get("warnings", []))

            except Exception:
                rows_rejected += 1

        # Create audit event
        await self._client.insert(
            table="audit_events",
            row={
                "client_id": str(client_id),
                "sync_run_id": str(sync_run_id) if sync_run_id else None,
                "action": "normalise",
                "entity_type": "lead_records",
                "entity_id": None,
                "event_metadata": {
                    "rows_processed": rows_processed,
                    "rows_normalised": rows_normalised,
                    "rows_rejected": rows_rejected,
                    "warnings_count": total_warnings,
                    "mapping_version": mapping_version,
                },
                "occurred_at": finished_at.isoformat(),
            },
        )

        return NormalisationSummary(
            client_id=client_id,
            sync_run_id=sync_run_id or UUID("00000000-0000-0000-0000-000000000000"),
            rows_processed=rows_processed,
            rows_normalised=rows_normalised,
            rows_rejected=rows_rejected,
            warnings_count=total_warnings,
            finished_at=finished_at,
        )

    def _normalise_row(
        self,
        *,
        raw_row_id: UUID,
        client_id: UUID,
        raw_values: list[Any],
        column_mappings: dict[str, str],
        status_mappings: dict[str, tuple[str, bool]],
        mapping_version: int,
        client_timezone: str,
    ) -> dict[str, Any]:
        """Normalise a single raw row."""
        warnings: list[dict[str, Any]] = []
        result: dict[str, Any] = {
            "raw_row_id": raw_row_id,
            "client_id": client_id,
            "mapping_version": mapping_version,
            "warnings": warnings,
        }

        # Extract values using column mappings
        for canonical_field, source_header in column_mappings.items():
            # Find index of this header
            header_index = None
            for idx, header in enumerate(column_mappings.keys()):
                if header == source_header:
                    header_index = idx
                    break

            if header_index is None or header_index >= len(raw_values):
                continue

            raw_value = raw_values[header_index]
            if raw_value is None:
                continue

            # Normalise based on field type
            field_lower = canonical_field.lower()

            if field_lower == "lead_date":
                parsed_date = self._parse_date(raw_value, client_timezone)
                if parsed_date is None:
                    warnings.append(
                        {
                            "code": "invalid_date",
                            "message": "Could not parse lead date",
                            "raw_field": canonical_field,
                            "raw_value": str(raw_value)[:100],
                        }
                    )
                else:
                    result["lead_at"] = parsed_date

            elif field_lower == "source_lead_id":
                trimmed = str(raw_value).strip()
                if trimmed:
                    result["source_lead_id"] = trimmed
                else:
                    warnings.append(
                        {
                            "code": "missing_lead_identifier",
                            "message": "Source lead ID is empty",
                            "raw_field": canonical_field,
                        }
                    )

            elif field_lower in (
                "campaign_id",
                "campaign_name",
                "adset_id",
                "adset_name",
                "ad_id",
                "ad_name",
            ):
                trimmed = str(raw_value).strip()
                if trimmed:
                    result[field_lower] = trimmed

            elif field_lower.startswith("utm_"):
                normalized = str(raw_value).strip().lower()
                if normalized:
                    result[field_lower] = normalized

            elif field_lower == "lead_status":
                raw_status = str(raw_value).strip()
                result["source_status_raw"] = raw_status
                normalized_status, is_reviewed = self._map_status(
                    raw_status=raw_status,
                    status_mappings=status_mappings,
                )
                result["canonical_status"] = normalized_status
                result["is_reviewed"] = is_reviewed
                if normalized_status == CanonicalLeadStatus.NOT_REVIEWED.value and raw_status:
                    warnings.append(
                        {
                            "code": "unknown_status",
                            "message": f"Status '{raw_status}' not in mapping",
                            "raw_field": canonical_field,
                            "raw_value": raw_status[:100],
                        }
                    )

            elif field_lower == "is_qualified":
                parsed_bool = self._parse_boolean(raw_value)
                if parsed_bool is not None:
                    # If qualified, set status if not already set
                    if (
                        parsed_bool
                        and result.get("canonical_status") == CanonicalLeadStatus.NOT_REVIEWED.value
                    ):
                        result["canonical_status"] = CanonicalLeadStatus.QUALIFIED.value
                        result["is_reviewed"] = True
                else:
                    warnings.append(
                        {
                            "code": "invalid_boolean",
                            "message": "Could not parse is_qualified",
                            "raw_field": canonical_field,
                            "raw_value": str(raw_value)[:100],
                        }
                    )

        # Check for missing attribution fields
        has_attribution = any(
            result.get(k)
            for k in (
                "campaign_id",
                "adset_id",
                "ad_id",
                "utm_source",
                "utm_medium",
                "utm_campaign",
            )
        )
        if not has_attribution:
            warnings.append(
                {
                    "code": "missing_attribution_fields",
                    "message": "No campaign/ad ID or UTM fields found",
                }
            )

        # Set defaults
        if "canonical_status" not in result:
            result["canonical_status"] = CanonicalLeadStatus.NOT_REVIEWED.value
            result["is_reviewed"] = False

        return result

    def _parse_date(self, value: Any, timezone: str) -> datetime | None:
        """Parse a date value into UTC datetime."""
        if value is None:
            return None

        try:
            # Try ISO format first
            if isinstance(value, str):
                # Handle YYYY-MM-DD
                if len(value) == 10 and value.count("-") == 2:
                    # Treat as a date in the client's timezone
                    parsed = datetime.strptime(value, "%Y-%m-%d")
                    # Assume start of day in client timezone, then convert to UTC
                    # For simplicity, we treat it as UTC for now
                    return parsed.replace(tzinfo=UTC)

                # Try ISO datetime
                parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
                if parsed.tzinfo is None:
                    return parsed.replace(tzinfo=UTC)
                return parsed.astimezone(UTC)

            if isinstance(value, datetime):
                if value.tzinfo is None:
                    return value.replace(tzinfo=UTC)
                return value.astimezone(UTC)

        except (ValueError, TypeError):
            pass

        return None

    def _parse_boolean(self, value: Any) -> bool | None:
        """Parse various boolean representations."""
        if value is None:
            return None

        if isinstance(value, bool):
            return value

        if isinstance(value, int | float | Decimal):
            return bool(value)

        if isinstance(value, str):
            lower = value.strip().lower()
            if lower in ("true", "yes", "1", "t", "y"):
                return True
            if lower in ("false", "no", "0", "f", "n"):
                return False

        return None

    def _map_status(
        self,
        raw_status: str,
        status_mappings: dict[str, tuple[str, bool]],
    ) -> tuple[str, bool]:
        """Map raw status to canonical status using mappings."""
        if not raw_status:
            return CanonicalLeadStatus.NOT_REVIEWED.value, False

        # Normalise the raw status for lookup
        normalized = unicodedata.normalize("NFKC", raw_status).strip().casefold()
        normalized = " ".join(normalized.split())

        if normalized in status_mappings:
            canonical, is_reviewed = status_mappings[normalized]
            return canonical, is_reviewed

        return CanonicalLeadStatus.NOT_REVIEWED.value, False

    async def _get_mappings(
        self,
        *,
        client_id: UUID,
        config_id: UUID,
        version: int,
    ) -> dict[str, Any]:
        """Get column and status mappings for a config version."""
        column_rows = await self._client.select(
            table="field_mappings",
            columns=("source_header", "canonical_field", "required"),
            filters={
                "client_id": str(client_id),
                "google_sheet_config_id": str(config_id),
                "version": str(version),
            },
            limit=200,
        )

        status_rows = await self._client.select(
            table="status_mappings",
            columns=("source_value_normalized", "canonical_status", "counts_as_reviewed"),
            filters={
                "client_id": str(client_id),
                "google_sheet_config_id": str(config_id),
                "mapping_version": str(version),
            },
            limit=200,
        )

        # Build column mapping: canonical_field -> source_header
        column_mappings = {}
        for row in column_rows:
            source = row.get("source_header", "")
            canonical = row.get("canonical_field", "")
            if source and canonical:
                column_mappings[canonical] = source

        # Build status mapping: normalized_value -> (canonical_status, is_reviewed)
        status_mappings = {}
        for row in status_rows:
            source_value = row.get("source_value_normalized", "")
            canonical = row.get("canonical_status", "")
            is_reviewed = row.get("counts_as_reviewed", False)
            if source_value and canonical:
                status_mappings[source_value] = (canonical, is_reviewed)

        return {
            "column_mappings": column_mappings,
            "status_mappings": status_mappings,
        }
