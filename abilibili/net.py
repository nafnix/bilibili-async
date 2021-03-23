#!/usr/bin/python
# -*- coding: UTF-8 -*-

import random
import asyncio

from . import settings

from aiohttp import (
    ClientSession, ClientTimeout,
    TCPConnector, BasicAuth,
)


class BilibiliSession(ClientSession):

    request_headers = {'User-Agent': random.choice(settings.USER_AGENT)}

    def __init__(
            self,
            pool: int = 8,
            proxy: str = None,
            proxy_auth: BasicAuth = None,
            auto_proxy: bool = None,
            timeout: int = 2333,
            ssl: bool = False
    ) -> None:
        """
        :param pool: 同时发起线程数
        :param proxy: 每个连接的代理
        :param proxy_auth: 每个连接的代理的身份
        :param auto_proxy: 自动设置系统代理
        :param timeout: 该客户端会话超时时间
        :param ssl: 验证SSL
        """
        super().__init__(
            trust_env=auto_proxy,
            connector=TCPConnector(limit=pool),
            timeout=ClientTimeout(total=timeout),
            headers=self.request_headers
        )

        self.proxy = proxy
        self.proxy_auth = proxy_auth

        self.verify_ssl = ssl
