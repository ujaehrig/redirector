"""DynamoDB implementation of the redirect repository."""

from datetime import UTC, datetime
from typing import Any

import boto3

from redirector.repository import RedirectEntry


class DynamoDbRedirectRepository:
    """DynamoDB implementation of the redirect repository."""

    def __init__(
        self,
        table_name: str,
        region: str,
        endpoint_url: str | None = None,
    ) -> None:
        """Initialize the DynamoDB repository.

        Args:
            table_name: Name of the DynamoDB table.
            region: AWS region.
            endpoint_url: Optional endpoint URL for local DynamoDB.
        """
        if endpoint_url:
            self._resource = boto3.resource(  # type: ignore[reportUnknownMemberType]
                "dynamodb",
                region_name=region,
                endpoint_url=endpoint_url,
            )
        else:
            self._resource = boto3.resource(  # type: ignore[reportUnknownMemberType]
                "dynamodb", region_name=region
            )
        self._table = self._resource.Table(table_name)

    def _item_to_entry(self, item: dict[str, Any]) -> RedirectEntry:
        """Convert a DynamoDB item to a RedirectEntry."""
        return RedirectEntry(
            short_code=item["short_code"],
            destination_url=item["destination_url"],
            status_code=int(item["status_code"]),
            created_at=datetime.fromisoformat(item["created_at"]),
            enabled=item["enabled"],
            owner_group=item.get("owner_group"),
            public=item.get("public", True),
        )

    def get_redirect(self, short_code: str) -> RedirectEntry | None:
        """Look up a redirect entry by short code.

        Args:
            short_code: The short code to look up.

        Returns:
            The redirect entry if found, None otherwise.
        """
        normalized = short_code.lower()
        response = self._table.get_item(Key={"short_code": normalized})
        item = response.get("Item")
        if item is None:
            return None
        return self._item_to_entry(item)

    def list_redirects(self) -> list[RedirectEntry]:
        """List all enabled redirect entries.

        Returns:
            A list of enabled redirect entries, ordered by short code.
        """
        response = self._table.scan(
            FilterExpression="enabled = :enabled",
            ExpressionAttributeValues={":enabled": True},
        )
        entries = [self._item_to_entry(item) for item in response["Items"]]
        return sorted(entries, key=lambda e: e.short_code)

    def list_public(self) -> list[RedirectEntry]:
        """List all enabled public redirect entries.

        Returns:
            A list of public redirect entries, ordered by short code.
        """
        response = self._table.scan(
            FilterExpression=(
                "enabled = :enabled AND "
                "(#pub = :pub_true OR attribute_not_exists(owner_group))"
            ),
            ExpressionAttributeNames={"#pub": "public"},
            ExpressionAttributeValues={
                ":enabled": True,
                ":pub_true": True,
            },
        )
        entries = [self._item_to_entry(item) for item in response["Items"]]
        return sorted(entries, key=lambda e: e.short_code)

    def list_by_groups(self, groups: list[str]) -> list[RedirectEntry]:
        """List entries visible to the given groups.

        Args:
            groups: List of group names the user belongs to.

        Returns:
            A list of redirect entries, ordered by short code.
        """
        if not groups:
            return self.list_public()

        # Scan all enabled, filter in Python for group membership + public
        response = self._table.scan(
            FilterExpression="enabled = :enabled",
            ExpressionAttributeValues={":enabled": True},
        )
        entries: list[RedirectEntry] = []
        for item in response["Items"]:
            entry = self._item_to_entry(item)  # type: ignore[arg-type]
            if entry.owner_group in groups or entry.public or entry.owner_group is None:
                entries.append(entry)
        return sorted(entries, key=lambda e: e.short_code)

    def add_redirect(
        self,
        short_code: str,
        destination_url: str,
        status_code: int,
        owner_group: str | None,
        public: bool,
    ) -> RedirectEntry:
        """Add a new redirect entry.

        Args:
            short_code: The short code for the redirect.
            destination_url: The destination URL.
            status_code: HTTP status code (301 or 302).
            owner_group: The owning group, or None.
            public: Whether the redirect is visible to all.

        Returns:
            The created redirect entry.
        """
        now = datetime.now(tz=UTC).isoformat()
        item: dict[str, Any] = {
            "short_code": short_code,
            "destination_url": destination_url,
            "status_code": status_code,
            "created_at": now,
            "enabled": True,
            "public": public,
        }
        if owner_group is not None:
            item["owner_group"] = owner_group
        self._table.put_item(Item=item)

        entry = self.get_redirect(short_code)
        assert entry is not None
        return entry

    def delete_redirect(self, short_code: str) -> bool:
        """Delete a redirect entry.

        Args:
            short_code: The short code to delete.

        Returns:
            True if deleted, False if not found.
        """
        # Check existence first
        existing = self.get_redirect(short_code)
        if existing is None:
            return False
        self._table.delete_item(Key={"short_code": short_code})
        return True

    def set_enabled(self, short_code: str, *, enabled: bool) -> bool:
        """Enable or disable a redirect entry.

        Args:
            short_code: The short code to update.
            enabled: Whether to enable or disable.

        Returns:
            True if updated, False if not found.
        """
        existing = self.get_redirect(short_code)
        if existing is None:
            return False
        self._table.update_item(
            Key={"short_code": short_code},
            UpdateExpression="SET enabled = :val",
            ExpressionAttributeValues={":val": enabled},
        )
        return True
