from round_robin.proxy import Proxies
import time

def opens():
    with open('./proxy.txt', 'r') as f:
        p = f.read()
    return p.split()


if __name__ == '__main__':
    proxys = opens()
    a = Proxies(proxy_list=proxys,
                max_order=100000,
                timeout_if_no_proxy=10,
                proxy_download_delay=2,
                randomize_download_delay=True,
                )
    # print(a.get_proxy())
    while True:
        time.sleep(1)
        cc = a.get_proxy()
        # print(cc)
        a.mark_good(cc)