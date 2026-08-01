"""Deterministic lead matching to Meta entities."""

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from app.data.supabase import ReportingSupabaseClientProtocol
from app.matching.models import (
    MatchMethod,
    MatchResult,
    MatchSummary,
    ReviewStatus,
)


class MatchingError(Exception):
    """Base error for matching failures."""

    pass


class NoLeadsError(MatchingError):
    """No unprocessed leads found."""

    pass


MATCHING_RULE_VERSION = "2026-08-01-v1"


class LeadMatcher:
    """Deterministic matching of leads to Meta entities."""

    def __init__(self, client: ReportingSupabaseClientProtocol) -> None:
        self._client = client

    async def match_all(self, *, client_id: UUID) -> MatchSummary:
        """Match all unmatched leads for a client."""
        # Get unmatched leads
        unmatched_leads = await self._client.select(
            table="lead_records",
            columns=(
                "id",
                "client_id",
                "source_lead_id",
                "meta_lead_id",
                "lead_at",
                "campaign_id",
                "campaign_name",
                "adset_id",
                "adset_name",
                "ad_id",
                "ad_name",
                "utm_source",
                "utm_medium",
                "utm_campaign",
                "utm_content",
                "utm_term",
            ),
            filters={"client_id": str(client_id)},
            limit=2000,
        )

        # Filter to unmatched (no active match)
        matched_ids = await self._get_already_matched_ids(client_id=client_id)
        to_match = [l for l in unmatched_leads if UUID(l["id"]) not in matched_ids]

        if not to_match:
            return MatchSummary(
                client_id=client_id,
                leads_processed=0,
                leads_matched=0,
                leads_unmatched=0,
                leads_ambiguous=0,
                method_counts={},
                finished_at=datetime.now(UTC),
            )

        # Load Meta entities for this client
        meta_entities = await self._load_meta_entities(client_id=client_id)

        leads_matched = 0
        leads_unmatched = 0
        leads_ambiguous = 0
        method_counts: dict[str, int] = {}

        for lead in to_match:
            lead_id = UUID(lead["id"])
            result = self._match_lead(
                client_id=client_id,
                lead=lead,
                meta_entities=meta_entities,
            )

            if result:
                # Store the match
                await self._store_match(
                    client_id=client_id,
                    lead_id=lead_id,
                    match=result,
                )
                leads_matched += 1
                method = result.method
                method_counts[method] = method_counts.get(method, 0) + 1
            else:
                # Store as unmatched
                await self._store_unmatched(
                    client_id=client_id,
                    lead_id=lead_id,
                )
                leads_unmatched += 1
                method_counts[MatchMethod.UNMATCHED.value] = (
                    method_counts.get(MatchMethod.UNMATCHED.value, 0) + 1
                )

        # Create audit event
        await self._client.insert(
            table="audit_events",
            row={
                "client_id": str(client_id),
                "action": "match",
                "entity_type": "lead_matches",
                "entity_id": None,
                "event_metadata": {
                    "leads_processed": len(to_match),
                    "leads_matched": leads_matched,
                    "leads_unmatched": leads_unmatched,
                    "leads_ambiguous": leads_ambiguous,
                    "method_counts": method_counts,
                    "rule_version": MATCHING_RULE_VERSION,
                },
                "occurred_at": datetime.now(UTC).isoformat(),
            },
        )

        return MatchSummary(
            client_id=client_id,
            leads_processed=len(to_match),
            leads_matched=leads_matched,
            leads_unmatched=leads_unmatched,
            leads_ambiguous=leads_ambiguous,
            method_counts=method_counts,
            finished_at=datetime.now(UTC),
        )

    async def manual_match(
        self,
        *,
        client_id: UUID,
        lead_id: UUID,
        external_campaign_id: str | None = None,
        campaign_display_name: str | None = None,
        external_ad_set_id: str | None = None,
        ad_set_display_name: str | None = None,
        external_ad_id: str | None = None,
        ad_display_name: str | None = None,
        operator_label: str = "manual",
    ) -> MatchResult:
        """Apply a manual match decision."""
        # Deactivate any existing active match
        await self._client.update(
            table="lead_matches",
            values={"is_active": False},
            filters={
                "client_id": str(client_id),
                "lead_record_id": str(lead_id),
                "is_active": True,
            },
        )

        # Determine matched level
        matched_entity_level = "campaign"
        matched_entity_id = None
        confidence = Decimal("0.5")

        if external_ad_id:
            matched_entity_level = "ad"
            matched_entity_id = external_ad_id
            confidence = Decimal("0.9")
        elif external_ad_set_id:
            matched_entity_level = "ad_set"
            matched_entity_id = external_ad_set_id
            confidence = Decimal("0.85")
        elif external_campaign_id:
            matched_entity_level = "campaign"
            matched_entity_id = external_campaign_id
            confidence = Decimal("0.8")

        # Insert the new match
        now = datetime.now(UTC)
        row = {
            "client_id": str(client_id),
            "lead_record_id": str(lead_id),
            "external_campaign_id": external_campaign_id,
            "campaign_display_name": campaign_display_name,
            "external_ad_set_id": external_ad_set_id,
            "ad_set_display_name": ad_set_display_name,
            "external_ad_id": external_ad_id,
            "ad_display_name": ad_display_name,
            "method": MatchMethod.MANUAL.value,
            "confidence": float(confidence),
            "matched_identifiers": {
                "external_campaign_id": external_campaign_id,
                "external_ad_set_id": external_ad_set_id,
                "external_ad_id": external_ad_id,
            },
            "rule_version": MATCHING_RULE_VERSION,
            "review_status": ReviewStatus.MANUAL_APPROVED.value,
            "reviewed_by_label": operator_label,
            "reviewed_at": now.isoformat(),
            "is_active": True,
        }

        inserted = await self._client.insert(
            table="lead_matches",
            row=row,
        )

        # Create audit event
        await self._client.insert(
            table="audit_events",
            row={
                "client_id": str(client_id),
                "action": "manual_match",
                "entity_type": "lead_matches",
                "entity_id": str(lead_id),
                "event_metadata": {
                    "match_id": inserted.get("id"),
                    "matched_entity_level": matched_entity_level,
                    "matched_entity_id": matched_entity_id,
                    "operator_label": operator_label,
                },
                "occurred_at": now.isoformat(),
            },
        )

        return MatchResult(
            lead_record_id=lead_id,
            client_id=client_id,
            method=MatchMethod.MANUAL.value,
            confidence=confidence,
            matched_entity_level=matched_entity_level,
            matched_entity_id=matched_entity_id,
            matched_at=now,
            rule_version=MATCHING_RULE_VERSION,
            review_status=ReviewStatus.MANUAL_APPROVED.value,
        )

    async def get_unmatched(self, *, client_id: UUID, limit: int = 100) -> list[dict[str, Any]]:
        """Get unmatched leads for review."""
        # Get leads without active matches
        leads = await self._client.select(
            table="lead_records",
            columns=(
                "id",
                "client_id",
                "source_lead_id",
                "lead_at",
                "campaign_name",
                "adset_name",
                "ad_name",
                "utm_source",
                "utm_medium",
                "utm_campaign",
                "source_status_raw",
                "canonical_status",
            ),
            filters={"client_id": str(client_id)},
            limit=min(limit, 1000),
        )

        matched_ids = await self._get_already_matched_ids(client_id=client_id)
        unmatched = [l for l in leads if UUID(l["id"]) not in matched_ids]

        # For each unmatched lead, find potential candidates
        for lead in unmatched:
            candidates = await self._find_candidates(client_id=client_id, lead=lead)
            lead["match_candidates"] = candidates
            lead["candidate_count"] = len(candidates)

        return unmatched

    async def get_ambiguous(self, *, client_id: UUID, limit: int = 100) -> list[dict[str, Any]]:
        """Get leads with ambiguous matches (multiple candidates)."""
        unmatched = await self.get_unmatched(client_id=client_id, limit=limit)
        ambiguous = [l for l in unmatched if l.get("candidate_count", 0) > 1]
        return ambiguous

    def _match_lead(
        self,
        *,
        client_id: UUID,
        lead: dict[str, Any],
        meta_entities: dict[str, Any],
    ) -> MatchResult | None:
        """Match a single lead using priority order."""
        lead_id = UUID(lead["id"])

        # Priority 1: Exact Meta ad ID (from meta_lead_id field)
        meta_lead_id = lead.get("meta_lead_id")
        if meta_lead_id:
            # Match by Meta lead ID to specific ad
            ad = meta_entities["ad_by_lead_id"].get(meta_lead_id)
            if ad:
                return MatchResult(
                    lead_record_id=lead_id,
                    client_id=client_id,
                    method=MatchMethod.EXACT_AD_ID.value,
                    confidence=Decimal("1.0"),
                    matched_entity_level="ad",
                    matched_entity_id=ad["external_ad_id"],
                    matched_at=datetime.now(UTC),
                    rule_version=MATCHING_RULE_VERSION,
                )

        # Priority 1b: Exact ad ID from Sheet
        ad_id = lead.get("ad_id")
        if ad_id:
            ad = meta_entities["ad_by_id"].get(ad_id)
            if ad:
                return MatchResult(
                    lead_record_id=lead_id,
                    client_id=client_id,
                    method=MatchMethod.EXACT_AD_ID.value,
                    confidence=Decimal("1.0"),
                    matched_entity_level="ad",
                    matched_entity_id=ad["external_ad_id"],
                    matched_at=datetime.now(UTC),
                    rule_version=MATCHING_RULE_VERSION,
                )

        # Priority 2: Exact ad-set ID
        adset_id = lead.get("adset_id")
        if adset_id:
            adset = meta_entities["ad_set_by_id"].get(adset_id)
            if adset:
                return MatchResult(
                    lead_record_id=lead_id,
                    client_id=client_id,
                    method=MatchMethod.EXACT_AD_SET_ID.value,
                    confidence=Decimal("0.95"),
                    matched_entity_level="ad_set",
                    matched_entity_id=adset["external_ad_set_id"],
                    matched_at=datetime.now(UTC),
                    rule_version=MATCHING_RULE_VERSION,
                )

        # Priority 3: Exact campaign ID
        campaign_id = lead.get("campaign_id")
        if campaign_id:
            campaign = meta_entities["campaign_by_id"].get(campaign_id)
            if campaign:
                return MatchResult(
                    lead_record_id=lead_id,
                    client_id=client_id,
                    method=MatchMethod.EXACT_CAMPAIGN_ID.value,
                    confidence=Decimal("0.9"),
                    matched_entity_level="campaign",
                    matched_entity_id=campaign["external_campaign_id"],
                    matched_at=datetime.now(UTC),
                    rule_version=MATCHING_RULE_VERSION,
                )

        # Priority 4: UTM match
        utm_source = lead.get("utm_source")
        utm_medium = lead.get("utm_medium")
        utm_campaign = lead.get("utm_campaign")

        if utm_campaign or utm_source:
            # Try to find matching entities by UTMs
            utm_key = f"{utm_source or ''}|{utm_medium or ''}|{utm_campaign or ''}"
            candidates = meta_entities["by_utm"].get(utm_key, [])

            # Filter to only unique
            if len(candidates) == 1:
                entity = candidates[0]
                return MatchResult(
                    lead_record_id=lead_id,
                    client_id=client_id,
                    method=MatchMethod.UTM_MATCH.value,
                    confidence=Decimal("0.85"),
                    matched_entity_level=entity["level"],
                    matched_entity_id=entity["id"],
                    matched_at=datetime.now(UTC),
                    rule_version=MATCHING_RULE_VERSION,
                )

        # Priority 5: Unique name match
        name = lead.get("campaign_name")
        if name:
            # Check for unique campaign name
            campaigns_with_name = [
                c
                for c in meta_entities["campaign_by_id"].values()
                if c.get("name") and c["name"].strip().lower() == name.strip().lower()
            ]
            if len(campaigns_with_name) == 1:
                campaign = campaigns_with_name[0]
                return MatchResult(
                    lead_record_id=lead_id,
                    client_id=client_id,
                    method=MatchMethod.UNIQUE_NAME.value,
                    confidence=Decimal("0.7"),
                    matched_entity_level="campaign",
                    matched_entity_id=campaign["external_campaign_id"],
                    matched_at=datetime.now(UTC),
                    rule_version=MATCHING_RULE_VERSION,
                )

        # Priority 6: Unmatched
        return None

    async def _load_meta_entities(self, *, client_id: UUID) -> dict[str, Any]:
        """Load Meta entities for matching."""
        campaigns = await self._client.select(
            table="meta_campaigns",
            columns=("id", "external_campaign_id", "name"),
            filters={"client_id": str(client_id)},
            limit=500,
        )

        ad_sets = await self._client.select(
            table="meta_ad_sets",
            columns=("id", "external_ad_set_id", "name", "external_campaign_id"),
            filters={"client_id": str(client_id)},
            limit=1000,
        )

        ads = await self._client.select(
            table="meta_ads",
            columns=("id", "external_ad_id", "name", "external_ad_set_id", "creative_id"),
            filters={"client_id": str(client_id)},
            limit=2000,
        )

        # Build lookup dictionaries
        return {
            "campaign_by_id": {c["external_campaign_id"]: c for c in campaigns},
            "ad_set_by_id": {a["external_ad_set_id"]: a for a in ad_sets},
            "ad_by_id": {a["external_ad_id"]: a for a in ads},
            "ad_by_lead_id": {},  # Would need lead ID mapping from Meta
            "by_utm": {},  # Would need UTM mapping from ads
        }

    async def _get_already_matched_ids(self, *, client_id: UUID) -> set[UUID]:
        """Get IDs of leads that already have active matches."""
        matches = await self._client.select(
            table="lead_matches",
            columns=("lead_record_id",),
            filters={"client_id": str(client_id), "is_active": True},
            limit=5000,
        )
        return {UUID(m["lead_record_id"]) for m in matches}

    async def _store_match(
        self,
        *,
        client_id: UUID,
        lead_id: UUID,
        match: MatchResult,
    ) -> None:
        """Store a match result."""
        await self._client.insert(
            table="lead_matches",
            row={
                "client_id": str(client_id),
                "lead_record_id": str(lead_id),
                "external_campaign_id": match.matched_entity_id
                if match.matched_entity_level == "campaign"
                else None,
                "external_ad_set_id": match.matched_entity_id
                if match.matched_entity_level == "ad_set"
                else None,
                "external_ad_id": match.matched_entity_id
                if match.matched_entity_level == "ad"
                else None,
                "method": match.method,
                "confidence": float(match.confidence) if match.confidence else None,
                "matched_identifiers": {},
                "rule_version": match.rule_version,
                "review_status": match.review_status,
                "is_active": True,
            },
        )

    async def _store_unmatched(self, *, client_id: UUID, lead_id: UUID) -> None:
        """Store an unmatched result."""
        await self._client.insert(
            table="lead_matches",
            row={
                "client_id": str(client_id),
                "lead_record_id": str(lead_id),
                "method": MatchMethod.UNMATCHED.value,
                "matched_identifiers": {},
                "rule_version": MATCHING_RULE_VERSION,
                "review_status": ReviewStatus.AUTOMATIC.value,
                "is_active": True,
            },
        )

    async def _find_candidates(
        self, *, client_id: UUID, lead: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """Find potential match candidates for a lead."""
        candidates = []
        meta_entities = await self._load_meta_entities(client_id=client_id)

        # Check campaign ID
        campaign_id = lead.get("campaign_id")
        if campaign_id:
            campaign = meta_entities["campaign_by_id"].get(campaign_id)
            if campaign:
                candidates.append(
                    {
                        "entity_level": "campaign",
                        "external_entity_id": campaign_id,
                        "entity_display_name": campaign.get("name"),
                    }
                )

        # Check campaign name
        campaign_name = lead.get("campaign_name")
        if campaign_name:
            for c in meta_entities["campaign_by_id"].values():
                if (
                    c.get("name")
                    and c["name"].strip().lower() == campaign_name.strip().lower()
                    and c["external_campaign_id"]
                    not in [x["external_entity_id"] for x in candidates]
                ):
                    candidates.append(
                        {
                            "entity_level": "campaign",
                            "external_entity_id": c["external_campaign_id"],
                            "entity_display_name": c.get("name"),
                        }
                    )

        return candidates[:5]  # Limit to 5 candidates
