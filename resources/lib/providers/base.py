# -*- coding: utf-8 -*-
"""
BaseProvider – základ pro všechny providery v StreamVault.

Každý provider deklaruje své schopnosti pomocí capability flags
a implementuje příslušná rozhraní.
"""
from __future__ import print_function, unicode_literals


class ProviderCapability:
    """Flagy schopností providera."""
    CATALOG = 'catalog'                     # poskytuje katalog titulů (browse/search)
    STREAMS = 'streams'                     # poskytuje stream kandidáty
    SUBTITLES = 'subtitles'                 # poskytuje titulky
    METADATA = 'metadata'                   # poskytuje metadata (TMDB, CSFD...)
    LIBRARY_EXPORT = 'library_export'       # tituly lze ukládat do Kodi knihovny
    SEARCH = 'search'                       # podporuje fulltextové vyhledávání
    STREAM_AUTO_PICK = 'stream_auto_pick'   # umí automaticky vybrat nejlepší stream
    PREFETCH_SUBTITLES = 'prefetch_subtitles'  # titulky dostupné před spuštěním přehrávání
    AUTH_REFRESH = 'auth_refresh'           # automatická obnova session/tokenu
    INTERNATIONAL = 'international'         # zahrnuje i zahraniční obsah (EN apod.)


class BaseProvider:
    """
    Základní třída pro všechny providery.

    Podtřídy přepisují:
      - PROVIDER_ID  (str)
      - CAPABILITIES (set of ProviderCapability)
      - metody podle deklarovaných schopností
    """

    PROVIDER_ID = 'base'
    CAPABILITIES = set()

    # --- Capability checks ---------------------------------------------------

    def has(self, capability):
        return capability in self.CAPABILITIES

    # --- Catalog -------------------------------------------------------------

    def browse(self, url):
        """
        Vrátí seznam položek katalogu pro danou URL.
        Returns: list[dict]  (SC API format)
        """
        raise NotImplementedError('{} nepodporuje browse()'.format(self.PROVIDER_ID))

    def search(self, query, page=1):
        """
        Vrátí výsledky hledání.
        Returns: list[dict]
        """
        raise NotImplementedError('{} nepodporuje search()'.format(self.PROVIDER_ID))

    # --- Streams -------------------------------------------------------------

    def get_streams(self, media_item, **kwargs):
        """
        Vrátí list[StreamCandidate] pro daný titul/epizodu.

        Args:
            media_item: Movie | Episode (z models.py)
            **kwargs: provider-specific params (quality_pref, lang_pref, ...)
        Returns:
            list[StreamCandidate]
        """
        raise NotImplementedError('{} nepodporuje get_streams()'.format(self.PROVIDER_ID))

    def resolve_stream(self, candidate):
        """
        Doresolví StreamCandidate.url pokud ještě není znám (ident → URL).

        Args:
            candidate: StreamCandidate
        Returns:
            str URL nebo None
        """
        raise NotImplementedError('{} nepodporuje resolve_stream()'.format(self.PROVIDER_ID))

    # --- Subtitles -----------------------------------------------------------

    def get_subtitles(self, media_item, **kwargs):
        """
        Vrátí list[SubtitleCandidate].
        """
        raise NotImplementedError('{} nepodporuje get_subtitles()'.format(self.PROVIDER_ID))

    # --- Metadata ------------------------------------------------------------

    def get_metadata(self, ids, media_type):
        """
        Obohatí Media IDs o metadata (poster, plot, rating...).

        Args:
            ids: MediaIds
            media_type: 'movie' | 'tvshow' | 'episode'
        Returns:
            dict s daty vhodnými pro Kodi ListItem
        """
        raise NotImplementedError('{} nepodporuje get_metadata()'.format(self.PROVIDER_ID))

    # --- Auth ----------------------------------------------------------------

    def is_authenticated(self):
        return True

    def authenticate(self):
        """Provede přihlášení / refresh tokenu. Returns: bool."""
        return True

    # --- Info ----------------------------------------------------------------

    def __repr__(self):
        caps = ', '.join(sorted(self.CAPABILITIES))
        return '<Provider id={} caps=[{}]>'.format(self.PROVIDER_ID, caps)
