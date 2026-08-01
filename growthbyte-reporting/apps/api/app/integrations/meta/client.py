"""HTTP client for Meta Graph API."""

import json
import logging
from typing import Any

import httpx

from app.core.errors import SafeApplicationError
from app.integrations.meta.models import (
    MetaAdAccountSummary,
    MetaAdSetSummary,
    MetaAdSummary,
    MetaCampaignSummary,
    MetaInsightRow,
)

logger = logging.getLogger(__name__)


class MetaApiError(SafeApplicationError):
    """Error from Meta Graph API with safe public representation."""

    code = "meta_api_error"
    safe_message = "The Meta Ads connection failed"
    status_code = 502


class MetaGraphClient:
    """
    HTTP client for Meta Graph API.

    Uses environment-level access token validated at startup.
    Never exposes tokens in logs or error messages.
    """

    def __init__(
        self,
        *,
        access_token: str,
        api_version: str = "v19.0",
        http_client: httpx.AsyncClient | None = None,
        timeout_seconds: float = 30.0,
    ) -> None:
        self._access_token = access_token
        self._base_url = f"https://graph.facebook.com/{api_version}"
        self._http_client = http_client
        self._timeout = timeout_seconds
        self._owned_client = False

    async def _get_client(self) -> httpx.AsyncClient:
        if self._http_client is None:
            self._http_client = httpx.AsyncClient(
                timeout=httpx.Timeout(self._timeout, connect=10.0)
            )
            self._owned_client = True
        return self._http_client

    async def close(self) -> None:
        if self._owned_client and self._http_client is not None:
            await self._http_client.aclose()
            self._http_client = None
            self._owned_client = False

    async def _request(self, *, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        """Make a GET request to Meta Graph API."""
        client = await self._get_client()
        url = f"{self._base_url}/{path}"
        try:
            response = await client.get(
                url,
                params=params or {},
                headers={"Authorization": f"Bearer {self._access_token}"},
            )
        except (httpx.TimeoutException, httpx.TransportError) as error:
            logger.warning(
                "Meta API network error",
                extra={"path": path, "error_type": type(error).__name__},
            )
            raise MetaApiError from error

        if response.status_code >= 400:
            logger.warning(
                "Meta API error response",
                extra={"path": path, "status": response.status_code},
            )
            raise MetaApiError

        try:
            payload = response.json()
        except ValueError as error:
            logger.warning("Meta API JSON decode error", extra={"path": path})
            raise MetaApiError from error

        if not isinstance(payload, dict):
            logger.warning("Meta API returned an invalid response")
            raise MetaApiError

        if "error" in payload:
            error_value = payload.get("error")
            error_code = error_value.get("code") if isinstance(error_value, dict) else None
            logger.warning(
                "Meta API returned error",
                extra={"path": path, "error_code": error_code},
            )
            raise MetaApiError

        return payload

    async def discover_ad_accounts(self) -> list[MetaAdAccountSummary]:
        """
        List ad accounts accessible to the environment token.

        Returns account summaries with IDs, names, and currencies.
        Never returns tokens or credentials.
        """
        try:
            # Get the "me" user's ad accounts
            data = await self._request(
                path="me/adaccounts",
                params={
                    "fields": "id,name,currency,timezone_name,account_status",
                    "limit": 100,
                },
            )

            accounts_data = data.get("data", [])
            accounts = []
            for account in accounts_data:
                # Remove "act_" prefix if present
                account_id = account.get("id", "")
                if account_id.startswith("act_"):
                    account_id = account_id[4:]

                accounts.append(
                    MetaAdAccountSummary(
                        external_account_id=account_id,
                        name=account.get("name"),
                        currency=account.get("currency"),
                        account_timezone=account.get("timezone_name"),
                        account_status=(
                            str(account["account_status"])
                            if account.get("account_status") is not None
                            else None
                        ),
                    )
                )

            return accounts
        except KeyError as error:
            logger.warning("Meta API response missing required key", exc_info=True)
            raise MetaApiError from error

    async def get_campaigns(
        self, *, external_account_id: str, limit: int = 100
    ) -> list[MetaCampaignSummary]:
        """Get campaigns for an ad account."""
        try:
            data = await self._request(
                path=f"act_{external_account_id}/campaigns",
                params={
                    "fields": "id,name,objective,status,effective_status",
                    "limit": str(limit),
                },
            )

            campaigns_data = data.get("data", [])
            return [
                MetaCampaignSummary(
                    external_campaign_id=campaign.get("id", ""),
                    name=campaign.get("name"),
                    objective=campaign.get("objective"),
                    status=campaign.get("status"),
                    effective_status=campaign.get("effective_status"),
                )
                for campaign in campaigns_data
            ]
        except KeyError as error:
            logger.warning("Meta API campaigns response missing key", exc_info=True)
            raise MetaApiError from error

    async def get_ad_sets(
        self, *, external_account_id: str, limit: int = 100
    ) -> list[MetaAdSetSummary]:
        """Get ad sets for an ad account."""
        try:
            data = await self._request(
                path=f"act_{external_account_id}/adsets",
                params={
                    "fields": "id,campaign_id,name,status,effective_status",
                    "limit": str(limit),
                },
            )

            ad_sets_data = data.get("data", [])
            return [
                MetaAdSetSummary(
                    external_ad_set_id=ad_set.get("id", ""),
                    external_campaign_id=ad_set.get("campaign_id"),
                    name=ad_set.get("name"),
                    status=ad_set.get("status"),
                    effective_status=ad_set.get("effective_status"),
                )
                for ad_set in ad_sets_data
            ]
        except KeyError as error:
            logger.warning("Meta API ad sets response missing key", exc_info=True)
            raise MetaApiError from error

    async def get_ads(self, *, external_account_id: str, limit: int = 100) -> list[MetaAdSummary]:
        """Get ads for an ad account."""
        try:
            data = await self._request(
                path=f"act_{external_account_id}/ads",
                params={
                    "fields": "id,adset_id,name,creative{id},status,effective_status",
                    "limit": str(limit),
                },
            )

            ads_data = data.get("data", [])
            return [
                MetaAdSummary(
                    external_ad_id=ad.get("id", ""),
                    external_ad_set_id=ad.get("adset_id"),
                    name=ad.get("name"),
                    creative_id=(
                        str(ad["creative"]["id"])
                        if isinstance(ad.get("creative"), dict) and ad["creative"].get("id")
                        else None
                    ),
                    status=ad.get("status"),
                    effective_status=ad.get("effective_status"),
                )
                for ad in ads_data
            ]
        except KeyError as error:
            logger.warning("Meta API ads response missing key", exc_info=True)
            raise MetaApiError from error

    async def get_insights(
        self,
        *,
        external_account_id: str,
        date_from: str,
        date_to: str,
        level: str = "account",
        limit: int = 100,
    ) -> list[MetaInsightRow]:
        """
        Get daily insights for an ad account.

        Args:
            external_account_id: Meta ad account ID (without "act_" prefix)
            date_from: Start date in YYYY-MM-DD format
            date_to: End date in YYYY-MM-DD format
            level: Granularity - "account", "campaign", "adset", or "ad"
            limit: Maximum number of rows per request

        Returns:
            List of insight rows with metrics
        """
        try:
            data = await self._request(
                path=f"act_{external_account_id}/insights",
                params={
                    "fields": (
                        "account_id,campaign_id,adset_id,ad_id,"
                        "impressions,reach,clicks,spend,"
                        "actions,action_values"
                    ),
                    "level": level,
                    "time_range": json.dumps({"since": date_from, "until": date_to}),
                    "time_increment": "1",  # Daily granularity
                    "limit": str(limit),
                },
            )

            insights_data = data.get("data", [])
            return [MetaInsightRow.model_validate(insight) for insight in insights_data]
        except KeyError as error:
            logger.warning("Meta API insights response missing key", exc_info=True)
            raise MetaApiError from error

    async def validate_token(self) -> bool:
        """Validate that the access token is working."""
        try:
            await self._request(path="me", params={"fields": "id"})
            return True
        except MetaApiError:
            return False
