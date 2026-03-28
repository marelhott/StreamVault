# -*- coding: utf-8 -*-
"""
Library Manager – správa Kodi knihovny jako first-class feature.

Přebírá a rozšiřuje mulen library_export.py:
  - filmy (movie) i seriály (tvshow) včetně sezon
  - STRM + NFO soubory
  - automatický refresh knihovny
  - ochrana před přepisem
  - čitelné chybové zprávy

Struktura souborů:
  <movie.library.path>/
    Film (2024)/
      Film (2024).strm
      Film (2024).nfo

  <tvshow.library.path>/
    Seriál (2020)/
      tvshow.nfo
      Season 01/
        Seriál S01E01 - Pilot.strm
        Seriál S01E02 - Epizoda.strm
      Season 02/
        ...
"""
from __future__ import print_function, unicode_literals

import re
import traceback

import xbmcvfs

from resources.lib.api.sc import Sc
from resources.lib.common.logger import debug
from resources.lib.constants import SC
from resources.lib.gui.dialog import dnotify, dyesno
from resources.lib.kodiutils import (
    create_plugin_url, exec_build_in, get_setting,
    make_legal_filename, make_nfo_content, translate_path
)

INVALID_FS_CHARS = re.compile(r'[\\/:*?"<>|]+')
ADDON_NAME = 'StreamVault'


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _safe(value, fallback='item'):
    value = (value or '').strip()
    if not value:
        return fallback
    value = INVALID_FS_CHARS.sub('_', value)
    value = re.sub(r'\s+', ' ', value).strip('. ').strip()
    return value or fallback


def _join(*parts):
    cleaned = []
    for i, p in enumerate(parts):
        if not p:
            continue
        t = str(p)
        cleaned.append(t.rstrip('/\\') if i == 0 else t.strip('/\\'))
    return '/'.join(cleaned)


def _write(path, content):
    parent = path.rsplit('/', 1)[0]
    if parent:
        _ensure_dir(parent)
    f = xbmcvfs.File(path, 'w')
    try:
        f.write(content)
    finally:
        f.close()


def _ensure_dir(path):
    path = make_legal_filename(path)
    if xbmcvfs.exists(path):
        return True
    return xbmcvfs.mkdirs(path)


def _delete(path):
    path = make_legal_filename(path)
    if not xbmcvfs.exists(path):
        return True
    if xbmcvfs.delete(path):
        return True
    entries = xbmcvfs.listdir(path)
    for d in entries[0]:
        _delete(_join(path, d))
    for f in entries[1]:
        _delete(_join(path, f))
    return xbmcvfs.rmdir(path, force=True)


def _is_writable(base):
    try:
        if not _ensure_dir(base):
            return False
        probe = _join(base, '.sv_write_test.tmp')
        f = xbmcvfs.File(make_legal_filename(probe), 'w')
        try:
            f.write('ok')
        finally:
            f.close()
        xbmcvfs.delete(make_legal_filename(probe))
        return True
    except Exception:
        return False


def _setting_path(key):
    raw = get_setting(key)
    if not raw:
        return ''
    if '://' in raw:
        return raw.rstrip('/\\')
    return translate_path(raw).rstrip('/\\')


def _ids_from_args(args):
    return {k: args.get(k) for k in ('imdb', 'tmdb', 'tvdb', 'csfd') if args.get(k)}


def _should_write_nfo():
    mode = get_setting('library.metadata.mode') or '1'
    return mode != '0'


def _refresh_library():
    mode = get_setting('library.update.mode') or '1'
    if mode != '0':
        exec_build_in('UpdateLibrary(video)')


def _refresh_msg():
    mode = get_setting('library.update.mode') or '1'
    return 'Knihovna byla aktualizována.' if mode != '0' else 'Knihovna nebyla automaticky prohledána.'


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def test_movie_library_path():
    base = _setting_path('movie.library.path')
    if not base:
        dnotify(ADDON_NAME, 'Nejdřív nastav cestu pro filmovou knihovnu.')
        return False
    if not _is_writable(base):
        dnotify(ADDON_NAME, 'Filmová knihovna není zapisovatelná: {}'.format(base))
        return False
    dnotify(ADDON_NAME, 'Filmová knihovna je v pořádku: {}'.format(base))
    return True


