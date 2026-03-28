# -*- coding: utf-8 -*-
"""
Playback pipeline pro StreamVault.

Explicitní, lineární pipeline:
  1. load_candidates()   – načte stream kandidáty ze všech dostupných providerů
  2. score_and_sort()    – ohodnotí a seřadí kandidáty podle preferencí uživatele
  3. pick_stream()       – vybere stream (auto nebo dialogen)
  4. resolve_url()       – doresolví ident/hash na přímé URL
  5. prepare_subtitles() – najde titulky
  6. play()              – předá URL + metadata Kodi přehrávači

Každý krok vrací jasný výsledek nebo vyvolá PlaybackError s kódem.
"""
from __future__ import print_function, unicode_literals

import traceback

from resources.lib.common.logger import debug, info
from resources.lib.models import StreamCandidate


class PlaybackError(Exception):
    """Chyba přehrávání s typem pro zobrazení v UI."""

    LOGIN_FAIL = 'login_fail'
    EXPIRED_SESSION = 'expired_session'
    NO_STREAMS = 'no_streams'
    PROVIDER_TIMEOUT = 'provider_timeout'
    NO_SUBSCRIPTION = 'no_subscription'
    RESOLVE_FAILED = 'resolve_failed'
    SUBTITLES_MISMATCH = 'subtitles_mismatch'
    USER_CANCELLED = 'user_cancelled'

    def __init__(self, code, message='', provider=None):
        super(PlaybackError, self).__init__(message)
        self.code = code
        self.provider = provider

    def __str__(self):
        return '[{}] {}'.format(self.code, self.args[0] if self.args else '')


