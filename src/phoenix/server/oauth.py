from datetime import datetime, timedelta
from typing import Any, Dict, Generic, List, Optional, Tuple

from authlib.integrations.starlette_client import OAuth
from authlib.integrations.starlette_client import StarletteOAuth2App as OAuthClient
from typing_extensions import TypeAlias, TypeVar

from phoenix.config import OAuthClientConfig

IdpId: TypeAlias = str


class OAuthClients:
    def __init__(self) -> None:
        self._clients: Dict[IdpId, OAuthClient] = {}
        self._oauth = OAuth(cache=_OAuthClientTTLCache[str, Any]())

    def add_client(self, config: OAuthClientConfig) -> None:
        if (idp_id := config.idp_id) in self._clients:
            raise ValueError(f"oauth client already registered: {idp_id}")
        client = self._oauth.register(
            idp_id,
            client_id=config.client_id,
            client_secret=config.client_secret,
            server_metadata_url=config.server_metadata_url,
            client_kwargs={"scope": "openid email profile"},
        )
        assert isinstance(client, OAuthClient)
        self._clients[config.idp_id] = client

    def get_client(self, idp_id: IdpId) -> OAuthClient:
        if (client := self._clients.get(idp_id)) is None:
            raise ValueError(f"unknown or unregistered oauth client: {idp_id}")
        return client

    @classmethod
    def from_configs(cls, configs: List[OAuthClientConfig]) -> "OAuthClients":
        oauth_clients = cls()
        for config in configs:
            oauth_clients.add_client(config)
        return oauth_clients


_CacheKey = TypeVar("_CacheKey")
_CacheValue = TypeVar("_CacheValue")
_Expiry: TypeAlias = datetime
_MINUTE = timedelta(minutes=1)


class _OAuthClientTTLCache(Generic[_CacheKey, _CacheValue]):
    """
    A TTL cache satisfying the interface required by the Authlib Starlette
    integration. Provides an alternative to starlette session middleware.
    """

    def __init__(self, cleanup_interval: timedelta = 10 * _MINUTE) -> None:
        self._data: Dict[_CacheKey, Tuple[_CacheValue, _Expiry]] = {}
        self._last_cleanup_time = datetime.now()
        self._cleanup_interval = cleanup_interval

    async def get(self, key: _CacheKey) -> Optional[_CacheValue]:
        """
        Retrieves the value associated with the given key if it exists and has
        not expired, otherwise, returns None.
        """
        if (value_and_expiry := self._data.get(key)) is None:
            return None
        value, expiry = value_and_expiry
        if datetime.now() < expiry:
            return value
        self._data.pop(key, None)
        return None

    async def set(self, key: _CacheKey, value: _CacheValue, expires: int) -> None:
        """
        Sets the value associated with the given key to the provided value with
        the given expiry time in seconds.
        """
        self._remove_expired_keys_if_cleanup_interval_exceeded()
        expiry = datetime.now() + timedelta(seconds=expires)
        self._data[key] = (value, expiry)

    async def delete(self, key: _CacheKey) -> None:
        """
        Removes the value associated with the given key if it exists.
        """
        self._remove_expired_keys_if_cleanup_interval_exceeded()
        self._data.pop(key, None)

    def _remove_expired_keys_if_cleanup_interval_exceeded(self) -> None:
        time_since_last_cleanup = datetime.now() - self._last_cleanup_time
        if time_since_last_cleanup > self._cleanup_interval:
            self._remove_expired_keys()

    def _remove_expired_keys(self) -> None:
        current_time = datetime.now()
        delete_keys = [key for key, (_, expiry) in self._data.items() if expiry <= current_time]
        for key in delete_keys:
            self._data.pop(key, None)
        self._last_cleanup_time = current_time
