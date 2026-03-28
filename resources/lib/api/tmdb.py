# -*- coding: utf-8 -*-
"""
TMDB (The Movie Database) metadata klient.

Atribuce: "This product uses the TMDB API but is not endorsed or certified by TMDB."

API key se nastavuje v settings.xml pod klíčem 'tmdb.api_key'.
Pokud uživatel nemá vlastní klíč, addon funguje bez TMDB obohacení.
"""
from __future__ import print_function, unicode_literals

import traceback

from resources.lib.common.logger import debug

TMDB_BASE = 'https://api.themoviedb.org/3'
TMDB_IMAGE_BASE = 'https://image.tmdb.org/t/p'

# Výchozí velikosti obrázků
POSTER_SIZE = 'w500'
BACKDROP_SIZE = 'w1280'
THUMB_SIZE = 'w300'


def _poster_url(path, size=POSTER_SIZE):
    if not path:
        return None
    return '{}/{}{}'.format(TMDB_IMAGE_BASE, size, path)


def _backdrop_url(path, size=BACKDROP_SIZE):
    if not path:
        return None
    return '{}/{}{}'.format(TMDB_IMAGE_BASE, size, path)


class TMDBClient:
    instance = None

    def __init__(self, api_key=None):
        self._api_key = api_key

    def _key(self):
        if self._api_key:
            return self._api_key
        try:
            from resources.lib.kodiutils import get_setting
            key = get_setting('tmdb.api_key')
            return key if key else None
        except Exception:
            return None

    def _get(self, path, params=None, lang='cs'):
        key = self._key()
        if not key:
            return None
        try:
            from resources.lib.system import Http
            p = {'api_key': key, 'language': lang}
            if params:
                p.update(params)
            resp = Http.get(TMDB_BASE + path, params=p, timeout=10)
            if resp.status_code == 200:
                return resp.json()
            debug('tmdb: HTTP {} pro {}'.format(resp.status_code, path))
        except Exception:
            debug('tmdb: error: {}'.format(traceback.format_exc()))
        return None

    # ------------------------------------------------------------------
    # Movies
    # ------------------------------------------------------------------

    def get_movie(self, tmdb_id, lang='cs'):
        """Vrátí detail filmu z TMDB."""
        return self._get('/movie/{}'.format(tmdb_id), lang=lang)

    def get_movie_by_imdb(self, imdb_id, lang='cs'):
        """Najde film přes IMDB ID."""
        data = self._get('/find/{}'.format(imdb_id),
                         params={'external_source': 'imdb_id'}, lang=lang)
        if data and data.get('movie_results'):
            return data['movie_results'][0]
        return None

    def enrich_movie(self, ids, lang='cs'):
        """
        Vrátí dict vhodný pro Kodi ListItem.setInfo() + setArt().

        Args:
            ids: MediaIds
        Returns:
            dict {'info': {...}, 'art': {...}} nebo {}
        """
        data = None
        if ids.tmdb:
            data = self.get_movie(ids.tmdb, lang=lang)
        elif ids.imdb:
            data = self.get_movie_by_imdb(ids.imdb, lang=lang)

        if not data:
            return {}

        info = {'mediatype': 'movie'}
        if data.get('title'):
            info['title'] = data['title']
        if data.get('overview'):
            info['plot'] = data['overview']
        if data.get('release_date'):
            info['year'] = int(data['release_date'][:4]) if data['release_date'] else None
        if data.get('vote_average'):
            info['rating'] = data['vote_average']
        if data.get('vote_count'):
            info['votes'] = data['vote_count']
        if data.get('runtime'):
            info['duration'] = data['runtime'] * 60
        if data.get('genres'):
            info['genre'] = [g['name'] for g in data['genres']]

        art = {}
        if data.get('poster_path'):
            art['poster'] = _poster_url(data['poster_path'])
            art['thumb'] = _poster_url(data['poster_path'], 'w342')
        if data.get('backdrop_path'):
            art['fanart'] = _backdrop_url(data['backdrop_path'])

        return {'info': info, 'art': art}

    # ------------------------------------------------------------------
    # TV Shows
    # ------------------------------------------------------------------

    def get_show(self, tmdb_id, lang='cs'):
        return self._get('/tv/{}'.format(tmdb_id), lang=lang)

    def get_show_by_imdb(self, imdb_id, lang='cs'):
        data = self._get('/find/{}'.format(imdb_id),
                         params={'external_source': 'imdb_id'}, lang=lang)
        if data and data.get('tv_results'):
            return data['tv_results'][0]
        return None

    def get_episode(self, tmdb_id, season, episode, lang='cs'):
        return self._get('/tv/{}/season/{}/episode/{}'.format(tmdb_id, season, episode),
                         lang=lang)

    def enrich_show(self, ids, lang='cs'):
        data = None
        if ids.tmdb:
            data = self.get_show(ids.tmdb, lang=lang)
        elif ids.imdb:
            data = self.get_show_by_imdb(ids.imdb, lang=lang)

        if not data:
            return {}

        info = {'mediatype': 'tvshow'}
        if data.get('name'):
            info['tvshowtitle'] = data['name']
        if data.get('overview'):
            info['plot'] = data['overview']
        if data.get('first_air_date'):
            info['year'] = int(data['first_air_date'][:4])
        if data.get('vote_average'):
            info['rating'] = data['vote_average']
        if data.get('genres'):
            info['genre'] = [g['name'] for g in data['genres']]

        art = {}
        if data.get('poster_path'):
            art['poster'] = _poster_url(data['poster_path'])
            art['thumb'] = _poster_url(data['poster_path'], 'w342')
        if data.get('backdrop_path'):
            art['fanart'] = _backdrop_url(data['backdrop_path'])

        return {'info': info, 'art': art}

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    def search_movie(self, query, year=None, lang='cs', page=1):
        params = {'query': query, 'page': page}
        if year:
            params['year'] = year
        data = self._get('/search/movie', params=params, lang=lang)
        return data.get('results', []) if data else []

    def search_show(self, query, lang='cs', page=1):
        data = self._get('/search/tv', params={'query': query, 'page': page}, lang=lang)
        return data.get('results', []) if data else []

    def is_available(self):
        """Zkontroluje, zda je nastavený API klíč."""
        return bool(self._key())


def get_tmdb():
    if TMDBClient.instance is None:
        TMDBClient.instance = TMDBClient()
    return TMDBClient.instance
