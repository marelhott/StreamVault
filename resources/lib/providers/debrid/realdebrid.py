# -*- coding: utf-8 -*-
"""Real-Debrid API klient."""
from __future__ import print_function, unicode_literals
import traceback
from resources.lib.common.logger import debug

RD_BASE = 'https://api.real-debrid.com/rest/1.0'


class RealDebridClient:
    def __init__(self, api_key):
        self._key = api_key

    def _headers(self):
        return {'Authorization': 'Bearer {}'.format(self._key)}

    def _get(self, path, params=None):
        from resources.lib.system import Http
        resp = Http.get(RD_BASE + path, headers=self._headers(), params=params, timeout=15)
        if resp.status_code == 200:
            return resp.json()
        debug('rd: GET {} → {}'.format(path, resp.status_code))
        return None

    def _post(self, path, data=None):
        from resources.lib.system import Http
        resp = Http.post(RD_BASE + path, headers=self._headers(), data=data, timeout=15)
        if resp.status_code in (200, 201):
            return resp.json()
        debug('rd: POST {} → {} body={}'.format(path, resp.status_code, resp.text[:200]))
        return None

    def _delete(self, path):
        from resources.lib.system import Http
        Http.delete(RD_BASE + path, headers=self._headers(), timeout=10)

    def check_cache(self, hashes):
        """
        Real-Debrid /torrents/instantAvailability byl ZAKÁZÁN (11/2024).
        Místo toho použijeme add + okamžitou kontrolu statusu.
        Vrátí prázdnou množinu – caller musí použít resolve_torrent přímo.
        """
        debug('rd: instantAvailability zakázáno, cache check přeskakujeme')
        return set()

    def resolve_torrent(self, info_hash, file_idx=None):
        """Přidá magnet, vybere soubor a vrátí stream URL."""
        debug('rd: resolve_torrent hash={}'.format(info_hash))
        try:
            magnet = 'magnet:?xt=urn:btih:{}'.format(info_hash)

            # 1. Přidej magnet
            result = self._post('/torrents/addMagnet', data={'magnet': magnet})
            if not result or 'id' not in result:
                debug('rd: addMagnet selhalo: {}'.format(result))
                return None
            torrent_id = result['id']
            debug('rd: torrent_id={}'.format(torrent_id))

            # 2. Vyber soubory
            self._post('/torrents/selectFiles/{}'.format(torrent_id), data={'files': 'all'})

            # 3. Počkej na status downloaded
            import time
            for _ in range(10):
                info = self._get('/torrents/info/{}'.format(torrent_id))
                if not info:
                    break
                status = info.get('status')
                debug('rd: torrent status={}'.format(status))
                if status == 'downloaded':
                    links = info.get('links', [])
                    if not links:
                        debug('rd: žádné links')
                        self._delete('/torrents/delete/{}'.format(torrent_id))
                        return None
                    # Vyber správný soubor
                    link = links[file_idx] if file_idx is not None and file_idx < len(links) else links[0]
                    return self._unrestrict(link, torrent_id)
                if status in ('error', 'magnet_error', 'virus', 'dead'):
                    debug('rd: torrent v chybovém stavu: {}'.format(status))
                    self._delete('/torrents/delete/{}'.format(torrent_id))
                    return None
                time.sleep(2)

            # Timeout – smaž torrent
            debug('rd: timeout při čekání na downloaded')
            self._delete('/torrents/delete/{}'.format(torrent_id))
            return None

        except Exception:
            debug('rd: resolve_torrent error: {}'.format(traceback.format_exc()))
            return None

    def _unrestrict(self, link, torrent_id=None):
        try:
            result = self._post('/unrestrict/link', data={'link': link})
            if result and result.get('download'):
                url = result['download']
                debug('rd: unrestricted URL={}'.format(url))
                # Nemazat torrent – může být potřeba pro opakované přehrání
                return url
            debug('rd: unrestrict selhalo: {}'.format(result))
            if torrent_id:
                self._delete('/torrents/delete/{}'.format(torrent_id))
        except Exception:
            debug('rd: unrestrict error: {}'.format(traceback.format_exc()))
        return None

    def unrestrict_link(self, link):
        return self._unrestrict(link)
