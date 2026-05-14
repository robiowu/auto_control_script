# -*- coding: utf-8 -*-
"""
my_log.py - 日志记录模块

职责:
- 提供支持文件轮转的日志记录器
- 同时输出到控制台和文件

调用链:
- game_case.py -> my_log.py -> logging
"""
import logging
from logging import handlers


class Logger(object):
    # 日志级别关系映射
    level_relations = {
        'debug': logging.DEBUG,
        'info': logging.INFO,
        'warning': logging.WARNING,
        'error': logging.ERROR,
        'crit': logging.CRITICAL
    }

    def __init__(self, filename: str, savelog: bool = True,
                 level: str = 'info', when: str = 'D',
                 backcount: int = 3,
                 fmt: str = '%(asctime)s - %(pathname)s[line:%(lineno)d] - %(levelname)s: %(message)s'):
        """
        初始化日志记录器，支持控制台输出和按时间轮转的文件输出。

        Args:
            filename (str): 日志文件名，可使用绝对路径或相对路径
            savelog (bool): 是否保存日志到文件，默认 True
            level (str): 最低捕获的日志级别，可选 debug/info/warning/error/crit
            when (str): 日志文件轮转时间单位，可选 S/M/H/D/W/midnight
            backcount (int): 最多保留的日志文件数量
            fmt (str): 日志输出格式字符串
        """
        self.logger = logging.getLogger(filename)
        # 设置日志格式
        format_str = logging.Formatter(fmt)
        # 这是设置采集日志的最低级别，默认是info，意思是debug级不采集，info及以上的采集
        self.logger.setLevel(self.level_relations.get(level))
        # 往屏幕上输出
        sh = logging.StreamHandler()
        # 设置屏幕上显示的格式
        sh.setFormatter(format_str)
        # 往文件里写入#指定间隔时间自动生成文件的处理器
        th = handlers.TimedRotatingFileHandler(filename=filename, when=when, backupCount=backcount, encoding='utf-8')
        # 实例化TimedRotatingFileHandler
        # interval是时间间隔，backupCount是备份文件的个数，如果超过这个个数，就会自动删除，when是间隔的时间单位，单位有以下几种：
        # S 秒
        # M 分
        # H 小时
        # D 天
        # W 每星期（interval==0时代表星期一）
        # midnight 每天凌晨
        # 设置文件里写入的格式
        th.setFormatter(format_str)
        # 把对象加到logger里
        self.logger.addHandler(sh)
        if savelog:
            self.logger.addHandler(th)


if __name__ == '__main__':
    log = Logger('auto_control_script_test.log', level='debug', backcount=1)
    log.logger.debug('debug')
    log.logger.info('info')
    log.logger.warning('警告')
    log.logger.error('报错')
    log.logger.critical('严重')
    Logger('error.log', level='error').logger.error('error')
