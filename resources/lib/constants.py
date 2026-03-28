# -*- coding: utf-8 -*-
from __future__ import print_function, unicode_literals

import sys
import xbmcplugin
import xbmcaddon

python_version = sys.version_info[0]
PY2 = python_version == 2
PY3 = python_version == 3

try:
    HANDLE = int(sys.argv[1])
except Exception:
    HANDLE = -1

ADDON_ID = 'plugin.video.streamvault'
ADDON = xbmcaddon.Addon(id=ADDON_ID)

# Stream Cinema catalog API
SC_BASE_URL = 'https://stream-cinema.online/kodi'
SC_API_VERSION = '2.0'

# Backwards-compat aliases (used by update_service.py and others)
BASE_URL = SC_BASE_URL
API_VERSION = SC_API_VERSION

# Cache switches
CACHE_ENABLED = True
CACHE_API_ENABLED = True
CACHE_STATIC_MENU_ENABLED = True
CACHE_MENU_ENABLED = True

# Provider IDs
PROVIDER_KRASKA = 'kraska'
PROVIDER_WEBSHARE = 'webshare'
PROVIDER_TORRENTIO = 'torrentio'

# Debrid service IDs
DEBRID_REALDEBRID = 'realdebrid'
DEBRID_ALLDEBRID = 'alldebrid'
DEBRID_PREMIUMIZE = 'premiumize'
DEBRID_TORBOX = 'torbox'


class GUI:
    BOTTOM = 'bottom'
    TOP = 'top'


class SC:
    """Stream Cinema API constants – zachováváme kompatibilitu s SC API odpověďmi."""
    ACTION = 'action'
    ACTION_PLAY_URL = 'playUrl'
    ACTION_SELECT_STREAM = 'selectStream'
    ACTION_ADD_TO_LIBRARY = 'add_to_library'
    ACTION_REMOVE_FROM_LIBRARY = 'remove_from_library'
    ACTION_TEST_MOVIE_LIBRARY_PATH = 'test_movie_library_path'
    ACTION_TEST_TVSHOW_LIBRARY_PATH = 'test_tvshow_library_path'
    ACTION_CMD = 'cmd'
    ACTION_PIN = 'pin'
    ACTION_CSEARCH = 'csearch'
    ACTION_LAST = 'last'
    ACTION_FILTER = 'filter'
    ACTION_DEBUG = 'debug'
    ACTION_BUFFER = 'buffer'
    ACTION_ANDROID = 'android'
    ACTION_DOWNLOAD = 'down'
    ACTION_ADD2HP = 'add2hp'
    ACTION_DEL2HP = 'del2hp'
    ACTION_HIDE_HP_ITEM = 'hide_hp_item'
    ACTION_RESET_HIDDEN = 'reset_hidden'
    ACTION_SET_PREFERRED_LANGUAGE = 'set_preferred_language'
    ACTION_DEL_PREFERRED_LANGUAGE = 'sel_preferred_language'
    ACTION_ADD_CUSTOM_FILTER = 'add_custom_filter'
    ACTION_DEL_CUSTOM_FILTER = 'del_custom_filter'
    ACTION_LOAD_SAVED_FILTER = 'load_saved_filter'
    ACTION_DELETE_SAVED_FILTER = 'delete_saved_filter'
    ACTION_EDIT_SAVED_FILTER = 'edit_saved_filter'
    ACTION_RENAME_SAVED_FILTER = 'rename_saved_filter'
    ACTION_REMOVE_FROM_LIST = 'remove_from_list'
    ACTION_UPDATE_ADDON = 'update_addon'
    # Playback pipeline actions
    ACTION_PLAY_INTERNATIONAL = 'play_international'

    CMD = 'cmd'
    DEFAULT_LANG = 'cs'

    ITEM_ACTION = 'action'
    ITEM_ART = 'art'
    ITEM_AUDIO_INFO = 'ainfo'
    ITEM_BITRATE = 'bitrate'
    ITEM_CMD = 'cmd'
    ITEM_CUSTOM_FILTER = 'custom'
    ITEM_SAVED_FILTER = 'saved_filter'
    ITEM_DIR = 'dir'
    ITEM_DOWNLOAD = 'down'
    ITEM_FOCUS = 'focus'
    ITEM_HPDIR = 'hpdir'
    ITEM_I18N_ART = 'i18n_art'
    ITEM_I18N_INFO = 'i18n_info'
    ITEM_ID = 'id'
    ITEM_IDENT = 'ident'
    ITEM_INFO = 'info'
    ITEM_LIBRARY = 'library'
    ITEM_LIBRARY_SUB = 'library_sub'
    ITEM_LANG = 'lang'
    ITEM_MENU = 'menu'
    ITEM_NEXT = 'next'
    ITEM_PAGE = 'page'
    ITEM_PREFERRED_LANG = 'pref_lang.{}'
    ITEM_PROVIDER = 'provider'
    ITEM_QUALITY = 'quality'
    ITEM_SIZE = 'size'
    ITEM_STRMS = 'strms'
    ITEM_SUBS = 'subs'
    ITEM_SYSTEM = 'system'
    ITEM_TITLE = 'title'
    ITEM_TYPE = 'type'
    ITEM_URL = 'url'
    ITEM_UIDS = 'unique_ids'
    ITEM_VIDEO = 'video'
    ITEM_VIDEO_INFO = 'vinfo'
    ITEM_VISIBLE = 'visible'
    ITEM_WIDGET = 'widget'

    MEDIA_TYPE = 'mediatype'
    MEDIA_TYPE_AUDIO = 'audio'
    MEDIA_TYPE_EPISODE = 'episode'
    MEDIA_TYPE_FILE = 'file'
    MEDIA_TYPE_SEASON = 'season'
    MEDIA_TYPE_TV_SHOW = 'tvshow'
    MEDIA_TYPE_VIDEO = 'video'

    NEXT = 'next'
    NEXT_EP_TIME_NOTIFICATION = 'next_ep_notify'
    NOTIFICATIONS = 'notifications'
    NOTIFICATIONS_PROPS = 'SV:NOTIFICATIONS'
    PROVIDER = 'kraska'
    RUN_PLUGIN = 'RunPlugin({})'
    SELECTED_ITEM = 'SV:selected'
    STREAM_FILTER_PREFS = 'SV:stream_filter_prefs'
    SKIP_END = 'skip_end'
    SKIP_END_TITLES = 'skip_end_titles'
    SKIP_START = 'skip_start'
    TXT_PINNED = 'p-{}'
    TXT_CUSTOM_FORMAT = 'custom-{}'
    BCK_FILE = 'sv.json'


