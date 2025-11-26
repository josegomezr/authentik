from datetime import timedelta

from django.core.cache import cache
from django.utils.timezone import now

from requests import Request
from requests.exceptions import RequestException

from structlog.stdlib import get_logger

from authentik.providers.scim.clients.exceptions import SCIMRequestException
from authentik.sources.oauth.clients.oauth2 import OAuth2Client
from authentik.sources.oauth.models import OAuthSource
from authentik.lib.utils.time import timedelta_from_string


class SUSESCIMOAuth2Handler:
    def __init__(self, provider):
        self.provider = provider
        self.logger = get_logger().bind()

    def _negotiate_oauth2_token_from_params(self, data):
        access_token_url = data["auth_url"]
        source = OAuthSource(
            consumer_key=data["client_id"],
            consumer_secret=data["client_secret"],
            access_token_url=access_token_url,
        )
        client = OAuth2Client(source, None)
        try:
            self.logger.debug("[SUSE] OAuth2 token request", **data)
            response = client.do_request(
                "POST",
                access_token_url,
                auth=client.get_access_token_auth(),
                data=data,
                headers=client._default_headers,
            )
            response.raise_for_status()
            body = response.json()
            token = body["access_token"]

            cache.set(self._cache_key(), token, timeout=self.cache_expiry(body))
            return token
        except RequestException as exc:
            raise SCIMRequestException(message="Failed to get auth token") from exc

    def cache_expiry(self, body):
        expires_seconds = timedelta_from_string("minutes=60").seconds

        if "expires_in" in body:
            expires_seconds = int(body.get("expires_in", 0))

        return expires_seconds

    def _cache_key(self):
        return f"v1/oauth-key-for-provider-{self.provider.pk}"

    def __call__(self, request: Request) -> Request:
        auth_token = cache.get(self._cache_key(), default=None)
        if not auth_token:
            self.logger.info("OAuth token expired, renewing token")
            auth_token = self._negotiate_oauth2_token_from_params(self.provider.auth_oauth_params)
        request.headers["Authorization"] = f"Bearer {auth_token}"
        return request
