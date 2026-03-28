# -*- coding: utf-8 -*-
"""
WebShare.cz API klient.

Auth flow:
  1. POST /api/salt/  → salt
  2. sha1(md5crypt(password, salt)) + md5(user:Webshare:pass) → digest
  3. POST /api/login/ → wst token
  4. POST /api/file_link/ + ident + wst → přímý CDN link

Vyžaduje balíček passlib nebo vlastní md5crypt implementaci.
"""
from __future__ import print_function, unicode_literals

import hashlib
import traceback

try:
    from xml.etree import cElementTree as ET
except ImportError:
    from xml.etree import ElementTree as ET

from resources.lib.common.logger import debug
from resources.lib.kodiutils import get_setting, set_setting

BASE = 'https://webshare.cz'
API = BASE + '/api'
HEADERS = {
    'X-Requested-With': 'XMLHttpRequest',
    'Accept': 'text/xml; charset=UTF-8',
    'Content-Type': 'application/x-www-form-urlencoded',
}


def _md5crypt(password, salt, magic='$1$'):
    """Pure-Python implementace md5crypt (jako v /etc/passwd)."""
    import struct

    def _to_64(v, n):
        chars = './0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz'
        result = []
        while n > 0:
            result.append(chars[v & 0x3f])
            v >>= 6
            n -= 1
        return ''.join(result)

    if isinstance(password, str):
        password = password.encode('utf-8')
    if isinstance(salt, str):
        salt = salt.encode('utf-8')
    if isinstance(magic, str):
        magic = magic.encode('utf-8')

    # krok 1 – startovní hash
    m = hashlib.md5()
    m.update(password)
    m.update(magic)
    m.update(salt)

    # krok 2 – alternativní hash
    m2 = hashlib.md5()
    m2.update(password)
    m2.update(salt)
    m2.update(password)
    mixin = m2.digest()

    for i in range(len(password)):
        m.update(bytes([mixin[i % 16]]))

    i = len(password)
    while i:
        if i & 1:
            m.update(b'\x00')
        else:
            m.update(bytes([password[0]]))
        i >>= 1

    final = m.digest()

    # 1000 iterací
    for i in range(1000):
        m2 = hashlib.md5()
        if i & 1:
            m2.update(password)
        else:
            m2.update(final)
        if i % 3:
            m2.update(salt)
        if i % 7:
            m2.update(password)
        if i & 1:
            m2.update(final)
        else:
            m2.update(password)
        final = m2.digest()

    # přeuspořádání bajtů (md5crypt specifická permutace)
    p = final
    rearranged = bytes([
        p[0], p[6],  p[12],
        p[1], p[7],  p[13],
        p[2], p[8],  p[14],
        p[3], p[9],  p[15],
        p[4], p[10], p[5],
        p[11],
    ])

    result = magic + salt + b'$'
    result += _to_64(
        (rearranged[0] << 16) | (rearranged[1] << 8) | rearranged[2], 4
    ).encode()
    result += _to_64(
        (rearranged[3] << 16) | (rearranged[4] << 8) | rearranged[5], 4
    ).encode()
    result += _to_64(
        (rearranged[6] << 16) | (rearranged[7] << 8) | rearranged[8], 4
    ).encode()
    result += _to_64(
        (rearranged[9] << 16) | (rearranged[10] << 8) | rearranged[11], 4
    ).encode()
    result += _to_64(
        (rearranged[12] << 16) | (rearranged[13] << 8) | rearranged[14], 4
    ).encode()
    result += _to_64(rearranged[15], 2).encode()

    return result.decode('ascii')


def _xml_val(xml_text, tag):
    """Extrahuje hodnotu tagu z XML odpovědi WebShare."""
    try:
        root = ET.fromstring(xml_text)
        el = root.find(tag)
        return el.text if el is not None else None
    except Exception:
        return None


class WebshareException(Exception):
    pass


