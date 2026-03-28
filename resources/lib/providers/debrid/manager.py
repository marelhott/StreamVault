# -*- coding: utf-8 -*-
"""
DebridManager – centrální správce všech debrid služeb.

Načítá aktivní debrid klienta podle nastavení uživatele
a poskytuje jednotné rozhraní bez závislosti na konkrétní službě.
"""
from __future__ import print_function, unicode_literals

from resources.lib.common.logger import debug
from resources.lib.constants import (
    DEBRID_REALDEBRID, DEBRID_ALLDEBRID, DEBRID_PREMIUMIZE, DEBRID_TORBOX
)


class DebridManager:
    _instance = None

    def __init__(self):
        self._client = None
        self._service_id = None

    @classmethod
    def get(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def _load(self):
        if self._client is not None:
            return self._client
        try:
            from resources.lib.kodiutils import get_setting
            svc = get_setting('debrid.service')
        except Exception:
            svc = None

        if not svc or svc in ('', '0', 'none'):
            debug('debrid: žádná služba nenakonfigurována')
            self._client = None
            return None

        try:
            from resources.lib.kodiutils import get_setting
            api_key = get_setting('debrid.api_key')
        except Exception:
            api_key = None

        if not api_key:
            debug('debrid: chybí API klíč')
            self._client = None
            return None

        self._service_id = svc
        self._client = self._create_client(svc, api_key)
        return self._client

    def _create_client(self, service_id, api_key):
        debug('debrid: vytváří klienta pro {}'.format(service_id))
        if service_id == DEBRID_REALDEBRID:
            from resources.lib.providers.debrid.realdebrid import RealDebridClient
            return RealDebridClient(api_key)
        if service_id == DEBRID_ALLDEBRID:
            from resources.lib.providers.debrid.alldebrid import AllDebridClient
            return AllDebridClient(api_key)
        if service_id == DEBRID_PREMIUMIZE:
            from resources.lib.providers.debrid.premiumize import PremiumizeClient
            return PremiumizeClient(api_key)
        if service_id == DEBRID_TORBOX:
            from resources.lib.providers.debrid.torbox import TorBoxClient
            return TorBoxClient(api_key)
        debug('debrid: neznámá služba {}'.format(service_id))
        return None

    def is_available(self):
        return self._load() is not None

    def service_id(self):
        self._load()
        return self._service_id

    def check_cache(self, hashes):
        """
        Zkontroluje, které info hashe jsou cachované.

        Returns: set of cached hashes (lowercase)
        """
        client = self._load()
        if not client:
            return set()
        try:
            return client.check_cache(hashes) or set()
        except Exception:
            debug('debrid: check_cache error')
            return set()

    def resolve_torrent(self, info_hash, file_idx=None):
        """
        Přidá torrent a vrátí přímý stream URL.

        Returns: str URL nebo None
        """
        client = self._load()
        if not client:
            return None
        try:
            return client.resolve_torrent(info_hash, file_idx)
        except Exception:
            debug('debrid: resolve_torrent error')
            return None

    def unrestrict_link(self, link):
        """
        Unrestriktuje hoster link → přímý URL.

        Returns: str URL nebo None
        """
        client = self._load()
        if not client:
            return None
        try:
            return client.unrestrict_link(link)
        except Exception:
            debug('debrid: unrestrict_link error')
            return None

    def invalidate(self):
        self._client = None
        self._service_id = None
        self.__class__._instance = None
