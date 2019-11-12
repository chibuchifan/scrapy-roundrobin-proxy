# scrapy-middlewares


## round_robin

一个用轮询实现的代理中间件, 一般的代理用random方式实现, 如果一个spider的代理数量少, 那么会发生碰撞, 造成代理的利用率下降.

这里采用的模式是如果一个代理是可用的, 那么下次尽可能将这个代理放到优先级队列的尾部, 也就是说, 尽量让一个代理在一个网站上使用的间隔最大.


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
