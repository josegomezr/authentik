"""SCIM Client"""

from typing import TYPE_CHECKING

from django.http import HttpResponseBadRequest, HttpResponseNotFound
from pydantic import ValidationError
from requests import RequestException, Session

from authentik.lib.sync.outgoing import (
    HTTP_CONFLICT,
    HTTP_NO_CONTENT,
    HTTP_SERVICE_UNAVAILABLE,
    HTTP_TOO_MANY_REQUESTS,
)
from authentik.lib.sync.outgoing.base import SAFE_METHODS, BaseOutgoingSyncClient
from authentik.lib.sync.outgoing.exceptions import (
    DryRunRejected,
    NotFoundSyncException,
    ObjectExistsSyncException,
    TransientSyncException,
)
from authentik.lib.utils.http import get_http_session
from authentik.lib.utils.time import timedelta_from_string
from authentik.providers.scim.clients.exceptions import SCIMRequestException
from authentik.providers.scim.clients.schema import ServiceProviderConfiguration
from authentik.providers.scim.models import SCIMCompatibilityMode, SCIMProvider

from urllib.parse import parse_qs
from django.core.cache import cache

if TYPE_CHECKING:
    from django.db.models import Model
    from pydantic import BaseModel


class SCIMClient[TModel: "Model", TConnection: "Model", TSchema: "BaseModel"](
    BaseOutgoingSyncClient[TModel, TConnection, TSchema, SCIMProvider]
):
    """SCIM Client"""

    base_url: str
    token: str

    _session: Session
    _config: ServiceProviderConfiguration

    def __init__(self, provider: SCIMProvider):
        super().__init__(provider)
        self._session = get_http_session()
        self._session.verify = provider.verify_certificates
        self.provider = provider
        # Remove trailing slashes as we assume the URL doesn't have any
        base_url = provider.url
        if base_url.endswith("/"):
            base_url = base_url[:-1]
        self.base_url = base_url
        self.token = provider.token
        self._config = self.get_service_provider_config()

    def _negotiate_oauth2_token_from_qs(self, qs):
        # TODO: this is not gonna be needed after fields exists in the DB
        cfg = {}
        try:
            cfg.update(
                {k: v[0] for k, v in parse_qs(qs, strict_parsing=True).items() if len(v) > 0}
            )
        except (KeyError, ValueError) as exc:
            raise SCIMRequestException(
                message="Failed to negotiate auth token: invalid qs"
            ) from exc
        # / TODO: this is not gonna be needed after fields exists in the DB

        auth_url = cfg["auth_url"]
        client_id = cfg["client_id"]
        grant_type = cfg["grant_type"]
        client_secret = cfg["client_secret"]
        expiry = timedelta_from_string(cfg.get("expiry", "minutes=60"))

        try:
            self.logger.debug("scim auth token request", **cfg)
            response = self._session.request(
                "POST",
                f"{auth_url}",
                data={
                    "client_id": client_id,
                    "grant_type": grant_type,
                    "client_secret": client_secret,
                },
                headers={"Accept": "application/json"},
            )
            response.raise_for_status()
            token = response.json()["access_token"]

            cache.set(self._cache_key(), token, timeout=expiry.seconds)
            return token
        except RequestException as exc:
            raise SCIMRequestException(message="Failed to get auth token") from exc

    def _cache_key(self):
        return f"v1/oauth-key-for-provider-{self.provider.pk}"

    def _request(self, method: str, path: str, **kwargs) -> dict:
        """Wrapper to send a request to the full URL"""
        if self.provider.dry_run and method.upper() not in SAFE_METHODS:
            raise DryRunRejected(f"{self.base_url}{path}", method, body=kwargs.get("json"))

        # Very hacky way of passing more information on a single field to avoid a db migration
        # if I can read a query string out of the token value then:
        # - use 'token' directly if it's present
        # - negotiate an oauth token in 'auth_url' with 'client_id', 'client_secret' and 'grant_type'
        oauth_needle = "__OAUTH2__"
        token = self.token

        if self.token.startswith(oauth_needle):
            qs = self.token[len(oauth_needle) :]

            auth_token = cache.get(self._cache_key(), default=None)
            if not auth_token:
                auth_token = self._negotiate_oauth2_token_from_qs(qs)

            token = auth_token

        headers = {
            "Accept": "application/scim+json",
            "Content-Type": "application/scim+json",
        }

        if token:
            headers["Authorization"] = f"Bearer {token}"

        try:
            response = self._session.request(
                method,
                f"{self.base_url}{path}",
                **kwargs,
                headers=headers,
            )
        except RequestException as exc:
            raise SCIMRequestException(message="Failed to send request") from exc
        self.logger.debug("scim request", path=path, method=method, **kwargs)
        if response.status_code >= HttpResponseBadRequest.status_code:
            if response.status_code == HttpResponseNotFound.status_code:
                raise NotFoundSyncException(response)
            if response.status_code in [HTTP_TOO_MANY_REQUESTS, HTTP_SERVICE_UNAVAILABLE]:
                raise TransientSyncException()
            if response.status_code == HTTP_CONFLICT:
                raise ObjectExistsSyncException(response)
            self.logger.warning(
                "Failed to send SCIM request", path=path, method=method, response=response.text
            )
            raise SCIMRequestException(response)
        if response.status_code == HTTP_NO_CONTENT:
            return {}
        return response.json()

    def get_service_provider_config(self):
        """Get Service provider config"""
        default_config = ServiceProviderConfiguration.default()
        endpoint = "/ServiceProviderConfig"
        if self.provider.compatibility_mode == SCIMCompatibilityMode.SFDC:
            endpoint = "/ServiceProviderConfigs"

        try:
            config = ServiceProviderConfiguration.model_validate(self._request("GET", endpoint))
            if self.provider.compatibility_mode == SCIMCompatibilityMode.AWS:
                config.patch.supported = False
            if self.provider.compatibility_mode == SCIMCompatibilityMode.SLACK:
                config.filter.supported = True
            return config
        except (ValidationError, SCIMRequestException, NotFoundSyncException) as exc:
            self.logger.warning("failed to get ServiceProviderConfig", exc=exc)
            return default_config
