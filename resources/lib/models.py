# -*- coding: utf-8 -*-
"""
Unified item model pro StreamVault.

Všechny části addonu (UI, knihovna, přehrávač, providery) pracují
s těmito datovými strukturami – žádné ad-hoc dicty.
"""
from __future__ import print_function, unicode_literals


class MediaIds:
    """Sada externích identifikátorů pro jeden titul."""

    def __init__(self, imdb=None, tmdb=None, tvdb=None, csfd=None):
        self.imdb = imdb    # tt1234567
        self.tmdb = tmdb    # 12345 (int nebo str)
        self.tvdb = tvdb    # 12345
        self.csfd = csfd    # 12345

    def to_dict(self):
        return {k: v for k, v in {
            'imdb': self.imdb,
            'tmdb': str(self.tmdb) if self.tmdb else None,
            'tvdb': str(self.tvdb) if self.tvdb else None,
            'csfd': str(self.csfd) if self.csfd else None,
        }.items() if v}

    @classmethod
    def from_dict(cls, d):
        if not d:
            return cls()
        return cls(
            imdb=d.get('imdb'),
            tmdb=d.get('tmdb'),
            tvdb=d.get('tvdb'),
            csfd=d.get('csfd'),
        )

    def __bool__(self):
        return any([self.imdb, self.tmdb, self.tvdb, self.csfd])

    __nonzero__ = __bool__


class ArtWork:
    """Obrázky pro Kodi ListItem."""

    def __init__(self, poster=None, fanart=None, thumb=None, banner=None, clearlogo=None):
        self.poster = poster
        self.fanart = fanart
        self.thumb = thumb or poster
        self.banner = banner
        self.clearlogo = clearlogo

    def to_dict(self):
        return {k: v for k, v in {
            'poster': self.poster,
            'fanart': self.fanart,
            'thumb': self.thumb,
            'banner': self.banner,
            'clearlogo': self.clearlogo,
        }.items() if v}


class Movie:
    media_type = 'movie'

    def __init__(self, title, year=None, ids=None, art=None, plot=None,
                 rating=None, votes=None, genres=None, runtime=None,
                 mpaa=None, sc_url=None):
        self.title = title
        self.year = year
        self.ids = ids or MediaIds()
        self.art = art or ArtWork()
        self.plot = plot
        self.rating = rating
        self.votes = votes
        self.genres = genres or []
        self.runtime = runtime
        self.mpaa = mpaa
        self.sc_url = sc_url   # URL na SC API pro streamování

    def info_dict(self):
        d = {'mediatype': 'movie', 'title': self.title}
        if self.year:
            d['year'] = self.year
        if self.plot:
            d['plot'] = self.plot
        if self.rating:
            d['rating'] = self.rating
        if self.votes:
            d['votes'] = self.votes
        if self.genres:
            d['genre'] = self.genres
        if self.runtime:
            d['duration'] = self.runtime
        if self.mpaa:
            d['mpaa'] = self.mpaa
        return d


class TVShow:
    media_type = 'tvshow'

    def __init__(self, title, year=None, ids=None, art=None, plot=None,
                 rating=None, status=None, sc_url=None):
        self.title = title
        self.year = year
        self.ids = ids or MediaIds()
        self.art = art or ArtWork()
        self.plot = plot
        self.rating = rating
        self.status = status
        self.sc_url = sc_url

    def info_dict(self):
        d = {'mediatype': 'tvshow', 'tvshowtitle': self.title}
        if self.year:
            d['year'] = self.year
        if self.plot:
            d['plot'] = self.plot
        if self.rating:
            d['rating'] = self.rating
        return d


class Season:
    media_type = 'season'

    def __init__(self, show_title, season_number, ids=None, art=None,
                 episode_count=None, sc_url=None):
        self.show_title = show_title
        self.season_number = season_number
        self.ids = ids or MediaIds()
        self.art = art or ArtWork()
        self.episode_count = episode_count
        self.sc_url = sc_url

    def info_dict(self):
        return {
            'mediatype': 'season',
            'tvshowtitle': self.show_title,
            'season': self.season_number,
        }


