from __future__ import absolute_import
import logging
import codecs
from functools import partial
from six.moves.urllib.parse import urlsplit

from twisted.internet.error import ConnectError
from scrapy.exceptions import CloseSpider, NotConfigured
from scrapy import signals
from scrapy.utils.misc import load_object
from scrapy.utils.url import add_http_if_no_scheme
from .proxy import Proxies

logger = logging.getLogger(__name__)


class RoundRobinProxyiddleware:

    def __init__(self, proxy_list=None, max_order=0, stop_if_no_proxies=False, max_proxies_to_try=6,
                 timeout_if_no_proxy=3000, proxy_download_delay=3, randomize_download_delay=True):
        self.proxies = Proxies(proxy_list=self.cleanup_proxy_list(proxy_list),
                               max_order=max_order, timeout_if_no_proxy=timeout_if_no_proxy,
                               proxy_download_delay=proxy_download_delay,
                               randomize_download_delay=randomize_download_delay
                               )
        self.stop_if_no_proxies = stop_if_no_proxies
        self.max_proxies_to_try = max_proxies_to_try

    @classmethod
    def cleanup_proxy_list(cls, proxy_list):
        lines = [line.strip() for line in proxy_list]
        return list({
            add_http_if_no_scheme(url)
            for url in lines
            if url and not url.startswith('#')
        })

    @classmethod
    def from_crawler(cls, crawler):
        s = crawler.settings
        proxy_path = s.get('ROTATING_PROXY_LIST_PATH', None)
        if proxy_path is not None:
            with codecs.open(proxy_path, 'r', encoding='utf8') as f:
                proxy_list = [line.strip() for line in f if line.strip()]
        else:
            proxy_list = s.getlist('ROTATING_PROXY_LIST')
        if not proxy_list:
            raise NotConfigured()
        mw = cls(
            proxy_list=proxy_list,
            stop_if_no_proxies=s.getbool('ROTATING_PROXY_CLOSE_SPIDER', False),
            max_proxies_to_try=s.getint('ROTATING_PROXY_PAGE_RETRY_TIMES', 5),
            max_order=s.getint("PROXY_MAX_ORDER", 1000000),
            timeout_if_no_proxy=s.getint("TIMEOUT_IF_NO_PROXY", 300),
            proxy_download_delay=s.getint("PROXY_DELAY", 3),
            randomize_download_delay=s.getbool("RANDOMIZE_DOWNLOAD_DELAY", True)
        )
        return mw

    def process_request(self, request, spider):
        if 'proxy' in request.meta and not request.meta.get('_round_proxy'):
            return
        proxy = self.proxies.get_proxy()
        if not proxy:
            if self.stop_if_no_proxies:
                raise CloseSpider("no_proxies")
            else:
                logger.warning("No proxies available; marking all proxies "
                               "as unchecked")
                from twisted.internet.defer import DeferredLock
                with DeferredLock():
                    self.proxies.reset()
                proxy = self.proxies.get_proxy()
                if proxy is None:
                    logger.error("No proxies available even after a reset.")
                    raise CloseSpider("no_proxies_after_reset")

        request.meta['proxy'] = proxy
        request.meta['download_slot'] = self.get_proxy_slot(proxy)
        request.meta['_round_proxy'] = True

    def process_response(self, request, response, spider):
        return self._handle_result(request, spider) or response

    def _handle_result(self, request, spider):
        proxy = request.meta.get('proxy', None)
        if not (proxy and request.meta.get('_round_proxy')):
            return

        ban = request.meta.get('_ban', None)

        if ban is True:
            self.proxies.mark_good(proxy, delay=10)  # 如果一个代理被ban了, 说明还是能跑通的, 扔到代理池的最后面
            return self._retry(request, spider)
        else:
            self.proxies.mark_good(proxy)
            return None

    def _retry(self, request, spider):
        retries = request.meta.get('proxy_retry_times', 0) + 1
        max_proxies_to_try = request.meta.get('max_proxies_to_try',
                                              self.max_proxies_to_try)
        # 这里也就是说, 这个代理不能用了, 或者说这个代理需要一个较长时间之后才能用, 但是在取出代理的时候会阻塞,
        retryreq = request.copy()
        retryreq.meta['proxy_retry_times'] = retries
        retryreq.dont_filter = True
        retryreq.priority = 1  # 扔到一个比较低的优先级队列中
        return retryreq

    def process_exception(self, request, exception, spider):
        proxy = request.meta.get('proxy', None)
        if not (proxy and request.meta.get('_round_proxy')):
            return
        # 只要这个代理通, 那么就能用, 暂时这么定
        if isinstance(exception, ConnectError):
            # self.proxies.make_dead(proxy)
            pass
        else:
            self.proxies.mark_good(proxy)

    def get_proxy_slot(self, proxy):
        """
        Return downloader slot for a proxy.
        By default it doesn't take port in account, i.e. all proxies with
        the same hostname / ip address share the same slot.
        """
        # FIXME: an option to use website address as a part of slot as well?
        return urlsplit(proxy).hostname


class BanDetectionMiddleware(object):

    def process_response(self, request, response, spider):
        # 这里自己添加403?
        is_ban = getattr(spider, 'response_is_ban')
        ban = is_ban(request, response)
        request.meta['_ban'] = ban
        return response

    def process_exception(self, request, exception, spider):
        is_ban = getattr(spider, 'exception_is_ban')
        ban = is_ban(request, exception)
        request.meta['_ban'] = ban
