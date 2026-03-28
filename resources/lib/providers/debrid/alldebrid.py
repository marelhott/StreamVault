# -*- coding: utf-8 -*-
"""AllDebrid API klient. Cache check stále funkční (na rozdíl od RD)."""
from __future__ import print_function, unicode_literals
import traceback
from resources.lib.common.logger import debug

AD_BASE = 'https://api.alldebrid.com/v4'
AGENT = 'StreamVault'


class AllDebridClient:
    def __init__(self, api_key):
        self._key = api_key

    def _headers(self):
        return {'Authorization': 'Bearer {}'.format(self._key)}

    def _get(self, path, params=None):
        from resources.lib.system import Http
        p = {'agent': AGENT}
        if params:
            p.update(params)
        resp = Http.get(AD_BASE + path, headers=self._headers(), params=p, timeout=15)
        if resp.status_code == 200:
            return resp.json()
        debug('ad: GET {} → {}'.format(path, resp.status_code))
        return None

    def _post(self, path, data=None):
        from resources.lib.system import Http
        p = {'agent': AGENT}
        resp = Http.post(AD_BASE + path, headers=self._headers(), params=p, data=data, timeout=15)
        if resp.status_code == 200:
            return resp.json()
        debug('ad: POST {} → {}'.format(path, resp.status_code))
        return None

    def check_cache(self, hashes):
        """Vrátí set hashů, které jsou cachované na AllDebrid."""
        debug('ad: check_cache pro {} hashů'.format(len(hashes)))
        cached = set()
        try:
            params = [('magnets[]', h) for h in hashes]
            from resources.lib.system import Http
            resp = Http.get(AD_BASE + '/magnet/instant',
                            headers=self._headers(),
                            params=[('agent', AGENT)] + params,
                            timeout=15)
            if resp.status_code != 200:
                return cached
            data = resp.json()
            for magnet in data.get('data', {}).get('magnets', []):
                if magnet.get('instant'):
                    cached.add(magnet.get('hash', '').lower())
        except Exception:
            debug('ad: check_cache error: {}'.format(traceback.format_exc()))
        debug('ad: cachováno {} / {} hashů'.format(len(cached), len(hashes)))
        return cached

    def resolve_torrent(self, info_hash, file_idx=None):
        debug('ad: resolve_torrent hash={}'.format(info_hash))
        try:
            magnet = 'magnet:?xt=urn:btih:{}'.format(info_hash)
            result = self._post('/magnet/upload', data={'magnets[]': magnet})
            if not result:
                return None

            magnets = result.get('data', {}).get('magnets', [])
            if not magnets:
                debug('ad: upload magnet selhalo')
                return None

            magnet_id = magnets[0].get('id')
            if not magnet_id:
                debug('ad: chybí magnet ID')
                return None

            # Zkontroluj status
            import time
            for _ in range(10):
                status_data = self._get('/magnet/status', params={'id': magnet_id})
                if not status_data:
                    break
                magnets_status = status_data.get('data', {}).get('magnets', {})
                status_code = magnets_status.get('statusCode', 0)
                debug('ad: magnet statusCode={}'.format(status_code))
                if status_code == 4:  # ready
                    links = magnets_status.get('links', [])
                    if not links:
                        return None
                    link_data = links[file_idx] if file_idx is not None and file_idx < len(links) else links[0]
                    link_url = link_data.get('link') if isinstance(link_data, dict) else link_data
                    return self.unrestrict_link(link_url)
                if status_code in (5, 6, 7):  # error states
                    debug('ad: magnet v chybovém stavu: {}'.format(status_code))
                    return None
                time.sleep(2)

            debug('ad: timeout čekání na magnet')
            return None

        except Exception:
            debug('ad: resolve_torrent error: {}'.format(traceback.format_exc()))
            return None

    def unrestrict_link(self, link):
        try:
            result = self._post('/link/unlock', data={'link': link})
            if result and result.get('data', {}).get('link'):
                url = result['data']['link']
                debug('ad: unrestricted URL={}'.format(url))
                return url
        except Exception:
            debug('ad: unrestrict error: {}'.format(traceback.format_exc()))
        return None
