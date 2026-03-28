# -*- coding: utf-8 -*-

from __future__ import print_function, unicode_literals

import datetime
import json
import time
import traceback

from resources.lib.common.cache import SimpleCache, use_cache
from resources.lib.common.logger import debug, info
from resources.lib.constants import SC_BASE_URL as BASE_URL, SC_API_VERSION as API_VERSION, SC, ADDON, CACHE_ENABLED, CACHE_API_ENABLED, CACHE_STATIC_MENU_ENABLED
from resources.lib.kodiutils import get_uuid, get_setting_as_bool, get_setting_as_int, get_setting, \
    file_put_contents, translate_path, file_exists, file_get_contents, set_setting
from resources.lib.system import user_agent, Http
from resources.lib.gui_cache import get_language_code, get_skin_name

try:
    # Python 3
    from urllib.parse import urlparse, parse_qs
except ImportError:
    # Python 2
    from urlparse import urlparse, parse_qs


class Sc:
    RATING_MAP = {
        "0": 0,
        "1": 6,
        "2": 12,
        "3": 15,
        "4": 18,
    }

    cache = SimpleCache()
    static_cache = {}
    static_cache_type = None

    @staticmethod
    def get(path, params=None, ttl=None):
        Sc.load_static_cache()

        if path in Sc.static_cache:
            ret = Sc.static_cache.get(path, None)
            if ret is not None:
                debug("{} je zo static cache".format(path))
                return ret

        sorted_values, url = Sc.prepare(params, path)
        key = '{}{}{}'.format(ADDON.getAddonInfo('version'), url, sorted_values)
        debug('CALL {} PARAMS {} KEY {}'.format(url, sorted_values, key))
        start = time.time()

        # Pre /IP endpoint nepoužívame cache
        # CACHE_ENABLED a CACHE_API_ENABLED z constants.py umožňujú vypnúť cache globálne
        use_cache_for_endpoint = path != '/IP'
        use_cache = use_cache_for_endpoint and CACHE_ENABLED and CACHE_API_ENABLED

        ret = None
        if use_cache:
            ret = Sc.cache.get(key)

        if ret is None:
            start = time.time()
            res = Http.get(url, headers=Sc.headers(), params=sorted_values)
            end = time.time()
            res.raise_for_status()
            try:
                ret = res.json()
                # Uložíme do cache len ak je povolená
                if use_cache:
                    Sc.save_cache(ret, key, ttl)
                elif not use_cache_for_endpoint:
                    debug('Skipping cache for /IP endpoint')
                elif not (CACHE_ENABLED and CACHE_API_ENABLED):
                    debug('API cache disabled by config (CACHE_ENABLED={}, CACHE_API_ENABLED={})'.format(CACHE_ENABLED, CACHE_API_ENABLED))
            except:
                debug('ERR JSON: {}'.format(traceback.format_exc()))
        else:
            debug('GET from cache'.format())
            end = time.time()

        debug('GET took {0:.2f}ms'.format((end - start) * 1000))
        return ret

    @staticmethod
    def prepare(params, path):
        url = BASE_URL + path
        o = urlparse(url)
        query = parse_qs(o.query)  # Returns dict with list values: {'key': ['value']}
        url = o._replace(query=None).geturl()
        p = Sc.default_params(query)
        # debug('p: {}'.format(p))
        query.update(p)
        if params is not None:
            query.update(params)

        # Convert dict to list of tuples, handling list values for PHP array syntax
        # Tieto parametre MUSIA byť vždy ako pole (aj pre single value)
        ALWAYS_ARRAY_PARAMS = ['co', 'ca', 'ge', 'mu']

        sorted_values = []
        for key, value in sorted(query.items(), key=lambda val: val[0]):
            if isinstance(value, list):
                # List hodnoty - rozlíšime či je to skutočný array (dĺžka > 1) alebo skalár z parse_qs
                if len(value) > 1 or key in ALWAYS_ARRAY_PARAMS:
                    # Skutočný PHP array alebo forced array - pridaj [] suffix pre každý item
                    for item in value:
                        sorted_values.append((key + '[]', item))
                elif len(value) == 1:
                    # parse_qs single value - pridaj ako skalár BEZ []
                    sorted_values.append((key, value[0]))
                # else: prázdny list, preskočíme
            else:
                # Skalárna hodnota priamo z params dictu (nie z parse_qs)
                # Ak je to forced array parameter, prekonvertuj na array syntax
                if key in ALWAYS_ARRAY_PARAMS:
                    sorted_values.append((key + '[]', value))
                else:
                    sorted_values.append((key, value))

        # debug('sorted: {}'.format(sorted_values))
        return sorted_values, url

    @staticmethod
    def post(path, **kwargs):
        sorted_values, url = Sc.prepare(path=path, params={})
        start = time.time()
        res = Http.post(url, params=sorted_values, headers=Sc.headers(), **kwargs)
        end = time.time()
        debug('POST took {0:.2f}ms'.format((end - start) * 1000))
        return res.json()

    @staticmethod
    def default_params(query):
        params = {
            'ver': API_VERSION,
            'uid': get_uuid(),
            'skin': get_skin_name(),
            'lang': get_language_code(),
        }
        # plugin_url = 'plugin://{}/{}'.format(ADDON_ID, query.params.orig_args if query.params.orig_args else '')
        # try:
        #     kv = KodiViewModeDb()
        #     sort = kv.get_sort(plugin_url)
        # except:
        #     sort = (0, 1)
        # try:
        #     if sort is not None:
        #         params.update({'sm': '{},{}'.format(sort[0], sort[1])})
        # except:
        #     debug('ERR API SORT: {}'.format(traceback.format_exc()))
        #     pass
        parental_control = Sc.parental_control_is_active()
        if get_setting_as_bool('stream.dubed') or (parental_control and get_setting_as_bool('parental.control.dubed')):
            params.update({'dub': 1})

        if not parental_control and get_setting_as_bool('stream.dubed.titles'):
            params.update({'dub': 1, "tit": 1})

        if parental_control:
            params.update({"m": Sc.RATING_MAP.get(get_setting('parental.control.rating'))})

        if get_setting_as_bool('plugin.show.genre'):
            params.update({'gen': 1})

        if 'HDR' not in query:
            params.update({'HDR': 0 if get_setting_as_bool('stream.exclude.hdr') else 1})

        if 'DV' not in query:
            params.update({'DV': 0 if get_setting_as_bool('stream.exclude.dolbyvision') else 1})

        if get_setting_as_bool('plugin.show.old.menu'):
            params.update({'old': 1})

        return params

    @staticmethod
    def parental_control_is_active():
        now = datetime.datetime.now()
        hour_start = get_setting_as_int('parental.control.start')
        hour_now = now.hour
        hour_end = get_setting_as_int('parental.control.end')
        return get_setting_as_bool('parental.control.enabled') and hour_start <= hour_now <= hour_end

    @staticmethod
    def headers(token=True):
        headers = {
            'User-Agent': user_agent(),
            'X-Uuid': get_uuid(),
        }
        if token:
            headers['X-AUTH-TOKEN'] = Sc.get_auth_token()
        return headers

    @staticmethod
    def get_auth_token(force = False):
        token = ''
        if force is False:
            token = get_setting('system.auth_token')

        if token == '' or token is None or token == 'None' or token is False:
            from resources.lib.api.kraska import getKraInstance

            kr = getKraInstance()
            if kr.get_token():
                found = kr.list_files(filter=SC.BCK_FILE)
                if found and len(found.get('data', [])) == 1:
                    for f in found.get('data', []):
                        try:
                            url = kr.resolve(f.get('ident'), server='b01')
                            data = Http.get(url)
                            if len(data.text) == 32:
                                token = data.text
                                set_setting('system.auth_token', token)
                                debug('get auth token from backup file: [MASKED]')
                                return token
                        except Exception as e:
                            debug('error get auth token: {}'.format(traceback.format_exc()))
                            raise Exception('error get auth token: {}'.format(e))
                else:
                    debug('backup file not found {}'.format(SC.BCK_FILE))

                path = '/auth/token?krt={}'.format(kr.get_token())
                sorted_values, url = Sc.prepare(path=path, params={})

                res = Http.post(url, params=sorted_values, headers=Sc.headers(False))
                res.raise_for_status()
                ret = res.json()
                debug('get auth token: response received')

                if 'error' in ret:
                    debug('error get auth token: {}'.format(ret.get('error', '?')))
                    return None
                if 'token' not in ret:
                    debug('error get auth token: token key missing in response')
                    return None
                token = ret['token']
                set_setting('system.auth_token', token)
                set_setting('system.auth_token_updated', ADDON.getAddonInfo('version'))  # Označíme verziou doplnku
                try:
                    kr.upload(token, SC.BCK_FILE)
                except Exception as e:
                    pass
            else:
                set_setting('system.auth_token', '')
        else:
            debug('auth token from settings {}'.format(token))
            
            # Skontrolujeme, či treba poslať update pre starý token
            from resources.lib.api.kraska import getKraInstance
            kr = getKraInstance()
            
            # Ak máme KR token a auth token nebol ešte aktualizovaný pre túto verziu
            current_version = ADDON.getAddonInfo('version')
            updated_version = get_setting('system.auth_token_updated')
            
            if kr.get_token() and updated_version != current_version:
                try:
                    debug('Sending auth token update for existing token (version: {} -> {})'.format(updated_version, current_version))
                    path = '/auth/token/update?krt={}&token={}'.format(kr.get_token(), token)
                    sorted_values, url = Sc.prepare(path=path, params={})
                    
                    res = Http.post(url, params=sorted_values, headers=Sc.headers(False))
                    res.raise_for_status()
                    ret = res.json()
                    debug('auth token update response: {}'.format(ret))
                    
                    # Označíme ako aktualizované pre túto verziu
                    set_setting('system.auth_token_updated', current_version)
                    
                except Exception as e:
                    debug('error updating auth token: {}'.format(e))
                    # Aj pri chybe označíme ako aktualizované pre túto verziu
                    set_setting('system.auth_token_updated', current_version)
                    
        return token

    @staticmethod
    def up_next(id, s, e):
        url = '/upNext/{}/{}/{}'.format(id, s, e)
        try:
            data = Sc.get(url, ttl=3600)
        except Exception:
            data = {'error': 'error'}
        return data

    @staticmethod
    def save_cache(ret, key, ttl=None):
        ttl = 3600 if ttl is None else ttl

        if SC.ITEM_SYSTEM in ret and 'TTL' in ret[SC.ITEM_SYSTEM]:
            ttl = int(ret[SC.ITEM_SYSTEM]['TTL'])

        debug('SAVE TO CACHE {} / {}'.format(ttl, key))
        Sc.cache.set(key, ret, expiration=datetime.timedelta(seconds=ttl))

    @staticmethod
    def static_cache_local_name():
        dpath = ADDON.getAddonInfo('profile')
        return translate_path("{}/{}".format(dpath, Sc.static_cache_filename()))

    @staticmethod
    def static_cache_filename():
        old = 1 if get_setting_as_bool('plugin.show.old.menu') else 0

        return 'menu.{}.json'.format(old)

    @staticmethod
    def download_menu():
        """Stiahne static menu cache z API"""
        try:
            url = "{}/../{}".format(BASE_URL, Sc.static_cache_filename())
            info('download menu cache {}'.format(url))
            resp = Http.get(url)
            resp.raise_for_status()

            # Parse JSON
            menu_data = resp.json()

            # Ulož lokálne
            dfile = Sc.static_cache_local_name()
            file_put_contents(dfile, resp.content)

            debug('Static menu downloaded: {} bytes'.format(len(resp.content)))

            # Načítaj do cache
            Sc.load_static_cache(True)

            return menu_data
        except Exception as e:
            debug('error download menu: {}'.format(traceback.format_exc()))
            return None

    @staticmethod
    def download_menu_bg():
        from threading import Thread
        worker = Thread(target=Sc.download_menu)
        worker.start()

    @staticmethod
    def load_static_cache(force=False):
        """Načíta static cache zo súboru"""
        try:
            # Ak je cache zakázaná, preskočiť
            if not (CACHE_ENABLED and CACHE_STATIC_MENU_ENABLED):
                debug('Static menu cache disabled by config (CACHE_ENABLED={}, CACHE_STATIC_MENU_ENABLED={})'.format(CACHE_ENABLED, CACHE_STATIC_MENU_ENABLED))
                Sc.static_cache = {}
                return

            # Ak už je načítaný a force nie je True, skip
            if Sc.static_cache != {} and not force:
                debug('uz mame static cache {} == {}'.format(Sc.static_cache_type, Sc.static_cache_filename()))
                return

            cache_file = Sc.static_cache_local_name()
            if file_exists(cache_file):
                debug('Natahujeme static cache zo suboru {}'.format(cache_file))
                content = file_get_contents(cache_file)

                # Skontroluj, či obsah nie je prázdny
                if not content or len(content.strip()) == 0:
                    debug('Static cache file je prazdny, vymazavam a nastavujem prazdny cache')
                    import os
                    try:
                        os.remove(cache_file)
                        debug('Vymazany prazdny cache file: {}'.format(cache_file))
                    except:
                        pass
                    Sc.static_cache = {}
                    return

                # Parsuj JSON
                Sc.static_cache = json.loads(content)
                Sc.static_cache_type = Sc.static_cache_filename()
                debug('Static cache loaded: {} paths'.format(len(Sc.static_cache)))
            else:
                debug('Static cache file neexistuje: {}'.format(cache_file))
                Sc.static_cache = {}
        except json.JSONDecodeError as e:
            # JSON parse error - poškodený súbor
            debug('Static cache file je poskodeny (JSON error): {}'.format(e))
            Sc.static_cache = {}
            # Vymaž poškodený súbor
            import os
            try:
                if file_exists(cache_file):
                    os.remove(cache_file)
                    debug('Vymazany poskodeny cache file: {}'.format(cache_file))
            except:
                pass
        except Exception as e:
            Sc.static_cache = {}
            debug('error load static menu: {}'.format(traceback.format_exc()))
