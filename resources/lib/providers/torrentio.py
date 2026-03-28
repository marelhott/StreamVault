# -*- coding: utf-8 -*-
"""
Torrentio provider pro StreamVault.

Torrentio je veřejné HTTP API (https://torrentio.strem.fun) kompatibilní
se Stremio addon protokolem. Lze ho volat přímo bez Stremia.

Endpoint:
  GET https://torrentio.strem.fun/{config}/stream/{type}/{id}.json
  - {config} = prázdný nebo "realdebrid=KEY/" apod.
  - {type}   = "movie" nebo "series"
  - {id}     = IMDB ID (tt...) nebo "tt...:S:E" pro epizody

Pokud uživatel zadá debrid API klíč, Torrentio vrátí přímo stream URL.
Bez debrid klíče vrátí infoHash (surový torrent – přehrání nevyřeší).
"""
from __future__ import print_function, unicode_literals

import traceback

from resources.lib.common.logger import debug
from resources.lib.models import StreamCandidate
from resources.lib.providers.base import BaseProvider, ProviderCapability

TORRENTIO_BASE = 'https://torrentio.strem.fun'

# Mapování debrid service ID → Torrentio config klíč
DEBRID_CONFIG_KEYS = {
    'realdebrid': 'realdebrid',
    'alldebrid': 'alldebrid',
    'premiumize': 'premiumize',
    'torbox': 'torbox',
    'debridlink': 'debridlink',
}

# Kvalita z názvu souboru → standardní label
_QUALITY_MAP = [
    ('2160p', '4K'), ('4k', '4K'), ('uhd', '4K'),
    ('1080p', '1080p'), ('1080i', '1080p'),
    ('720p', '720p'), ('720i', '720p'),
    ('480p', '480p'), ('sd', 'SD'),
]

_CODEC_MAP = [
    ('hevc', 'h265'), ('h265', 'h265'), ('x265', 'h265'),
    ('h264', 'h264'), ('x264', 'h264'), ('avc', 'h264'),
    ('av1', 'av1'), ('xvid', 'xvid'), ('divx', 'divx'),
]

_HDR_TAGS = ('hdr', 'hdr10', 'hdr10+', 'dolby vision', 'dv', 'hlg')
_DV_TAGS = ('dolby vision', 'dv')
_AUDIO_MAP = [
    ('dolby atmos', 'atmos'), ('truehd', 'truehd'),
    ('dts-hd', 'dtshd'), ('dts-x', 'dtsx'), ('dts', 'dts'),
    ('eac3', 'eac3'), ('dd+', 'eac3'), ('ac3', 'ac3'),
    ('dd', 'ac3'), ('aac', 'aac'), ('mp3', 'mp3'),
]


def _parse_quality(title):
    """Extrahuje quality, codecs, HDR z názvu souboru/torrentu."""
    t = title.lower()
    quality = None
    for tag, label in _QUALITY_MAP:
        if tag in t:
            quality = label
            break

    video_codec = None
    for tag, codec in _CODEC_MAP:
        if tag in t:
            video_codec = codec
            break

    audio_codec = None
    for tag, codec in _AUDIO_MAP:
        if tag in t:
            audio_codec = codec
            break

    hdr = any(tag in t for tag in _HDR_TAGS)
    dv = any(tag in t for tag in _DV_TAGS)

    return quality, video_codec, audio_codec, hdr, dv


def _build_config(debrid_service=None, debrid_key=None):
    """Sestaví Torrentio config string pro URL."""
    if debrid_service and debrid_key:
        key = DEBRID_CONFIG_KEYS.get(debrid_service, debrid_service)
        return '{}={}'.format(key, debrid_key)
    return ''