class Episode:
    media_type = 'episode'

    def __init__(self, show_title, season, episode, title=None,
                 ids=None, art=None, plot=None, rating=None,
                 aired=None, runtime=None, sc_url=None):
        self.show_title = show_title
        self.season = season
        self.episode = episode
        self.title = title
        self.ids = ids or MediaIds()
        self.art = art or ArtWork()
        self.plot = plot
        self.rating = rating
        self.aired = aired
        self.runtime = runtime
        self.sc_url = sc_url

    def info_dict(self):
        d = {
            'mediatype': 'episode',
            'tvshowtitle': self.show_title,
            'season': self.season,
            'episode': self.episode,
        }
        if self.title:
            d['title'] = self.title
        if self.plot:
            d['plot'] = self.plot
        if self.rating:
            d['rating'] = self.rating
        if self.aired:
            d['aired'] = self.aired
        if self.runtime:
            d['duration'] = self.runtime
        return d


class StreamCandidate:
    """Jeden stream kandidát vrácený providerem."""

    def __init__(self, url=None, ident=None, provider_id=None,
                 quality=None, resolution=None, bitrate=None,
                 audio_lang=None, audio_codec=None,
                 video_codec=None, hdr=False, dolby_vision=False,
                 size_bytes=None, label=None, is_debrid=False,
                 info_hash=None, file_idx=None, debrid_service=None):
        self.url = url                      # přímý stream URL (pokud znám)
        self.ident = ident                  # kra.sk / WebShare ident (pokud URL není znám)
        self.provider_id = provider_id      # 'kraska' | 'webshare' | 'torrentio' | ...
        self.quality = quality              # '4K' | '1080p' | '720p' | 'SD'
        self.resolution = resolution        # (1920, 1080)
        self.bitrate = bitrate              # kbps
        self.audio_lang = audio_lang        # 'cs' | 'sk' | 'en' | ...
        self.audio_codec = audio_codec      # 'ac3' | 'eac3' | 'aac' | 'dts' | ...
        self.video_codec = video_codec      # 'h264' | 'h265' | 'av1' | ...
        self.hdr = hdr
        self.dolby_vision = dolby_vision
        self.size_bytes = size_bytes
        self.label = label                  # zobrazovaný label v dialogu výběru
        self.is_debrid = is_debrid
        self.info_hash = info_hash          # pro torrent-based kandidáty
        self.file_idx = file_idx
        self.debrid_service = debrid_service  # 'realdebrid' | 'alldebrid' | ...

    @property
    def quality_score(self):
        """Numerické skóre kvality pro řazení (vyšší = lepší)."""
        scores = {'4K': 4000, '2160p': 4000, '1080p': 1000, '720p': 700, '480p': 480, 'SD': 400}
        base = scores.get(self.quality, 0)
        if self.dolby_vision:
            base += 200
        if self.hdr:
            base += 100
        if self.bitrate:
            base += min(self.bitrate // 1000, 100)
        return base

    def __repr__(self):
        return '<StreamCandidate provider={} quality={} lang={}>'.format(
            self.provider_id, self.quality, self.audio_lang)


class SubtitleCandidate:
    """Jeden titulek kandidát."""

    def __init__(self, url=None, lang=None, lang_name=None,
                 provider_id=None, forced=False, hearing_impaired=False,
                 format=None, label=None):
        self.url = url
        self.lang = lang            # ISO 639-1: 'cs', 'sk', 'en'
        self.lang_name = lang_name  # 'Czech', 'Slovak', 'English'
        self.provider_id = provider_id
        self.forced = forced
        self.hearing_impaired = hearing_impaired
        self.format = format        # 'srt' | 'ass' | 'vtt'
        self.label = label

    def __repr__(self):
        return '<SubtitleCandidate lang={} provider={}>'.format(
            self.lang, self.provider_id)
