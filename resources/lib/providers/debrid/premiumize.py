# -*- coding: utf-8 -*-
"""Premiumize API klient. Cache check stále funkční."""
from __future__ import print_function, unicode_literals
import traceback
from resources.lib.common.logger import debug

PM_BASE = 'https://www.premiumize.me/api'


class PremiumizeClient:
    def __init__(self, api_key):
        self._key = api_key

    def _headers(self):
        return {'Authorization': 'Bearer {}'.format(self._key)}

    def _post(self, path, data=None):
        from resources.lib.system import Http
        resp = Http.post(PM_BASE + path, headers=self._headers(), data=data, timeout=15)
        if resp.status_code == 200:
            return resp.json()
        debug('pm: POST {} → {}'.format(path, resp.status_code))
        return None

    def check_cache(self, hashes):
        """Cache check – nepočítá do fair-use kvóty."""
        debug('pm: check_cache pro {} hashů'.format(len(hashes)))
        cached = set()
        try:
            items = ['magnet:?xt=urn:btih:{}'.format(h) for h in hashes]
            # Premiumize akceptuje max 100 položek
            for i in range(0, len(items), 100):
                chunk = items[i:i+100]
                data = [('items[]', item) for item in chunk]
                from resources.lib.system import Http
                resp = Http.post(PM_BASE + '/cache/check',
                                 headers=self._headers(),
                                 data=data,
                                 timeout=15)
                if resp.status_code != 200:
                    continue
                result = resp.json()
                responses = result.get('response', [])
                for idx, is_cached in enumerate(responses):
                    if is_cached and idx < len(chunk):
                        h = hashes[i + idx] if (i + idx) < len(hashes) else None
                        if h:
                            cached.add(h.lower())
        except Exception:
            debug('pm: check_cache error: {}'.format(traceback.format_exc()))
        debug('pm: cachováno {} hashů'.format(len(cached)))
        return cached

    def resolve_torrent(self, info_hash, file_idx=None):
        debug('pm: resolve_torrent hash={}'.format(info_hash))
        try:
            magnet = 'magnet:?xt=urn:btih:{}'.format(info_hash)
            result = self._post('/transfer/directdl', data={'src': magnet})
            if result and result.get('status') == 'success':
                content = result.get('content', [])
                if not content:
                    debug('pm: prázdný content')
                    return None
                item = content[file_idx] if file_idx is not None and file_idx < len(content) else content[0]
                url = item.get('stream_link') or item.get('link')
                debug('pm: resolved URL={}'.format(url))
                return url
            debug('pm: directdl selhalo: {}'.format(result))
        except Exception:
            debug('pm: resolve_torrent error: {}'.format(traceback.format_exc()))
        return None

    def unrestrict_link(self, link):
        try:
            result = self._post('/transfer/directdl', data={'src': link})
            if result and result.get('status') == 'success':
                content = result.get('content', [])
                if content:
                    url = content[0].get('stream_link') or content[0].get('link')
                    return url
        except Exception:
            debug('pm: unrestrict error: {}'.format(traceback.format_exc()))
        return None
