from urllib.parse import parse_qs

import httpx
import pytest

from app.integrations.meta.client import MetaGraphClient


@pytest.mark.asyncio
async def test_campaign_discovery_reads_every_cursor_page() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        query = parse_qs(request.url.query.decode())
        assert request.headers["Authorization"] == "Bearer test-token"
        if "after" not in query:
            return httpx.Response(
                200,
                json={
                    "data": [{"id": "campaign-1", "name": "First"}],
                    "paging": {
                        "cursors": {"after": "next-cursor"},
                        "next": "https://graph.facebook.com/page-with-token",
                    },
                },
            )
        assert query["after"] == ["next-cursor"]
        return httpx.Response(
            200,
            json={"data": [{"id": "campaign-2", "name": "Second"}]},
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
        client = MetaGraphClient(access_token="test-token", http_client=http_client)
        campaigns = await client.get_campaigns(external_account_id="account-1", limit=1)

    assert [campaign.external_campaign_id for campaign in campaigns] == [
        "campaign-1",
        "campaign-2",
    ]
    assert len(requests) == 2
    assert all(request.url.path.endswith("/act_account-1/campaigns") for request in requests)