class HTTP:
    TIMEOUT = 10
    GET = 'get'
    POST = 'post'
    HEAD = 'head'
    OPTION = 'option'
    PUT = 'put'
    DELETE = 'delete'
    PATCH = 'patch'


class KodiDbMap:
    """Mapování Kodi DB polí pro ukládání watched stavu."""
    MOVIE = 'movie'
    EPISODE = 'episode'
    TVSHOW = 'tvshow'
    SEASON = 'season'
    MUSICVIDEO = 'musicvideo'

    # Pole v Kodi video DB
    FIELD_PLAY_COUNT = 'playcount'
    FIELD_LAST_PLAYED = 'lastplayed'
    FIELD_RESUME = 'resume'
    FIELD_BOOKMARK = 'bookmark'


SORT_METHODS = {
    14: xbmcplugin.SORT_METHOD_ALBUM,
    15: xbmcplugin.SORT_METHOD_ALBUM_IGNORE_THE,
    11: xbmcplugin.SORT_METHOD_ARTIST,
    13: xbmcplugin.SORT_METHOD_ARTIST_IGNORE_THE,
    42: xbmcplugin.SORT_METHOD_BITRATE,
    3: xbmcplugin.SORT_METHOD_DATE,
    21: xbmcplugin.SORT_METHOD_DATEADDED,
    8: xbmcplugin.SORT_METHOD_DURATION,
    24: xbmcplugin.SORT_METHOD_EPISODE,
    5: xbmcplugin.SORT_METHOD_FILE,
    16: xbmcplugin.SORT_METHOD_GENRE,
    1: xbmcplugin.SORT_METHOD_LABEL,
    2: xbmcplugin.SORT_METHOD_LABEL_IGNORE_THE,
    36: xbmcplugin.SORT_METHOD_LASTPLAYED,
    0: xbmcplugin.SORT_METHOD_NONE,
    37: xbmcplugin.SORT_METHOD_PLAYCOUNT,
    4: xbmcplugin.SORT_METHOD_SIZE,
    9: xbmcplugin.SORT_METHOD_TITLE,
    10: xbmcplugin.SORT_METHOD_TITLE_IGNORE_THE,
    39: xbmcplugin.SORT_METHOD_UNSORTED,
    19: xbmcplugin.SORT_METHOD_VIDEO_RATING,
    31: xbmcplugin.SORT_METHOD_VIDEO_RUNTIME,
    25: xbmcplugin.SORT_METHOD_VIDEO_TITLE,
    20: xbmcplugin.SORT_METHOD_VIDEO_USER_RATING,
    18: xbmcplugin.SORT_METHOD_VIDEO_YEAR,
}

if PY2:
    SORT_METHODS_INVERT = {v: k for k, v in SORT_METHODS.iteritems()}
else:
    SORT_METHODS_INVERT = {v: k for k, v in SORT_METHODS.items()}