def test_tvshow_library_path():
    base = _setting_path('tvshow.library.path')
    if not base:
        dnotify(ADDON_NAME, 'Nejdřív nastav cestu pro seriálovou knihovnu.')
        return False
    if not _is_writable(base):
        dnotify(ADDON_NAME, 'Seriálová knihovna není zapisovatelná: {}'.format(base))
        return False
    dnotify(ADDON_NAME, 'Seriálová knihovna je v pořádku: {}'.format(base))
    return True


def export_from_args(args):
    media_type = args.get('content')
    if media_type == 'movie':
        return export_movie(args)
    if media_type == 'tvshow':
        return export_tvshow(args)
    dnotify(ADDON_NAME, 'Tento typ položky ještě nejde uložit do knihovny.')
    return False


def remove_from_args(args):
    media_type = args.get('content')
    if media_type == 'movie':
        return remove_movie(args)
    if media_type == 'tvshow':
        return remove_tvshow(args)
    dnotify(ADDON_NAME, 'Tento typ položky nejde odebrat z knihovny.')
    return False


# ---------------------------------------------------------------------------
# Movie
# ---------------------------------------------------------------------------

def _movie_paths(args):
    base = _setting_path('movie.library.path')
    title = args.get('title') or args.get('name')
    year = args.get('year', '')
    folder = _safe('{} ({})'.format(title, year) if year else title, 'Movie')
    folder_path = _join(base, folder)
    return {
        'base': base,
        'folder': folder_path,
        'strm': _join(folder_path, '{}.strm'.format(folder)),
        'nfo': _join(folder_path, '{}.nfo'.format(folder)),
    }


def export_movie(args):
    p = _movie_paths(args)
    if not p['base']:
        dnotify(ADDON_NAME, 'Nejdřív nastav složku pro filmovou knihovnu.')
        return False
    if not _is_writable(p['base']):
        dnotify(ADDON_NAME, 'Do filmové knihovny se nedá zapisovat: {}'.format(p['base']))
        return False

    play_url = args.get('url')
    title = args.get('title') or args.get('name')
    if not play_url or not title:
        dnotify(ADDON_NAME, 'Chybí data pro export filmu.')
        return False

    if xbmcvfs.exists(make_legal_filename(p['folder'])):
        if not dyesno(ADDON_NAME, '{} už v knihovně existuje.\n\nPřepsat?'.format(title)):
            dnotify(title, 'Export přeskočen.')
            return False

    try:
        _delete(p['folder'])
        _ensure_dir(p['folder'])
        _write(make_legal_filename(p['strm']), create_plugin_url({'play': play_url}))

        ids = _ids_from_args(args)
        if _should_write_nfo() and ids:
            _write(make_legal_filename(p['nfo']),
                   make_nfo_content({SC.ITEM_UIDS: ids}, 'movie'))

        _refresh_library()
        dnotify(title, 'Film přidán do knihovny.\n{}'.format(p['folder']))
        dnotify(ADDON_NAME, _refresh_msg())
        return True
    except Exception:
        debug('library: export_movie error: {}'.format(traceback.format_exc()))
        dnotify(title, 'Nepodařilo se přidat film do knihovny.')
        return False


def remove_movie(args):
    p = _movie_paths(args)
    if not p['base']:
        dnotify(ADDON_NAME, 'Nejdřív nastav složku pro filmovou knihovnu.')
        return False
    if not xbmcvfs.exists(make_legal_filename(p['folder'])):
        dnotify(args.get('title', ADDON_NAME), 'Film v knihovně nebyl nalezen.')
        return False
    if not dyesno(ADDON_NAME, 'Odebrat film z knihovny?\n\n{}'.format(p['folder'])):
        return False
    if _delete(p['folder']):
        _refresh_library()
        dnotify(args.get('title', ADDON_NAME), 'Film odebrán z knihovny.')
        return True
    dnotify(args.get('title', ADDON_NAME), 'Nepodařilo se odebrat film z knihovny.')
    return False


# ---------------------------------------------------------------------------
# TV Show
# ---------------------------------------------------------------------------

def _tvshow_paths(args):
    base = _setting_path('tvshow.library.path')
    show_title = args.get('title') or args.get('tvshowtitle') or args.get('name')
    year = args.get('year', '')
    folder = _safe('{} ({})'.format(show_title, year) if year else show_title, 'TV Show')
    show_folder = _join(base, folder)
    return {
        'base': base,
        'folder': show_folder,
        'nfo': _join(show_folder, 'tvshow.nfo'),
    }


