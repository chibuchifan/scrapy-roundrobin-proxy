# scrapy-middlewares

## 设计思想

在抓一个指定网站的时候, 保证不能抓这个网站太快, 防止将网站抓跪了

在防止被ban上, 我们的理想条件是每个代理在两次抓取中间隔最大, 这样可以尽量避免被反爬引擎监控到. 随机的获取代理会造成碰撞

第二就是每个页面不允许失败, 如果这个页面是因为被ban然后失败, 那么将这个页面扔到队列的最后, 过阵子再抓.

每次请求都从代理池中拿出一个最长时间未使用的代理.


## round_robin

一个用轮询实现的代理中间件, 一般的代理用random方式实现, 如果一个spider的代理数量少, 那么会发生碰撞, 造成代理的利用率下降.

这里采用的模式是如果一个代理是可用的, 那么下次尽可能将这个代理放到优先级队列的尾部, 也就是说, 尽量让一个代理在一个网站上使用的间隔最大.


具体用法参考见这个大佬的(代理插件)[https://github.com/TeamHG-Memex/scrapy-ROUND_ROBIN-proxies]

在settings.py文件中编辑

```python
DOWNLOADER_MIDDLEWARES = {
    # ...
    'round_robin.middlewares.ROUND_ROBINProxyMiddleware': 610,
    'round_robin.middlewares.BanDetectionMiddleware': 620,
    # ...
}
```


每个spider需要实现下面两个方法, 用来确定哪些页面是被ban掉的:

```python
    def response_is_ban(self, request, response):
        if response.status not in self.NOT_BAN_STATUSES:
            return True
        if response.status == 200 and not len(response.body):
            return True
        return False

    def exception_is_ban(self, request, exception):
        return not isinstance(exception, self.NOT_BAN_EXCEPTIONS)
 ```

 在`settings.py`中设置下面几个参数:


```python
ROUND_ROBIN_PROXY_LIST_PATH = "proxy.txt" # 存放代理的路径, 格式类似于127.0.0.1:8080
# 或者直接在setting中写
ROUND_ROBIN_PROXY_LIST = [
    'proxy1.com:8000',
    'proxy2.com:8031',
    # ...
]

ROUND_ROBIN_PROXY_CLOSE_SPIDER = True # 代理为空的操作, 默认是关闭
ROUND_ROBIN_PROXY_PAGE_RETRY_TIMES = 2 # 代理失败的重试次数, 这个是重试过失败后会扔到队列最后面, 也就是说, 不允许有失败的页面
PROXY_MAX_ORDER =  100000 # 内存中代理池的最大数量, 这个数字应该比你代理的数量大一倍, 建议
TIMEOUT_IF_NO_PROXY = 300 # 代理池为空的话, 等待多少秒后才抛出没有代理的异常
ROUND_ROBIN_PROXY_DELAY = 3 # 每个代理间隔多久才能用, 默认是3s, 这里是说, 我这个代理再次请求这个网站的间隔
RANDOMIZE_DOWNLOAD_DELAY # True # 代理的延迟间隔是否采用随机, 随机的话是0.5*delay ~ 1.5*delay之间
```