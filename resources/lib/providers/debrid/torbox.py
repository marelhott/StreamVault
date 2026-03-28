# -*- coding: utf-8 -*-
"""TorBox API klient."""
from __future__ import print_function, unicode_literals
import traceback
from resources.lib.common.logger import debug

TB_BASE = 'https://api.torbox.app/v1/api'


class TorBoxClient:
    def __init__(self, api_key):
        self._key = api_key

    def _headers(self):
        return {'Authorization': 'Bearer {}'.format(self._key)}

    def _get(self, path, params=None):
        from resources.lib.system import Http
        resp = Http.get(TB_BASE + path, headers=self._headers(), params=params, timeout=15)
        if resp.status_code == 200:
            return resp.json()
        debug('tb: GET {} → {}'.format(path, resp.status_code))
        return None

    def _post(self, path, data=None, json=None):
        from resources.lib.system import Http
        resp = Http.post(TB_BASE + path, headers=self._headers(), data=data, json=json, timeout=15)
        if resp.status_code in (200, 201):
            return resp.json()
        debug('tb: POST {} → {}'.format(path, resp.status_code))
        return None

    def check_cache(self, hashes):
        """Zkontroluje cache přes TorBox API."""
        cached = set()
        try:
            for h in hashes:
                result = self._get('/torrents/checkcached', params={'hash': h, 'format': 'object'})
                if result and result.get('data', {}).get(h.lower()):
                    cached.add(h.lower())
        except Exception:
            debug('tb: check_cache error: {}'.format(traceback.format_exc()))
        return cached

    def resolve_torrent(self, info_hash, file_idx=None):
        debug('tb: resolve_torrent hash={}'.format(info_hash))
        try:
            magnet = 'magnet:?xt=urn:btih:{}'.format(info_hash)
            result = self._post('/torrents/createtorrent', data={'magnet': magnet})
            if not result or not result.get('data'):
                return None

            torrent_id = result['data'].get('torrent_id')
            if not torrent_id:
                return None

            # Získej download link
            import time
            for _ in range(10):
                info = self._get('/torrents/mylist', params={'id': torrent_id})
                if not info:
                    break
                torrent_data = info.get('data')
                if not torrent_data:
                    break
                if isinstance(torrent_data, list):
                    torrent_data = torrent_data[0] if torrent_data else None
                if not torrent_data:
                    break

                if torrent_data.get('download_finished'):
                    files = torrent_data.get('files', [])
                    if not files:
                        return None
                    file_data = files[file_idx] if file_idx is not None and file_idx < len(files) else files[0]
                    file_id = file_data.get('id')

                    link_result = self._get('/torrents/requestdl', params={
                        'token': self._key,
                        'torrent_id': torrent_id,
                        'file_id': file_id,
                        'zip_link': 'false',
                    })
                    if link_result and link_result.get('data'):
                        return link_result['data']
                    return None

                time.sleep(2)

        except Exception:
            debug('tb: resolve_torrent error: {}'.format(traceback.format_exc()))
        return None

    def unrestrict_link(self, link):
        """TorBox nepodporuje hoster unrestrict stejným způsobem."""
        return link
