from __future__ import print_function, unicode_literals

import time
import traceback

from resources.lib.api.kraska import getKraInstance
from resources.lib.common.android import AndroidTv
from resources.lib.common.logger import debug
from resources.lib.constants import ADDON, ADDON_ID
from resources.lib.gui.dialog import dtextviewer
from resources.lib.kodiutils import sleep, set_setting, get_uuid, get_setting, exec_build_in, get_setting_as_bool, \
    update_addon, clean_textures
from resources.lib.services.monitor import monitor
from resources.lib.services.player import player
from resources.lib.services.next_episodes import NextEp
from resources.lib.services.menu_cache_server import menu_cache_server


class Service:
    next_ep = None
    monitor = None
    player = None
    atv = None
    startup_time = None

    # 30s - dá zariadeniu čas na inicializáciu
    TRAKT_SYNC_STARTUP_DELAY = 30

    def __init__(self):
        set_setting('system.ver', ADDON.getAddonInfo('version'))
        get_uuid()
        if get_setting('androidtv.path'):
            self.atv = AndroidTv()
        self.startup_time = time.time()

    def run(self):
        debug('START SERVICE....................................................................')
        last_changelog = get_setting('system.changelog')

        update_addon()

        kr = getKraInstance()
        try:
            if kr.username and kr.password:
                kr.get_token()
                kr.user_info()
                # kr.login()
        except:
            debug('Kraska login error: {}'.format(traceback.format_exc()))
            kr.login()
            return
            pass

        if last_changelog != ADDON.getAddonInfo('version'):
            debug('SYSTEM.CHANGELOG: {}'.format(ADDON.getAddonInfo('changelog')))
            set_setting('system.changelog', '{}'.format(ADDON.getAddonInfo('version')))
            dtextviewer('', ADDON.getAddonInfo('changelog'))

        if get_setting_as_bool('system.autoexec'):
            try:
                exec_build_in('ActivateWindow(videos,plugin://{})'.format(ADDON_ID))
            except:
                pass

        if get_setting('kraska.user'):
            kra = getKraInstance()
            kra.check_user()

        # if get_setting_as_bool('system.ws.remote.enable'):
        #     ws = websocket.WS()
        #     ws.reconnect()

        self.next_ep = NextEp()

        clean_textures()
        from threading import Thread

        # MenuCacheServer sa inicializuje automaticky pri prvom použití (lazy loading)
        # Voliteľne: Preheat homepage cache pre lepší UX
        # try:
        #     debug('MenuCacheServer: Preheating homepage cache...')
        #     menu_cache_server.run()
        # except:
        #     debug('MenuCacheServer preheat error: {}'.format(traceback.format_exc()))
        #     pass

        # Spusti player thread
        w = Thread(target=player.run)
        w.start()

        while not monitor.abortRequested():
            try:
                self.periodical_check()
            except Exception as e:
                debug('error: {}'.format(traceback.format_exc()))
            sleep(1000 * 5)

    def periodical_check(self):
        if monitor.can_check():
            try:
                monitor.periodical_check()
            except:
                debug('monitor err: {}'.format(traceback.format_exc()))
                pass

            try:
                if self.atv:
                    self.atv.run()
            except:
                debug('android tv err: {}'.format(traceback.format_exc()))
                pass

            try:
                self.next_ep.start(monitor=monitor, player=player)
            except:
                debug('nextep err: {}'.format(traceback.format_exc()))
                pass


service = Service()
