"""Tests for the JWT authentication module."""

import time
from typing import Any
from unittest.mock import patch

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from redirector.auth import (
    AuthError,
    JWKSClient,
    User,
    decode_token,
    extract_user,
)


@pytest.fixture
def rsa_private_key() -> rsa.RSAPrivateKey:
    """Generate an RSA private key for testing."""
    return rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
    )


@pytest.fixture
def rsa_public_key(
    rsa_private_key: rsa.RSAPrivateKey,
) -> rsa.RSAPublicKey:
    """Get the public key from the private key."""
    return rsa_private_key.public_key()


@pytest.fixture
def jwks_response(rsa_public_key: rsa.RSAPublicKey) -> dict[str, Any]:
    """Create a JWKS response with the test public key."""
    from jwt.algorithms import RSAAlgorithm

    jwk: dict[str, Any] = RSAAlgorithm.to_jwk(rsa_public_key, as_dict=True)
    jwk["kid"] = "test-key-1"
    jwk["use"] = "sig"
    jwk["alg"] = "RS256"
    return {"keys": [jwk]}


@pytest.fixture
def valid_token(rsa_private_key: rsa.RSAPrivateKey) -> str:
    """Create a valid JWT token."""
    payload = {
        "sub": "user-123",
        "email": "user@example.com",
        "groups": ["engineering", "devops"],
        "iss": "https://idp.example.com/",
        "aud": "my-client-id",
        "exp": int(time.time()) + 3600,
        "iat": int(time.time()),
    }
    return jwt.encode(
        payload,
        rsa_private_key,
        algorithm="RS256",
        headers={"kid": "test-key-1"},
    )


@pytest.fixture
def expired_token(rsa_private_key: rsa.RSAPrivateKey) -> str:
    """Create an expired JWT token."""
    payload = {
        "sub": "user-123",
        "email": "user@example.com",
        "groups": ["engineering"],
        "iss": "https://idp.example.com/",
        "aud": "my-client-id",
        "exp": int(time.time()) - 3600,
        "iat": int(time.time()) - 7200,
    }
    return jwt.encode(
        payload,
        rsa_private_key,
        algorithm="RS256",
        headers={"kid": "test-key-1"},
    )


@pytest.fixture
def wrong_issuer_token(rsa_private_key: rsa.RSAPrivateKey) -> str:
    """Create a token with wrong issuer."""
    payload = {
        "sub": "user-123",
        "email": "user@example.com",
        "groups": ["engineering"],
        "iss": "https://wrong-issuer.com/",
        "aud": "my-client-id",
        "exp": int(time.time()) + 3600,
        "iat": int(time.time()),
    }
    return jwt.encode(
        payload,
        rsa_private_key,
        algorithm="RS256",
        headers={"kid": "test-key-1"},
    )


@pytest.fixture
def wrong_audience_token(rsa_private_key: rsa.RSAPrivateKey) -> str:
    """Create a token with wrong audience."""
    payload = {
        "sub": "user-123",
        "email": "user@example.com",
        "groups": ["engineering"],
        "iss": "https://idp.example.com/",
        "aud": "wrong-client-id",
        "exp": int(time.time()) + 3600,
        "iat": int(time.time()),
    }
    return jwt.encode(
        payload,
        rsa_private_key,
        algorithm="RS256",
        headers={"kid": "test-key-1"},
    )


@pytest.fixture
def no_groups_token(rsa_private_key: rsa.RSAPrivateKey) -> str:
    """Create a token without groups claim."""
    payload = {
        "sub": "user-123",
        "email": "user@example.com",
        "iss": "https://idp.example.com/",
        "aud": "my-client-id",
        "exp": int(time.time()) + 3600,
        "iat": int(time.time()),
    }
    return jwt.encode(
        payload,
        rsa_private_key,
        algorithm="RS256",
        headers={"kid": "test-key-1"},
    )


@pytest.fixture
def admin_token(rsa_private_key: rsa.RSAPrivateKey) -> str:
    """Create a token with admin group."""
    payload = {
        "sub": "admin-user",
        "email": "admin@example.com",
        "groups": ["admin", "engineering"],
        "iss": "https://idp.example.com/",
        "aud": "my-client-id",
        "exp": int(time.time()) + 3600,
        "iat": int(time.time()),
    }
    return jwt.encode(
        payload,
        rsa_private_key,
        algorithm="RS256",
        headers={"kid": "test-key-1"},
    )