def export_tvshow(args):
    p = _tvshow_paths(args)
    if not p['base']:
        dnotify(ADDON_NAME, 'Nejdřív nastav složku pro seriálovou knihovnu.')
        return False
    if not _is_writable(p['base']):
        dnotify(ADDON_NAME, 'Do seriálové knihovny se nedá zapisovat: {}'.format(p['base']))
        return False

    show_url = args.get('url')
    show_title = args.get('title') or args.get('tvshowtitle') or args.get('name')
    if not show_url or not show_title:
        dnotify(ADDON_NAME, 'Chybí data pro export seriálu.')
        return False

    if xbmcvfs.exists(make_legal_filename(p['folder'])):
        if not dyesno(ADDON_NAME, '{} už v knihovně existuje.\n\nPřepsat?'.format(show_title)):
            dnotify(show_title, 'Export přeskočen.')
            return False

    try:
        episodes = _collect_episodes(show_url)
        if not episodes:
            dnotify(show_title, 'Nepodařilo se načíst epizody seriálu.')
            return False

        _delete(p['folder'])
        _ensure_dir(p['folder'])

        ids = _ids_from_args(args)
        if _should_write_nfo() and ids:
            _write(make_legal_filename(p['nfo']),
                   make_nfo_content({SC.ITEM_UIDS: ids}, 'tvshow'))

        safe_title = _safe(show_title, 'TV Show')
        written = 0
        for ep in episodes:
            info = ep.get(SC.ITEM_INFO, {})
            season = info.get('season')
            ep_num = info.get('episode')
            ep_url = ep.get(SC.ITEM_URL)
            ep_title = _safe(info.get('title') or '', '')

            if season in (None, '') or ep_num in (None, '') or not ep_url:
                continue

            s = int(season)
            e = int(ep_num)
            season_folder = _join(p['folder'], 'Season {:02d}'.format(s))
            _ensure_dir(season_folder)

            base_name = '{} S{:02d}E{:02d}'.format(safe_title, s, e)
            if ep_title:
                base_name = '{} - {}'.format(base_name, ep_title)

            _write(make_legal_filename(_join(season_folder, '{}.strm'.format(base_name))),
                   create_plugin_url({'play': ep_url}))
            written += 1

        if written == 0:
            dnotify(show_title, 'Nebyly nalezeny žádné exportovatelné epizody.')
            return False

        _refresh_library()
        dnotify(show_title, 'Seriál přidán do knihovny ({} epizod).\n{}'.format(
            written, p['folder']))
        dnotify(ADDON_NAME, _refresh_msg())
        return True

    except Exception:
        debug('library: export_tvshow error: {}'.format(traceback.format_exc()))
        dnotify(show_title, 'Nepodařilo se přidat seriál do knihovny.')
        return False


def remove_tvshow(args):
    p = _tvshow_paths(args)
    if not p['base']:
        dnotify(ADDON_NAME, 'Nejdřív nastav složku pro seriálovou knihovnu.')
        return False
    title = args.get('title') or args.get('tvshowtitle') or ADDON_NAME
    if not xbmcvfs.exists(make_legal_filename(p['folder'])):
        dnotify(title, 'Seriál v knihovně nebyl nalezen.')
        return False
    if not dyesno(ADDON_NAME, 'Odebrat seriál z knihovny?\n\n{}'.format(p['folder'])):
        return False
    if _delete(p['folder']):
        _refresh_library()
        dnotify(title, 'Seriál odebrán z knihovny.')
        return True
    dnotify(title, 'Nepodařilo se odebrat seriál z knihovny.')
    return False


# ---------------------------------------------------------------------------
# Episode collection (rekurzivní načtení přes SC API)
# ---------------------------------------------------------------------------

def _collect_episodes(show_url):
    response = Sc.get(show_url)
    if not isinstance(response, dict):
        return []

    episodes = []
    for item in response.get(SC.ITEM_MENU, []):
        info = item.get(SC.ITEM_INFO, {})
        media_type = info.get('mediatype')

        if media_type == 'episode':
            episodes.append(item)
            continue

        season_url = item.get(SC.ITEM_URL)
        if media_type != 'season' or not season_url:
            continue

        season_resp = Sc.get(season_url)
        if not isinstance(season_resp, dict):
            continue

        for ep in season_resp.get(SC.ITEM_MENU, []):
            if ep.get(SC.ITEM_INFO, {}).get('mediatype') == 'episode':
                episodes.append(ep)

    return episodes
