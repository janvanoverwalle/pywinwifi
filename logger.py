import inspect
import logging
import os


class Logger(object):
    _log_directory = 'logs'
    _handlers = []
    _logger = None
    _enabled = True

    @classmethod
    def _reset(cls):
        # Close and remove any existing handlers
        for handler in cls._handlers:
            handler.close()
            cls._logger.removeHandler(handler)
        cls._handlers = []
        cls._logger = None

    @classmethod
    def _configure_logger(cls, *args, **kwargs):
        log_directory = kwargs.get('directory', kwargs.get('dir'))
        if log_directory:
            cls._log_directory = log_directory

        # TODO: Presence of output directory determines whether any logging whatsoever occurs. Not good!
        if not kwargs.get('force') and (cls._logger or not cls._enabled or not os.path.exists(cls._log_directory)):
            return

        if cls._logger:
            cls._reset()

        filename = os.path.join(kwargs.get('path', cls._log_directory), kwargs.get('filename', 'output.log'))
        if kwargs.get('overwrite_existing', True) and not kwargs.get('append'):
            try:
                os.remove(filename)
            except FileNotFoundError:
                pass

        os.makedirs(os.path.dirname(filename), exist_ok=True)

        file_handler = logging.FileHandler(filename, 'a+' if kwargs.get('append') else 'w+')
        file_handler.setLevel(kwargs.get('file_level', kwargs.get('level', logging.DEBUG)))

        console_handler = logging.StreamHandler()
        console_handler.setLevel(kwargs.get('console_level', kwargs.get('level', logging.WARNING)))

        default_log_format = '%(asctime)s - %(moduleinfo)18s - %(levelname)7s - %(message)s'
        file_format = kwargs.get('file_format', kwargs.get('format', default_log_format))
        file_handler.setFormatter(logging.Formatter(file_format))
        console_format = kwargs.get('console_format', kwargs.get('format', default_log_format))
        console_handler.setFormatter(logging.Formatter(console_format))

        cls._logger = logging.getLogger(__name__)
        cls._logger.setLevel(kwargs.get('level', logging.DEBUG))
        cls._logger.addHandler(file_handler)
        cls._handlers.append(file_handler)
        cls._logger.addHandler(console_handler)
        cls._handlers.append(console_handler)

    @classmethod
    def enable(cls, enabled=True):
        if cls._enabled == enabled:
            return
        if not enabled:
            cls.info('Disabling logger')
        cls._enabled = enabled
        if enabled:
            cls.info('Enabling logger')

    @classmethod
    def disable(cls):
        cls.enable(enabled=False)

    @classmethod
    def log(cls, level, msg, *args, **kwargs):
        if not cls._enabled:
            return

        cls._configure_logger(*args, **kwargs)
        if not cls._logger:
            return

        # Include module info into logs (can probably be improved)
        try:
            stack_index = 1
            caller = inspect.stack()[stack_index]
            caller_module = inspect.getmodule(caller[0])

            while caller_module.__name__ == __name__:
                stack_index += 1
                caller = inspect.stack()[stack_index]
                caller_module = inspect.getmodule(caller[0])

            line_nr = inspect.getlineno(caller[0])
            module_name = caller_module.__name__.split('.')[-1]
            module_info = '{0}.py:{1:>4}'.format(module_name, line_nr)
        except:
            module_info = 'unknown'

        if 'extra' in kwargs:
            kwargs['extra']['moduleinfo'] = module_info
        else:
            kwargs['extra'] = {'moduleinfo': module_info}

        cls._logger.log(level, msg, *args, **kwargs)

    @classmethod
    def debug(cls, msg, *args, **kwargs):
        cls.log(logging.DEBUG, msg, *args, **kwargs)

    @classmethod
    def info(cls, msg, *args, **kwargs):
        cls.log(logging.INFO, msg, *args, **kwargs)

    @classmethod
    def warning(cls, msg, *args, **kwargs):
        cls.log(logging.WARNING, msg, *args, **kwargs)

    @classmethod
    def error(cls, msg, *args, **kwargs):
        cls.log(logging.ERROR, msg, *args, **kwargs)

    @classmethod
    def exception(cls, msg, *args, exc_info=True, **kwargs):
        cls.error(msg, *args, exc_info=exc_info, **kwargs)

    @classmethod
    def critical(cls, msg, *args, **kwargs):
        cls.log(logging.CRITICAL, msg, *args, **kwargs)

    fatal = critical
