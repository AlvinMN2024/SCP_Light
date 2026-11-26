# -*- coding: utf-8 -*-
'''Load SCP-Light service modules from this package.''' 
import importlib
import os

cfg = __import__(str(__name__).split('.')[0] + '.core.config', fromlist=[''])


class Modules:

    def __init__(self):
        pass

    def loading(self):
        directory = os.path.dirname(str(__file__))
        package = __name__.rsplit('.', 1)[0]
        for _, _, filenames in cfg.osSCP.walk(directory):
            for filename in sorted(filenames):
                if not filename.endswith('.py'):
                    continue
                module_name = filename[:-3]
                if module_name in ('modules', '__init__'):
                    continue
                module = importlib.import_module('.' + module_name, package)
                service_class = getattr(module, module_name, None)
                if service_class is None:
                    continue
                service = service_class()
                setattr(cfg, module_name, service)
                service.loading()
