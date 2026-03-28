# -*- coding: utf-8 -*-
from __future__ import print_function, unicode_literals

from resources.lib.common.logger import info
from resources.lib.streamvault import StreamVault

if __name__ == '__main__':
    info('StreamVault start')
    StreamVault().run()
