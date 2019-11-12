import time
import logging
import random
from heapq import heapify, heappop, heappush
from functools import total_ordering
from twisted.internet.defer import DeferredLock
import traceback

logger = logging.getLogger(__name__)


@total_ordering
class Node:
    def __init__(self, attempts=0, address=None, order=0):
        self.attempts = attempts  # 下次可用的时间戳
        self.address = address  # 代理地址
        self.order = order  # 如果时间戳相同, 用order判断大小

    def __str__(self):
        return "Node(address={}, attempts={}, order={})".format(self.address, self.attempts, self.order)

    __repr__ = __str__

    def __eq__(self, other):
        return self.order == other.order and self.attempts == self.attempts

    def __lt__(self, other):
        if self.attempts == other.attempts:
            return self.order < other.order
        return self.attempts < other.attempts

    def __gt__(self, other):
        if self.attempts == other.attempts:
            return self.order > other.order
        return self.attempts > other.attempts

    def __hash__(self):
        return self.address


class Proxies:

    def __init__(self, proxy_list=None, max_order=0,
                 timeout_if_no_proxy=3000, proxy_download_delay=3, randomize_download_delay=True):
        self.proxies = None  # 代理的堆
        self.max_order = max_order  # 堆中最大的数字, 这个数字一定要比代理列表的长度大, 确保所有的代理都能放到堆中
        self.timeout_if_no_proxy = timeout_if_no_proxy  # 如果堆中没有元素, 多久后处理是否停止
        self.proxy_download_delay = proxy_download_delay  # 每个代理间隔多久可用
        self.randomize_download_delay = randomize_download_delay  # 对每个代理是否随机延迟
        self._lock = DeferredLock()
        self.current_order = 0
        self.init_proxies(proxy_list)

    def init_proxies(self, proxy_list):
        try:
            self._lock.acquire()
            proxy_list = [Node(attempts=time.time(), address=i, order=p) for p, i in enumerate(proxy_list)]
            heapify(proxy_list)
            self.proxies = proxy_list
            self.current_order = len(proxy_list)
        except Exception as e:
            traceback.print_exc()
        finally:
            self._lock.release()

    def get_proxy(self):
        try:
            self._lock.acquire()
            if not self.proxies:
                c = 0
                while c < self.timeout_if_no_proxy:
                    time.sleep(5)
                    c += 5
                    if self.proxies:
                        break
                address = None
            else:
                node = heappop(self.proxies)
                penalty = node.attempts - time.time()
                if penalty < 0:
                    address = node.address
                elif self.timeout_if_no_proxy >= penalty >= 0:
                    logger.debug("从现在开始, 这里要卡上{}".format(penalty))
                    time.sleep(penalty)
                    address = node.address
                else:
                    address = None
            return address
        except Exception as e:
            traceback.print_exc()
        finally:
            self._lock.release()

    def mark_dead(self, proxy):
        pass

    def mark_good(self, proxy, delay=0):
        if not proxy:
            raise ValueError("proxy {}报错".format(proxy))
        try:
            self._lock.acquire()
            if self.current_order > self.max_order:
                
                self.reset()
            self.current_order += 1
            attempts = time.time() + self.proxy_delay()
            if delay:
                attempts += delay
            node = Node(address=proxy, attempts=attempts, order=self.current_order)
            logger.debug("push {} to proxy pool".format(node))
            heappush(self.proxies, node)

        except Exception as e:
            traceback.print_exc()
        finally:
            self._lock.release()
        # print(self.proxies)

    def reset(self):
        logger.debug("这时候开始重置代理, 当前的牌号是{}, 最大order是{}".format(self.current_order, self.max_order))
        proxy_list = list(self.proxies)
        proxy_list = [Node(attempts=i.attempts, address=i.address, order=p) for p, i in enumerate(proxy_list)]
        heapify(proxy_list)
        self.proxies = proxy_list
        self.current_order = len(proxy_list)

    def proxy_delay(self):
        if self.randomize_download_delay:
            return random.uniform(0.5 * self.proxy_download_delay, 1.5 * self.proxy_download_delay)
        return self.proxy_download_delay
