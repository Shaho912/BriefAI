from __future__ import annotations

from supabase import Client, create_client

from .config import settings

_client: Client | None = None


def get_admin_client() -> Client:
    """Return a singleton Supabase client using the service role key."""
    global _client
    if _client is None:
        _client = create_client(settings.supabase_url, settings.supabase_service_key)
    return _client
