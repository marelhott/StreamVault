import json
import re
import traceback
from hashlib import md5

import xbmcaddon

from resources.lib.common.logger import debug
from resources.lib.constants import ADDON
from resources.lib.gui import home_win
from resources.lib.gui.dialog import dnotify, dyesno, dok
from resources.lib.kodiutils import open_settings, get_setting, set_setting
from resources.lib.language import Strings
from resources.lib.services.settings import settings
from resources.lib.system import Http

BASE = 'https://api.kra.sk'
UPLOAD = 'https://upload.kra.sk'
PROXY_PORT_DEFAULT = 65007

class ResolveException(Exception):
    pass


def getKraInstance():
    if Kraska.instance is None:
        Kraska.instance = Kraska()
    return Kraska.instance


class Kraska:
    instance = None
    _user_info = None
    token = False

    def __init__(self, u=None, p=None):
        self.username = u if u is not None else get_setting('kraska.user')
        self.password = p if p is not None else get_setting('kraska.pass')

    def login(self):
        try:
            debug('kra login start')
            data = self.get_data('/api/user/login', {'data': {'username': self.username, 'password': self.password}})
            if "session_id" in data:
                debug('kra login OK')
                self.set_token(data.get('session_id'))
                from resources.lib.api.sc import Sc
                Sc.get_auth_token(True)
                return True
        except:
            debug('kra err login: {}'.format(traceback.format_exc()))
            data = {}
            pass
        self.set_token(False)
        debug('DATA: {}'.format(data))
        debug('kra login FALSE')
        return False

    def set_token(self, token):
        if token != self.token:
            self.token = token
            debug('kra set token: [MASKED]')
            checksum_credentials = self._get_chsum(self.username, self.password)
            set_setting('kraska.chsum', '{}'.format(checksum_credentials))
            set_setting('kraska.token', '{}'.format(token))
            debug('kra set chsum: [OK]')

    @staticmethod
    def _get_chsum(username, password):
        return md5("{}|{}".format(password, username).encode('utf-8')).hexdigest()

    def get_token(self):
        # debug('get_token start')
        if self.token is not False:
            debug('kra get_token: [MASKED]')
            return self.token
        try:
            chsum = get_setting('kraska.chsum')
            if chsum is None or chsum == '':
                self.token = False
                return False
            testchsum = self._get_chsum(self.username, self.password)
            debug('check sum [{}] vs [{}]'.format(chsum, testchsum))
            if chsum != testchsum:
                debug('prihlasovacie udaje niesu zhodne s tokenom, treba login')
                self.token = False
                return False
        except Exception as e:
            debug('error get token: {}'.format(traceback.format_exc()))
            self.token = False
            return False
        # debug('get_token from settings')
        token = get_setting('kraska.token')
        debug('kra get cached token: [MASKED]')
        if token == '' or 'False' == token or None is token:
            debug('kra get_token: token is empty')
            token = False
        self.token = token
        # debug('get_token: {}'.format(token))
        return token

    def _check_server_availability(self, url, timeout=1):
        """
        Kontroluje dostupnosť servera pomocou HEAD requestu.

        Args:
            url: URL na kontrolu
            timeout: Timeout v sekundách (default 1s)

        Returns:
            bool: True ak je server dostupný, False inak
        """
        try:
            debug('Kontrolujem dostupnost servera: {}'.format(url))
            response = Http.head(url, timeout=timeout, allow_redirects=True)
            # Ak je odpoveď 2xx alebo 3xx (redirect), server je dostupný
            is_available = 200 <= response.status_code < 400
            debug('Server availability check: {} - status: {}'.format(
                'OK' if is_available else 'FAILED', response.status_code))
            return is_available
        except Exception as e:
            debug('Server availability check FAILED: {}'.format(str(e)))
            return False

    def resolve(self, ident, server=None, retry_count=0):
        """
        Resolve súbor z kra.sk API

        Args:
            ident: Identifikátor súboru
            server: Voliteľný custom server
            retry_count: Interný počítadlo retry pokusov (0 = prvý pokus, 1 = retry)

        Returns:
            URL súboru alebo None pri chybe
        """
        debug('kra resolve (attempt {}): ident={}, server={}'.format(retry_count + 1, ident, server))

        # Skontroluj či máme token, ak nie, prihlás sa
        if self.get_token() is False:
            debug('nemame token, pokusam sa prihlasit')
            if self.login() is False:
                debug('nepodarilo sa prihlasit')
                self.wrong_credential()
                return None

        # Skontroluj predplatné (days_left)
        try:
            days_left = self.get_days_left()
            if days_left is None:
                raise Exception('days_left is None')

            # Notifikácia ak ostáva menej ako 14 dní
            if 14 >= days_left:
                debug('mame nizky pocet dni predplatneho: {}'.format(days_left))
                dnotify(Strings.txt(Strings.KRASKA_NOTIFY_LOW_DAYS_LEFT).format(days_left), '')
        except Exception as e:
            debug('error pri ziskavani days_left: {}'.format(e))
            # Ak zlyhá get_days_left a je to prvý pokus, skús sa re-loginovať
            if retry_count == 0:
                debug('days_left zlyhal, invalidujem token a skusam znova')
                self.set_token(False)
                self._user_info = None  # vymažeme cache user_info
                return self.resolve(ident, server, retry_count + 1)
            else:
                # Po retry stále nemáme predplatné
                dok(Strings.txt(Strings.RESOLVE_ERROR_H1), Strings.txt(Strings.KRASKA_NOTIFY_NO_SUBSCRIPTION))
                return None

        # Pokus o resolve súboru
        debug('skusame resolvnut ident: {}'.format(ident))
        data = self.get_data('/api/file/download', {"data": {"ident": ident}})

        # Skontroluj či máme validnú odpoveď
        if data and "data" in data:
            file_data = data.get("data")
            if "link" in file_data:
                url = file_data.get("link")
                debug('kra resolvovala URL: {}'.format(url))

                # NOVÁ LOGIKA: Kontrola dostupnosti custom servera
                if server is not None:
                    old_url = url
                    new_url = re.sub(r'://(.{1,2}\d{2})\.', '://{}.'.format(server), url)

                    # Skontroluj dostupnosť nového servera pomocou HEAD requestu
                    if self._check_server_availability(new_url):
                        url = new_url
                        debug('kra custom server {} je dostupny, pouzivam: {} <= {}'.format(
                            server, url, old_url))
                    else:
                        debug('kra custom server {} NIEJE dostupny, fallback na API server: {}'.format(
                            server, old_url))
                        # url zostane pôvodná URL z API
                        # Vyčistíme nastavenie aby sa nepokúšalo použiť nedostupný server znova
                        set_setting('stream.adv.speedtest.best_server', '')
                        debug('Vymazany nedostupny server z nastaveni')

                return url

        # Ak sme tu, resolve zlyhal
        # Môže to byť API error (expirovaná session) alebo network error (data = False)

        # Ak je to prvý pokus, skúsime retry s re-login
        if retry_count == 0:
            if data and 'error' in data:
                error_code = data.get('error')
                error_msg = data.get('msg', 'Unknown error')
                debug('kra API error: {} - {}, invalidujem token a skusam znova'.format(error_code, error_msg))
            else:
                debug('kra resolve zlyhal (data={}), invalidujem token a skusam znova'.format(data))

            # Invalidujeme token a skúsime znova
            self.set_token(False)
            self._user_info = None  # vymažeme cache user_info
            return self.resolve(ident, server, retry_count + 1)

        # Po retry stále nefunguje
        if data and 'error' in data:
            error_msg = data.get('msg', 'Unknown error')
            debug('Nepodarilo sa resolvnut subor: {} - API error: {}'.format(ident, error_msg))
        else:
            debug('Nepodarilo sa resolvnut subor: {} - data: {}'.format(ident, data))

        raise ResolveException("Chybny subor alebo expirovala session")

    def resolve_via_proxy(self, ident, server=None, retry_count=0):
        """Resolve cez lokalny service.sc.helper proxy."""
        debug('kra resolve via proxy (attempt {}): ident={}, server={}'.format(retry_count + 1, ident, server))

        if self.get_token() is False:
            debug('nemame token, pokusam sa prihlasit')
            if self.login() is False:
                debug('nepodarilo sa prihlasit')
                self.wrong_credential()
                return None

        try:
            days_left = self.get_days_left()
            if days_left is None:
                raise Exception('days_left is None')
            if 14 >= days_left:
                debug('mame nizky pocet dni predplatneho: {}'.format(days_left))
                dnotify(Strings.txt(Strings.KRASKA_NOTIFY_LOW_DAYS_LEFT).format(days_left), '')
        except Exception as e:
            debug('error pri ziskavani days_left: {}'.format(e))
            if retry_count == 0:
                debug('days_left zlyhal, invalidujem token a skusam znova')
                self.set_token(False)
                self._user_info = None
                return self.resolve_via_proxy(ident, server, retry_count + 1)
            else:
                dok(Strings.txt(Strings.RESOLVE_ERROR_H1), Strings.txt(Strings.KRASKA_NOTIFY_NO_SUBSCRIPTION))
                return None

        port = home_win.getProperty('sc.helper.port')
        if not port:
            try:
                port = xbmcaddon.Addon('service.sc.helper').getSetting('port')
            except Exception:
                pass
        if not port:
            port = PROXY_PORT_DEFAULT
        proxy_port = int(port)
        proxy_url = 'http://127.0.0.1:{}/play?ident={}&token={}'.format(
            proxy_port, ident, self.token)
        if server:
            proxy_url += '&server={}'.format(server)

        debug('proxy request: {}'.format(proxy_url))
        try:
            resp = Http.get(proxy_url, timeout=20)
            data = resp.json()
        except Exception as e:
            debug('proxy error: {}'.format(traceback.format_exc()))
            if retry_count == 0:
                self.set_token(False)
                self._user_info = None
                return self.resolve_via_proxy(ident, server, retry_count + 1)
            raise ResolveException("Proxy error: {}".format(e))

        if 'error' in data:
            debug('proxy error response: {}'.format(data))
            if retry_count == 0:
                self.set_token(False)
                self._user_info = None
                return self.resolve_via_proxy(ident, server, retry_count + 1)
            raise ResolveException("Proxy: {}".format(data.get('error')))

        url = data.get('url')
        debug('proxy resolved: {}'.format(url))
        return url

    def get_days_left(self):
        debug('get days left')
        user_info = self.user_info()
        if not user_info:
            debug('nepodarilo sa natiahnut info o userovi')
            self.set_token(False)
            raise ResolveException("User nieje prihlaseny")

        if not user_info.get('subscribed_until'):
            debug('user nema aktivne predplatne')
            raise ResolveException("Nieje predplatne")

        debug('idem vratit pocet dni')
        return user_info.get('days_left', 0)

    def get_data(self, endpoint, data=None):
        if data is None:
            data = {}
        if self.token:
            data.update({'session_id': self.token})
        debug('kra req: {} {}'.format(endpoint, json.dumps(data)))
        try:
            raw_data = Http.post(BASE + endpoint, json=data)
            # debug('kra raw response: {}'.format(raw_data.text))
            return raw_data.json()
        except Exception as e:
            return False

    def user_info(self, level=0):
        if self._user_info is not None:
            debug('vraciame user info z cache')
            return self._user_info
        debug('skusam natiahnut user info')
        if self.get_token() is False:
            if self.login() is False:
                debug('Nepodarilo sa ziskat info o userovi, lebo nieje prihlaseny')
                self._user_info = None
                return False
        debug('mame token/sme uz prihlaseny')
        try:
            data = self.get_data('/api/user/info')
            if not data or 'data' not in data:
                debug('mame error na info {}'.format(data))
                raise Exception(data.get('msg', 'kraska error') if data else 'kraska error')

            user_data = data.get('data')
            days_left = user_data.get('days_left') or 0
            set_setting('kraska.days.left', days_left)
            debug('vracame info o userovi')
            self._user_info = user_data
            return self._user_info
        except Exception as e:
            debug('===========================================================================================')
            debug('kra error: {}'.format(traceback.format_exc()))
            debug('===========================================================================================')
            self.set_token(False)
            if level == 0:
                debug('skusame znova natiahnut info o userovi')
                return self.user_info(1)
        debug('vzdali sme info o userovi ... nieje prihlaseny')
        return False

    def check_user(self):
        debug('check_user start')
        if get_setting('kraska.user'):
            try:
                if not self.user_info():
                    raise Exception()
            except:
                self.wrong_credential()
                return

            try:
                self.get_days_left()
            except:
                dok('{} - {}'.format(Strings.txt(Strings.RESOLVE_ERROR_H1), ADDON.getAddonInfo('name')), Strings.txt(Strings.KRASKA_NOTIFY_NO_SUBSCRIPTION))

    def wrong_credential(self):
        res = dyesno('{} - {}'.format(Strings.txt(Strings.KRASKA_NOTIFY_CREDENTIAL_H1), ADDON.getAddonInfo('name')),
                     Strings.txt(Strings.KRASKA_NOTIFY_CREDENTIAL_L1))
        if res:
            open_settings('0.0')

    def list_files(self, parent=None, filter=None):
        self.get_token()
        data = self.get_data('/api/file/list', {'data': {'parent': parent, 'filter': filter}})
        debug('list files: {}'.format(data))

        return data

    def upload(self, data, filename):
        self.get_token()
        import base64

        item = self.get_data('/api/file/create', {'data': {'name': filename}, 'shared': False})
        if item is not False and 'error' in item and item.get('error') == 1205:
            found = self.list_files(filter=filename).get('data', [])
            if len(found) == 1 and found[0].get('name') == filename:
                return False
                # self.delete(found[0].get('ident'))
                # return self.upload(data, filename)

        if item is False or 'data' not in item:
            debug('error upload 1: {} / {}'.format(item, item.get('error')))
            raise Exception('error upload: {}'.format(item))

        file_data = item.get('data')
        ident = file_data.get('ident')
        link = file_data.get('link')
        if not ident or not link:
            debug('error upload 2: {}'.format(item))
            raise Exception('error upload: {}'.format(item))

        bident = base64.b64encode(ident.encode('utf-8')).decode("utf-8")

        headers = {
            'Tus-Resumable': '1.0.0',
            'Upload-Metadata': 'ident {}'.format(bident),
            'Upload-Length': str(len(data)),
        }
        # debug('upload headers: {} - {}'.format(link, json.dumps(headers)))

        upload = Http.post(link, headers=headers, allow_redirects=False)
        # debug('response headers: {}/{}'.format(upload.status_code, json.dumps(dict(upload.headers))))
        upload_url = upload.headers.get('location')

        if not upload_url or upload.status_code != 201:
            debug('error upload 3: {}'.format(item))
            self.delete(ident)
            raise Exception('error upload: {}'.format(item))

        debug('upload url: {}{}'.format(UPLOAD, upload_url))

        headers = {
            'Tus-Resumable': '1.0.0',
            'Upload-Offset': '0',
            'Content-Type': 'application/offset+octet-stream',
        }
        ufile = Http.patch('{}{}'.format(UPLOAD, upload_url), data=data, headers=headers)

        if ufile.status_code != 204:
            debug('error upload 4: {}'.format(ufile.status_code))
            self.delete(ident)

        debug('upload ok: {}'.format(ufile.get()))


    def delete(self, ident):
        return self.get_data('/api/file/delete', {'data': {'ident': ident}})