class TestJWKSClient:
    """Test JWKS key fetching and caching."""

    def test_fetches_keys_from_url(self, jwks_response: dict[str, Any]) -> None:
        import httpx

        with patch("redirector.auth.httpx.get") as mock_get:
            mock_get.return_value = httpx.Response(200, json=jwks_response)
            client = JWKSClient("https://idp.example.com/.well-known/jwks.json")
            key = client.get_signing_key("test-key-1")

        assert key is not None
        mock_get.assert_called_once()

    def test_caches_keys_on_second_call(self, jwks_response: dict[str, Any]) -> None:
        import httpx

        with patch("redirector.auth.httpx.get") as mock_get:
            mock_get.return_value = httpx.Response(200, json=jwks_response)
            client = JWKSClient("https://idp.example.com/.well-known/jwks.json")
            client.get_signing_key("test-key-1")
            client.get_signing_key("test-key-1")

        mock_get.assert_called_once()

    def test_raises_on_unknown_kid(self, jwks_response: dict[str, Any]) -> None:
        import httpx

        with patch("redirector.auth.httpx.get") as mock_get:
            mock_get.return_value = httpx.Response(200, json=jwks_response)
            client = JWKSClient("https://idp.example.com/.well-known/jwks.json")

            with pytest.raises(AuthError, match="Signing key not found"):
                client.get_signing_key("unknown-key")

    def test_refreshes_on_unknown_kid_once(self, jwks_response: dict[str, Any]) -> None:
        import httpx

        with patch("redirector.auth.httpx.get") as mock_get:
            mock_get.return_value = httpx.Response(200, json=jwks_response)
            client = JWKSClient("https://idp.example.com/.well-known/jwks.json")
            # First call fetches keys
            client.get_signing_key("test-key-1")
            # Unknown kid triggers one refresh attempt
            with pytest.raises(AuthError, match="Signing key not found"):
                client.get_signing_key("unknown-key")

        # Initial fetch + one refresh attempt
        assert mock_get.call_count == 2


class TestDecodeToken:
    """Test JWT token decoding and validation."""

    def test_decodes_valid_token(
        self,
        valid_token: str,
        jwks_response: dict[str, Any],
    ) -> None:
        import httpx

        with patch("redirector.auth.httpx.get") as mock_get:
            mock_get.return_value = httpx.Response(200, json=jwks_response)
            client = JWKSClient("https://idp.example.com/.well-known/jwks.json")
            payload = decode_token(
                valid_token,
                client,
                issuer="https://idp.example.com/",
                audience="my-client-id",
            )

        assert payload["sub"] == "user-123"
        assert payload["groups"] == ["engineering", "devops"]

    def test_rejects_expired_token(
        self,
        expired_token: str,
        jwks_response: dict[str, Any],
    ) -> None:
        import httpx

        with patch("redirector.auth.httpx.get") as mock_get:
            mock_get.return_value = httpx.Response(200, json=jwks_response)
            client = JWKSClient("https://idp.example.com/.well-known/jwks.json")

            with pytest.raises(AuthError, match="expired"):
                decode_token(
                    expired_token,
                    client,
                    issuer="https://idp.example.com/",
                    audience="my-client-id",
                )

    def test_rejects_wrong_issuer(
        self,
        wrong_issuer_token: str,
        jwks_response: dict[str, Any],
    ) -> None:
        import httpx

        with patch("redirector.auth.httpx.get") as mock_get:
            mock_get.return_value = httpx.Response(200, json=jwks_response)
            client = JWKSClient("https://idp.example.com/.well-known/jwks.json")

            with pytest.raises(AuthError, match="Invalid token"):
                decode_token(
                    wrong_issuer_token,
                    client,
                    issuer="https://idp.example.com/",
                    audience="my-client-id",
                )

    def test_rejects_wrong_audience(
        self,
        wrong_audience_token: str,
        jwks_response: dict[str, Any],
    ) -> None:
        import httpx

        with patch("redirector.auth.httpx.get") as mock_get:
            mock_get.return_value = httpx.Response(200, json=jwks_response)
            client = JWKSClient("https://idp.example.com/.well-known/jwks.json")

            with pytest.raises(AuthError, match="Invalid token"):
                decode_token(
                    wrong_audience_token,
                    client,
                    issuer="https://idp.example.com/",
                    audience="my-client-id",
                )


