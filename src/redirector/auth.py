"""JWT authentication module."""

import logging
from dataclasses import dataclass, field
from typing import Any

import httpx
import jwt
from jwt.algorithms import RSAAlgorithm

logger = logging.getLogger(__name__)


class AuthError(Exception):
    """Raised when authentication fails."""


@dataclass(frozen=True)
class User:
    """Authenticated user extracted from a JWT token."""

    sub: str
    email: str
    groups: list[str] = field(default_factory=lambda: list[str]())
    is_admin: bool = False


class JWKSClient:
    """Fetches and caches JWKS signing keys from an identity provider."""

    def __init__(self, jwks_url: str) -> None:
        """Initialize the JWKS client.

        Args:
            jwks_url: URL to the JWKS endpoint.
        """
        self._jwks_url = jwks_url
        self._keys: dict[str, Any] = {}

    def _fetch_keys(self) -> None:
        """Fetch keys from the JWKS endpoint."""
        response = httpx.get(self._jwks_url, timeout=10.0)
        if response.status_code != 200:
            msg = f"Failed to fetch JWKS: HTTP {response.status_code}"
            raise AuthError(msg)
        jwks = response.json()
        self._keys = {}
        for key_data in jwks.get("keys", []):
            kid = key_data.get("kid")
            if kid:
                self._keys[kid] = key_data

    def get_signing_key(self, kid: str) -> Any:
        """Get the signing key for the given key ID.

        Fetches keys on first call and caches them. If the kid is
        not found, attempts one refresh before raising an error.

        Args:
            kid: The key ID from the JWT header.

        Returns:
            The public key for signature verification.

        Raises:
            AuthError: If the signing key cannot be found.
        """
        if not self._keys:
            self._fetch_keys()

        if kid not in self._keys:
            # Key rotation may have happened, try refreshing once
            self._fetch_keys()

        if kid not in self._keys:
            msg = f"Signing key not found for kid: {kid}"
            raise AuthError(msg)

        key_data = self._keys[kid]
        return RSAAlgorithm.from_jwk(key_data)


def decode_token(
    token: str,
    jwks_client: JWKSClient,
    issuer: str,
    audience: str,
) -> dict[str, Any]:
    """Decode and validate a JWT token.

    Args:
        token: The encoded JWT token string.
        jwks_client: JWKS client for key retrieval.
        issuer: Expected token issuer.
        audience: Expected token audience.

    Returns:
        The decoded token payload.

    Raises:
        AuthError: If the token is invalid, expired, or has
            wrong issuer/audience.
    """
    try:
        # Get the key ID from the token header
        unverified_header = jwt.get_unverified_header(token)
        kid = unverified_header.get("kid", "")
        signing_key = jwks_client.get_signing_key(kid)

        payload: dict[str, Any] = jwt.decode(
            token,
            signing_key,
            algorithms=["RS256"],
            issuer=issuer,
            audience=audience,
        )
    except jwt.ExpiredSignatureError as e:
        msg = "Token has expired"
        raise AuthError(msg) from e
    except (jwt.InvalidTokenError, jwt.PyJWTError) as e:
        msg = f"Invalid token: {e}"
        raise AuthError(msg) from e

    return payload


def extract_user(
    payload: dict[str, Any],
    groups_claim: str,
    admin_group: str,
) -> User:
    """Extract a User from a decoded JWT payload.

    Args:
        payload: The decoded JWT token payload.
        groups_claim: The claim name that contains group membership.
        admin_group: The group name that grants admin access.

    Returns:
        A User instance with identity and group information.
    """
    sub: str = str(payload.get("sub", ""))
    email: str = str(payload.get("email", ""))
    groups_raw: object = payload.get(groups_claim, [])
    if not isinstance(groups_raw, list):
        groups: list[str] = []
    else:
        groups = [str(g) for g in groups_raw]  # type: ignore[reportUnknownArgumentType]
    is_admin = admin_group in groups

    return User(
        sub=sub,
        email=email,
        groups=groups,
        is_admin=is_admin,
    )