class TorrentioProvider(BaseProvider):

    PROVIDER_ID = 'torrentio'
    CAPABILITIES = {
        ProviderCapability.STREAMS,
        ProviderCapability.SEARCH,
        ProviderCapability.INTERNATIONAL,
        ProviderCapability.STREAM_AUTO_PICK,
    }

    def __init__(self, debrid_service=None, debrid_key=None):
        self._debrid_service = debrid_service
        self._debrid_key = debrid_key

    def _load_debrid_settings(self):
        """Načte debrid nastavení z Kodi settings pokud nebyly předány."""
        if not self._debrid_service or not self._debrid_key:
            try:
                from resources.lib.kodiutils import get_setting
                svc = get_setting('debrid.service')
                key = get_setting('debrid.api_key')
                if svc and svc != '0' and key:
                    self._debrid_service = svc
                    self._debrid_key = key
            except Exception:
                pass

    def get_streams(self, media_item, **kwargs):
        """
        Vrátí list[StreamCandidate] z Torrentio API.

        Pokud je nastavený debrid klíč, vrátí přímé URL.
        Bez debrid vrátí prázdný seznam (raw torrent nelze bez debrid přehrát).
        """
        self._load_debrid_settings()

        imdb_id = getattr(media_item, 'ids', None)
        if imdb_id:
            imdb_id = imdb_id.imdb
        if not imdb_id:
            debug('torrentio: chybí IMDB ID')
            return []

        media_type = getattr(media_item, 'media_type', 'movie')
        if media_type == 'episode':
            season = getattr(media_item, 'season', None)
            episode = getattr(media_item, 'episode', None)
            torrentio_type = 'series'
            torrentio_id = '{}:{}:{}'.format(imdb_id, season, episode)
        else:
            torrentio_type = 'movie'
            torrentio_id = imdb_id

        config = _build_config(self._debrid_service, self._debrid_key)
        if config:
            url = '{}/{}/stream/{}/{}.json'.format(
                TORRENTIO_BASE, config, torrentio_type, torrentio_id)
        else:
            url = '{}/stream/{}/{}.json'.format(
                TORRENTIO_BASE, torrentio_type, torrentio_id)

        debug('torrentio: GET {}'.format(url))
        return self._fetch_streams(url)

    def _fetch_streams(self, url):
        try:
            from resources.lib.system import Http
            resp = Http.get(url, timeout=20)
            if resp.status_code != 200:
                debug('torrentio: HTTP {}'.format(resp.status_code))
                return []
            data = resp.json()
        except Exception:
            debug('torrentio: fetch error: {}'.format(traceback.format_exc()))
            return []

        streams = []
        for item in data.get('streams', []):
            candidate = self._parse_stream(item)
            if candidate:
                streams.append(candidate)

        debug('torrentio: nalezeno {} stream kandidátů'.format(len(streams)))
        return streams

    def _parse_stream(self, item):
        """Parsuje jeden stream objekt z Torrentio odpovědi."""
        stream_url = item.get('url')
        info_hash = item.get('infoHash')

        # Bez debrid nemáme URL – přeskočit
        if not stream_url and not info_hash:
            return None

        name = item.get('name', '')
        title = item.get('title', '')
        full_text = '{} {}'.format(name, title)

        quality, video_codec, audio_codec, hdr, dv = _parse_quality(full_text)

        # Extrahuj velikost z title (formát "💾 8.2 GB")
        size_bytes = None
        import re
        size_match = re.search(r'💾\s*([\d.]+)\s*(GB|MB)', title)
        if size_match:
            val = float(size_match.group(1))
            unit = size_match.group(2)
            size_bytes = int(val * (1024 ** 3 if unit == 'GB' else 1024 ** 2))

        # Pěkný label pro dialog výběru
        label_parts = []
        if quality:
            label_parts.append(quality)
        if hdr:
            label_parts.append('HDR')
        if dv:
            label_parts.append('DV')
        if video_codec:
            label_parts.append(video_codec.upper())
        if audio_codec:
            label_parts.append(audio_codec.upper())
        if size_bytes:
            label_parts.append('{:.1f} GB'.format(size_bytes / 1024 ** 3))
        label = ' | '.join(label_parts) if label_parts else name

        return StreamCandidate(
            url=stream_url,
            info_hash=info_hash,
            file_idx=item.get('fileIdx'),
            provider_id=self.PROVIDER_ID,
            quality=quality,
            video_codec=video_codec,
            audio_codec=audio_codec,
            hdr=hdr,
            dolby_vision=dv,
            size_bytes=size_bytes,
            label=label,
            is_debrid=bool(stream_url),
            debrid_service=self._debrid_service,
        )

    def resolve_stream(self, candidate):
        """Torrentio s debrid klíčem vrací URL přímo – resolve není potřeba."""
        return candidate.url

    def is_available(self):
        """Provider je dostupný jen pokud je nastavený debrid klíč."""
        self._load_debrid_settings()
        return bool(self._debrid_service and self._debrid_key)