class TestExtractUser:
    """Test user extraction from token payload."""

    def test_extracts_user_with_groups(self) -> None:
        payload = {
            "sub": "user-123",
            "email": "user@example.com",
            "groups": ["engineering", "devops"],
        }
        user = extract_user(payload, groups_claim="groups", admin_group="admin")
        assert user.sub == "user-123"
        assert user.email == "user@example.com"
        assert user.groups == ["engineering", "devops"]
        assert user.is_admin is False

    def test_extracts_admin_user(self) -> None:
        payload = {
            "sub": "admin-user",
            "email": "admin@example.com",
            "groups": ["admin", "engineering"],
        }
        user = extract_user(payload, groups_claim="groups", admin_group="admin")
        assert user.is_admin is True

    def test_empty_groups_when_claim_missing(self) -> None:
        payload = {
            "sub": "user-123",
            "email": "user@example.com",
        }
        user = extract_user(payload, groups_claim="groups", admin_group="admin")
        assert user.groups == []
        assert user.is_admin is False

    def test_custom_groups_claim(self) -> None:
        payload = {
            "sub": "user-123",
            "email": "user@example.com",
            "cognito:groups": ["marketing"],
        }
        user = extract_user(payload, groups_claim="cognito:groups", admin_group="admin")
        assert user.groups == ["marketing"]

    def test_email_defaults_to_empty(self) -> None:
        payload = {
            "sub": "user-123",
            "groups": ["engineering"],
        }
        user = extract_user(payload, groups_claim="groups", admin_group="admin")
        assert user.email == ""


class TestUser:
    """Test User dataclass."""

    def test_user_creation(self) -> None:
        user = User(
            sub="user-123",
            email="user@example.com",
            groups=["engineering"],
            is_admin=False,
        )
        assert user.sub == "user-123"
        assert user.email == "user@example.com"
        assert user.groups == ["engineering"]
        assert user.is_admin is False

    def test_admin_user(self) -> None:
        user = User(
            sub="admin",
            email="admin@example.com",
            groups=["admin"],
            is_admin=True,
        )
        assert user.is_admin is True


class TestJWKSClientErrors:
    """Test JWKS client error handling."""

    def test_raises_on_http_error(self) -> None:
        import httpx

        with patch("redirector.auth.httpx.get") as mock_get:
            mock_get.return_value = httpx.Response(500)
            client = JWKSClient("https://idp.example.com/.well-known/jwks.json")

            with pytest.raises(AuthError, match="Failed to fetch JWKS"):
                client.get_signing_key("any-kid")


class TestExtractUserEdgeCases:
    """Test edge cases in user extraction."""

    def test_non_list_groups_treated_as_empty(self) -> None:
        payload = {
            "sub": "user-123",
            "email": "user@example.com",
            "groups": "not-a-list",
        }
        user = extract_user(payload, groups_claim="groups", admin_group="admin")
        assert user.groups == []


class TestJWKSClientEmptyKeys:
    """Test JWKS client with empty key set."""

    def test_empty_keys_raises_on_any_kid(self) -> None:
        import httpx

        with patch("redirector.auth.httpx.get") as mock_get:
            mock_get.return_value = httpx.Response(200, json={"keys": []})
            client = JWKSClient("https://idp.example.com/.well-known/jwks.json")

            with pytest.raises(AuthError, match="Signing key not found"):
                client.get_signing_key("any-kid")

    def test_keys_without_kid_are_skipped(self) -> None:
        import httpx

        jwks_no_kid = {"keys": [{"kty": "RSA", "n": "abc", "e": "AQAB"}]}
        with patch("redirector.auth.httpx.get") as mock_get:
            mock_get.return_value = httpx.Response(200, json=jwks_no_kid)
            client = JWKSClient("https://idp.example.com/.well-known/jwks.json")

            with pytest.raises(AuthError, match="Signing key not found"):
                client.get_signing_key("any-kid")
