from __future__ import annotations

from rich.console import Console
from supabase import create_client

console = Console()


class SupabaseStorage:
    """Uploads MP3 files to Supabase Storage and returns a public URL."""

    def __init__(self, url: str, service_key: str, bucket: str) -> None:
        self.client = create_client(url, service_key)
        self.bucket = bucket

    def upload(self, mp3_bytes: bytes, filename: str) -> str:
        """
        Upload MP3 bytes to the configured bucket.

        Overwrites if the file already exists (upsert=True).
        Returns the public URL of the uploaded file.
        """
        with console.status(f"[dim]Uploading {filename} to Supabase...[/dim]", spinner="dots"):
            self.client.storage.from_(self.bucket).upload(
                path=filename,
                file=mp3_bytes,
                file_options={
                    "content-type": "audio/mpeg",
                    "upsert": "true",
                },
            )
            public_url = self.client.storage.from_(self.bucket).get_public_url(filename)

        console.print(f"[bold green]Uploaded to Supabase:[/bold green] {public_url}")
        return public_url
