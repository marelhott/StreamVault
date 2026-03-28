# -*- coding: utf-8 -*-
from __future__ import print_function, unicode_literals

from resources.lib.common.logger import info

if __name__ == '__main__':
    info('StreamVault service start')
    from resources.lib.services.service import run
    run()
