import argparse
import asyncio
import json
import sys
from typing import Any

from app.core.config import get_settings
from app.data.supabase import (
    ReadOnlyKnowledgeSupabaseClient,
    ReportingSupabaseClient,
    create_knowledge_supabase_client,
    create_reporting_supabase_client,
)
from app.knowledge.errors import KnowledgeImportError
from app.knowledge.mapper import KnowledgeMapper
from app.knowledge.service import KnowledgeImportService
from app.knowledge.source import ReadOnlyKnowledgeAdapter
from app.repositories.client_knowledge import ClientKnowledgeRepository
from app.repositories.clients import ReportingClientRepository


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Preview or apply a client knowledge import")
    subparsers = parser.add_subparsers(dest="command", required=True)

    preview = subparsers.add_parser("preview", help="perform a zero-write preview")
    _add_identifiers(preview)
    preview.add_argument("--target-status")

    apply = subparsers.add_parser("apply", help="perform a confirmed atomic upsert")
    _add_identifiers(apply)
    apply.add_argument("--target-status", required=True)
    apply.add_argument("--confirm-target-client-id", required=True)
    return parser


def _add_identifiers(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--source-client-id", required=True)
    parser.add_argument("--target-client-id", required=True)


async def _run(args: argparse.Namespace) -> dict[str, Any]:
    reporting_client: ReportingSupabaseClient | None = None
    knowledge_client: ReadOnlyKnowledgeSupabaseClient | None = None
    try:
        settings = get_settings()
        reporting_client = create_reporting_supabase_client(settings.reporting_supabase)
        knowledge_client = create_knowledge_supabase_client(settings.knowledge_supabase)
        service = KnowledgeImportService(
            clients=ReportingClientRepository(reporting_client),
            knowledge=ClientKnowledgeRepository(reporting_client),
            source=ReadOnlyKnowledgeAdapter(knowledge_client),
            mapper=KnowledgeMapper(),
        )
        if args.command == "preview":
            result = await service.preview(
                source_client_identifier=args.source_client_id,
                target_client_id=args.target_client_id,
                target_status=args.target_status,
            )
        else:
            result = await service.apply(
                source_client_identifier=args.source_client_id,
                target_client_id=args.target_client_id,
                confirm_target_client_id=args.confirm_target_client_id,
                target_status=args.target_status,
            )
        return result.model_dump(mode="json")
    finally:
        if knowledge_client is not None:
            await knowledge_client.close()
        if reporting_client is not None:
            await reporting_client.close()


def main() -> int:
    args = _parser().parse_args()
    try:
        payload = asyncio.run(_run(args))
    except KnowledgeImportError as error:
        payload = {"error": {"code": error.code, "message": error.safe_message}}
        print(json.dumps(payload, sort_keys=True), file=sys.stderr)
        return 2
    except Exception:
        payload = {"error": {"code": "internal_error", "message": "Knowledge import failed"}}
        print(json.dumps(payload, sort_keys=True), file=sys.stderr)
        return 1
    print(json.dumps(payload, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