class Webshare:
    instance = None

    def __init__(self):
        self.username = get_setting('webshare.user')
        self.password = get_setting('webshare.pass')
        self._wst = None   # WebShare Token (session)

    # ------------------------------------------------------------------
    # Auth
    # ------------------------------------------------------------------

    def get_wst(self):
        """Vrátí platný WST token, pokud není platný – přihlásí."""
        if self._wst:
            return self._wst
        cached = get_setting('webshare.wst')
        if cached and cached not in ('', 'False', 'None'):
            self._wst = cached
            return self._wst
        return self.login()

    def login(self):
        debug('webshare: login start')
        if not self.username or not self.password:
            debug('webshare: chybí přihlašovací údaje')
            return None
        try:
            from resources.lib.system import Http

            # krok 1 – získej salt
            resp = Http.post(API + '/salt/', data={'username_or_email': self.username},
                             headers=HEADERS, timeout=10)
            salt = _xml_val(resp.text, 'salt')
            if not salt:
                debug('webshare: nepodařilo se získat salt')
                return None
            debug('webshare: salt = {}'.format(salt))

            # krok 2 – hashuj heslo
            encrypted = _md5crypt(self.password, salt)
            hashed_pass = hashlib.sha1(encrypted.encode('utf-8')).hexdigest()
            digest = hashlib.md5(
                '{}:Webshare:{}'.format(self.username, self.password).encode('utf-8')
            ).hexdigest()

            # krok 3 – přihlášení
            resp = Http.post(API + '/login/', headers=HEADERS, timeout=10, data={
                'username_or_email': self.username,
                'password': hashed_pass,
                'digest': digest,
                'keep_logged_in': '1',
            })
            token = _xml_val(resp.text, 'token')
            if not token:
                debug('webshare: login selhalo – odpověď: {}'.format(resp.text[:200]))
                return None

            debug('webshare: login OK, token = {}...'.format(token[:8]))
            self._wst = token
            set_setting('webshare.wst', token)
            return token
        except Exception:
            debug('webshare: login error: {}'.format(traceback.format_exc()))
            return None

    def logout(self):
        self._wst = None
        set_setting('webshare.wst', '')

    # ------------------------------------------------------------------
    # File resolution
    # ------------------------------------------------------------------

    def resolve(self, ident, retry=True):
        """
        Vrátí přímý CDN link pro daný WebShare ident.

        Returns: str URL nebo None
        """
        debug('webshare: resolve ident={}'.format(ident))
        wst = self.get_wst()
        if not wst:
            debug('webshare: nemáme WST token')
            return None
        try:
            from resources.lib.system import Http
            resp = Http.post(API + '/file_link/', headers=HEADERS, timeout=10, data={
                'ident': ident,
                'wst': wst,
            })
            link = _xml_val(resp.text, 'link')
            if link:
                debug('webshare: resolved URL = {}'.format(link))
                return link

            # status chyby – možná expirovaný token
            status = _xml_val(resp.text, 'status')
            debug('webshare: resolve status={}, resp={}'.format(status, resp.text[:200]))

            if retry and status in ('FATAL', 'FORBIDDEN', None):
                debug('webshare: reset WST a retry')
                self._wst = None
                set_setting('webshare.wst', '')
                return self.resolve(ident, retry=False)

        except Exception:
            debug('webshare: resolve error: {}'.format(traceback.format_exc()))
        return None

    # ------------------------------------------------------------------
    # Search (volitelné – pro případnou budoucí integraci)
    # ------------------------------------------------------------------

    def search(self, query, category='video', sort='largest', limit=50, offset=0):
        """
        Vyhledává soubory na WebShare.

        Returns: list[dict] s klíči: ident, name, size, type, ...
        """
        wst = self.get_wst()
        if not wst:
            return []
        try:
            from resources.lib.system import Http
            resp = Http.post(API + '/search/', headers=HEADERS, timeout=15, data={
                'what': query,
                'wst': wst,
                'category': category,
                'sort': sort,
                'limit': str(limit),
                'offset': str(offset),
            })
            root = ET.fromstring(resp.text)
            results = []
            for f in root.findall('.//file'):
                item = {}
                for child in f:
                    item[child.tag] = child.text
                results.append(item)
            return results
        except Exception:
            debug('webshare: search error: {}'.format(traceback.format_exc()))
            return []

    # ------------------------------------------------------------------
    # User info
    # ------------------------------------------------------------------

    def user_info(self):
        wst = self.get_wst()
        if not wst:
            return None
        try:
            from resources.lib.system import Http
            resp = Http.post(API + '/user_data/', headers=HEADERS, timeout=10,
                             data={'wst': wst})
            root = ET.fromstring(resp.text)
            info = {}
            for child in root:
                info[child.tag] = child.text
            return info
        except Exception:
            debug('webshare: user_info error: {}'.format(traceback.format_exc()))
            return None

    def is_premium(self):
        info = self.user_info()
        if not info:
            return False
        return info.get('vip_until') not in (None, '', '0')


def get_webshare_instance():
    if Webshare.instance is None:
        Webshare.instance = Webshare()
    return Webshare.instance