class PlaybackPipeline:
    """
    Orchestruje přehrávání jednoho titulu/epizody.

    Použití:
        pipeline = PlaybackPipeline(media_item)
        pipeline.run()
    """

    def __init__(self, media_item, force_stream_select=False, preferred_provider=None):
        self.media_item = media_item
        self.force_select = force_stream_select
        self.preferred_provider = preferred_provider

        self._candidates = []
        self._chosen = None
        self._resolved_url = None
        self._subtitles = []

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    def run(self):
        """Spustí celou pipeline. Vyvolá PlaybackError při selhání."""
        info('pipeline: start pro {}'.format(
            getattr(self.media_item, 'title', str(self.media_item))))

        self._candidates = self.load_candidates()

        if not self._candidates:
            raise PlaybackError(PlaybackError.NO_STREAMS,
                                'Žádné streamy nebyly nalezeny.')

        self._candidates = self.score_and_sort(self._candidates)
        self._chosen = self.pick_stream(self._candidates)

        if self._chosen is None:
            raise PlaybackError(PlaybackError.USER_CANCELLED, 'Přehrávání zrušeno.')

        self._resolved_url = self.resolve_url(self._chosen)

        if not self._resolved_url:
            raise PlaybackError(PlaybackError.RESOLVE_FAILED,
                                'Nepodařilo se získat stream URL.',
                                provider=self._chosen.provider_id)

        self._subtitles = self.prepare_subtitles()
        self.play(self._resolved_url, self._chosen, self._subtitles)

    # ------------------------------------------------------------------
    # Krok 1 – načíst kandidáty
    # ------------------------------------------------------------------

    def load_candidates(self):
        """
        Načte stream kandidáty ze všech dostupných providerů.
        CZ/SK zdroje mají prioritu – zahraniční jen pokud CZ selžou nebo
        je uživatel na mezinárodním titulu.
        """
        candidates = []

        # --- Primární: kra.sk (SC API vrátí identifikátory) ---------------
        sc_url = getattr(self.media_item, 'sc_url', None)
        if sc_url:
            debug('pipeline: načítám SC/kra.sk streamy')
            candidates += self._load_kraska(sc_url)

        # --- Sekundární: WebShare (pokud je nakonfigurováno) --------------
        if not candidates:
            debug('pipeline: kra.sk nenašel streamy, zkouším WebShare')
            candidates += self._load_webshare()

        # --- Zahraniční: Torrentio + debrid (pokud je nakonfigurováno) ---
        imdb = getattr(self.media_item.ids, 'imdb', None) if hasattr(self.media_item, 'ids') else None
        if imdb:
            try:
                from resources.lib.kodiutils import get_setting
                use_intl = get_setting('intl.enabled') == 'true'
            except Exception:
                use_intl = False

            if use_intl or (not candidates):
                debug('pipeline: načítám Torrentio streamy')
                candidates += self._load_torrentio()

        debug('pipeline: celkem {} stream kandidátů'.format(len(candidates)))
        return candidates

    def _load_kraska(self, sc_url):
        """Načte SC API odpověď a vytvoří StreamCandidate objekty z kra.sk identů."""
        try:
            from resources.lib.api.sc import Sc
            from resources.lib.api.kraska import getKraInstance
            from resources.lib.constants import SC as SCC

            response = Sc.get(sc_url)
            if not response:
                return []

            streams_data = response.get(SCC.ITEM_STRMS, [])
            if not streams_data:
                return []

            kr = getKraInstance()
            candidates = []
            for stream in streams_data:
                ident = stream.get(SCC.ITEM_IDENT)
                if not ident:
                    continue
                vinfo = stream.get(SCC.ITEM_VIDEO_INFO, {})
                ainfo = stream.get(SCC.ITEM_AUDIO_INFO, {})
                quality = vinfo.get('quality') or stream.get(SCC.ITEM_QUALITY)
                c = StreamCandidate(
                    ident=ident,
                    provider_id='kraska',
                    quality=quality,
                    bitrate=stream.get(SCC.ITEM_BITRATE),
                    audio_lang=ainfo.get('lang') if ainfo else None,
                    audio_codec=ainfo.get('codec') if ainfo else None,
                    video_codec=vinfo.get('codec') if vinfo else None,
                    hdr='hdr' in (quality or '').lower(),
                    dolby_vision='dv' in (quality or '').lower(),
                    size_bytes=stream.get(SCC.ITEM_SIZE),
                    label=stream.get(SCC.ITEM_TITLE) or quality or ident,
                )
                candidates.append(c)
            return candidates
        except Exception:
            debug('pipeline: _load_kraska error: {}'.format(traceback.format_exc()))
            return []

    def _load_webshare(self):
        """Pokud by SC katalog obsahoval WebShare identy (budoucí rozšíření)."""
        # Zatím placeholder – WebShare se integrovuje primárně přes SC katalog
        return []

    def _load_torrentio(self):
        try:
            from resources.lib.providers.torrentio import TorrentioProvider
            p = TorrentioProvider()
            if not p.is_available():
                debug('pipeline: Torrentio není nakonfigurováno')
                return []
            return p.get_streams(self.media_item)
        except Exception:
            debug('pipeline: _load_torrentio error: {}'.format(traceback.format_exc()))
            return []

    # ------------------------------------------------------------------
    # Krok 2 – ohodnotit a seřadit
    # ------------------------------------------------------------------

    def score_and_sort(self, candidates):
        """Seřadí kandidáty: preferovaný jazyk > kvalita > velikost."""
        # Mapování indexů ze settings (type="integer") na skutečné hodnoty
        _LANG_MAP = {0: 'cs', 1: 'sk', 2: 'en', '0': 'cs', '1': 'sk', '2': 'en'}
        _QUAL_MAP = {0: '4K', 1: '1080p', 2: '720p', 3: '480p',
                     '0': '4K', '1': '1080p', '2': '720p', '3': '480p'}
        try:
            from resources.lib.kodiutils import get_setting
            _lang_raw = get_setting('stream.preferred_lang')
            _qual_raw = get_setting('stream.preferred_quality')
            pref_lang = _LANG_MAP.get(_lang_raw, _LANG_MAP.get(int(_lang_raw or 0), 'cs'))
            pref_quality = _QUAL_MAP.get(_qual_raw, _QUAL_MAP.get(int(_qual_raw or 1), '1080p'))
        except Exception:
            pref_lang = 'cs'
            pref_quality = '1080p'

        quality_order = {'4K': 4, '1080p': 3, '720p': 2, '480p': 1, 'SD': 0}
        pref_quality_score = quality_order.get(pref_quality, 3)

        def score(c):
            s = 0
            # 1. Shoda jazyka (nejvyšší váha)
            if c.audio_lang and pref_lang in (c.audio_lang or '').lower():
                s += 10000
            # 2. Kvalita – preferuj požadovanou, penalizuj příliš vysokou i nízkou
            cq = quality_order.get(c.quality, 1)
            s += 1000 - abs(cq - pref_quality_score) * 200
            # 3. HDR bonus
            if c.hdr:
                s += 100
            # 4. Velikost souboru (větší = lepší do rozumné míry)
            if c.size_bytes:
                s += min(c.size_bytes // (1024 ** 3), 20) * 10  # max 20 GB bonifikace
            # 5. Debrid streamy mají trochu vyšší prioritu (přímá URL)
            if c.is_debrid:
                s += 50
            return s

        return sorted(candidates, key=score, reverse=True)

    # ------------------------------------------------------------------
    # Krok 3 – vybrat stream
    # ------------------------------------------------------------------

    def pick_stream(self, candidates):
        """
        Vybere stream:
        - auto_pick=True a force_select=False → první kandidát
        - jinak → zobrazí dialog výběru
        """
        try:
            from resources.lib.kodiutils import get_setting_as_bool
            auto_pick = get_setting_as_bool('stream.auto_pick')
        except Exception:
            auto_pick = True

        if auto_pick and not self.force_select:
            debug('pipeline: auto-pick → {}'.format(candidates[0]))
            return candidates[0]

        return self._show_stream_select_dialog(candidates)

    def _show_stream_select_dialog(self, candidates):
        try:
            import xbmcgui
            labels = []
            for c in candidates:
                parts = [c.label or c.quality or '?']
                if c.audio_lang:
                    parts.append(c.audio_lang.upper())
                if c.size_bytes:
                    parts.append('{:.1f} GB'.format(c.size_bytes / 1024 ** 3))
                labels.append(' | '.join(parts))

            idx = xbmcgui.Dialog().select('Vybrat stream', labels)
            if idx < 0:
                return None
            return candidates[idx]
        except Exception:
            debug('pipeline: dialog error: {}'.format(traceback.format_exc()))
            return candidates[0] if candidates else None

    # ------------------------------------------------------------------
    # Krok 4 – resolve URL
    # ------------------------------------------------------------------

    def resolve_url(self, candidate):
        """Doresolví StreamCandidate na přímé přehrávací URL."""
        if candidate.url:
            debug('pipeline: URL již k dispozici')
            return candidate.url

        if candidate.provider_id == 'kraska':
            return self._resolve_kraska(candidate)

        if candidate.provider_id == 'webshare':
            return self._resolve_webshare(candidate)

        if candidate.provider_id == 'torrentio' and candidate.info_hash:
            return self._resolve_debrid(candidate)

        debug('pipeline: nelze resolvnout kandidáta: {}'.format(candidate))
        return None

    def _resolve_kraska(self, candidate):
        try:
            from resources.lib.api.kraska import getKraInstance
            kr = getKraInstance()
            server = None
            try:
                from resources.lib.kodiutils import get_setting
                server = get_setting('stream.adv.speedtest.best_server') or None
            except Exception:
                pass
            return kr.resolve(candidate.ident, server=server)
        except Exception as e:
            debug('pipeline: kra.sk resolve error: {}'.format(e))
            err_str = str(e).lower()
            if 'session' in err_str or 'login' in err_str:
                raise PlaybackError(PlaybackError.EXPIRED_SESSION, str(e), provider='kraska')
            if 'predplatne' in err_str or 'subscription' in err_str:
                raise PlaybackError(PlaybackError.NO_SUBSCRIPTION, str(e), provider='kraska')
            raise PlaybackError(PlaybackError.RESOLVE_FAILED, str(e), provider='kraska')

    def _resolve_webshare(self, candidate):
        try:
            from resources.lib.api.webshare import get_webshare_instance
            ws = get_webshare_instance()
            return ws.resolve(candidate.ident)
        except Exception as e:
            debug('pipeline: webshare resolve error: {}'.format(e))
            raise PlaybackError(PlaybackError.RESOLVE_FAILED, str(e), provider='webshare')

    def _resolve_debrid(self, candidate):
        try:
            from resources.lib.providers.debrid.manager import DebridManager
            dm = DebridManager.get()
            return dm.resolve_torrent(candidate.info_hash, candidate.file_idx)
        except Exception as e:
            debug('pipeline: debrid resolve error: {}'.format(e))
            raise PlaybackError(PlaybackError.RESOLVE_FAILED, str(e), provider='debrid')

    # ------------------------------------------------------------------
    # Krok 5 – titulky
    # ------------------------------------------------------------------

    def prepare_subtitles(self):
        """Vrátí seznam URL titulků, které se předají přehrávači."""
        sc_url = getattr(self.media_item, 'sc_url', None)
        if not sc_url:
            return []
        try:
            from resources.lib.api.sc import Sc
            from resources.lib.constants import SC as SCC
            response = Sc.get(sc_url)
            if not response:
                return []
            subs_data = response.get(SCC.ITEM_SUBS, [])
            return [s.get('url') for s in subs_data if s.get('url')]
        except Exception:
            debug('pipeline: prepare_subtitles error: {}'.format(traceback.format_exc()))
            return []

    # ------------------------------------------------------------------
    # Krok 6 – předat přehrávači
    # ------------------------------------------------------------------

    def play(self, url, candidate, subtitles=None):
        """Vytvoří Kodi ListItem a spustí přehrávání."""
        import xbmc
        import xbmcgui

        debug('pipeline: play URL={}'.format(url))

        li = xbmcgui.ListItem(path=url)
        li.setProperty('IsPlayable', 'true')

        # Metadata pro přehrávač
        info_dict = {}
        if hasattr(self.media_item, 'info_dict'):
            info_dict = self.media_item.info_dict()
        if info_dict:
            li.setInfo('video', info_dict)

        # Art
        if hasattr(self.media_item, 'art') and self.media_item.art:
            li.setArt(self.media_item.art.to_dict())

        # Titulky
        if subtitles:
            li.setSubtitles(subtitles)

        # Předáme přehrávači
        import xbmcplugin
        from resources.lib.constants import HANDLE
        xbmcplugin.setResolvedUrl(HANDLE, True, li)
        debug('pipeline: setResolvedUrl volán')

    # ------------------------------------------------------------------
    # Error handling helper
    # ------------------------------------------------------------------

    @staticmethod
    def show_error(error):
        """Zobrazí uživatelsky čitelnou chybovou hlášku."""
        try:
            import xbmcgui
            messages = {
                PlaybackError.LOGIN_FAIL: 'Přihlášení selhalo. Zkontroluj údaje v nastavení.',
                PlaybackError.EXPIRED_SESSION: 'Platnost session vypršela. Přihlašujeme znovu...',
                PlaybackError.NO_STREAMS: 'Pro tento titul nebyly nalezeny žádné streamy.',
                PlaybackError.PROVIDER_TIMEOUT: 'Provider nereagoval včas. Zkus to znovu.',
                PlaybackError.NO_SUBSCRIPTION: 'Nemáš aktivní předplatné u poskytovatele.',
                PlaybackError.RESOLVE_FAILED: 'Nepodařilo se získat odkaz ke streamu.',
                PlaybackError.USER_CANCELLED: '',
            }
            msg = messages.get(error.code, str(error))
            if msg:
                provider_info = ' ({})'.format(error.provider) if error.provider else ''
                xbmcgui.Dialog().notification(
                    'StreamVault',
                    '{}{}'.format(msg, provider_info),
                    xbmcgui.NOTIFICATION_ERROR,
                    5000
                )
        except Exception:
            debug('pipeline: show_error failed: {}'.format(traceback.format_exc()))
