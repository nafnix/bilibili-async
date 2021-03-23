#!/usr/bin/python
# -*- coding: UTF-8 -*-

from typing import List
from uuid import uuid4
import json
import re
import os

from . import settings
from .net import BilibiliSession

from lxml import etree
import subprocess
from aiohttp import ClientResponse


def retry(retries: int):
    def wrapper(fetch_func):
        async def run(*args, **kwargs):
            nonlocal retries
            while True:
                retries -= 1
                try:
                    resp = await fetch_func(*args, **kwargs)
                except Exception as error:
                    if retries == 0:
                        raise error
                else:
                    return resp
        return run
    return wrapper


class BilibiliInitError(Exception):

    def __init__(self):
        self.message = "'url' 或 'bid' 参数必须有值!"

    def __str__(self):
        return self.message


class BilibiliBase(object):

    BASEURL = 'https://www.bilibili.com'
    _HTML: etree = None

    def __init__(
            self,
            session: BilibiliSession = None,
            url: str = None,
            bid: str = None,
    ):
        """
        :param session: 请求客户端
        :param url: 请求URL
        :param bid: 请求ID
        """
        if url is None and bid is None:
            raise BilibiliInitError()

        self.url = url if url else '/'.join((self.BASEURL, 'video', bid))
        self._session = session
        self._bid = bid

    @retry(settings.RETRY)
    async def _request(
            self,
            method: str,
            url: str,
            bs: BilibiliSession = None,
            headers: dict = None,
            **kwargs) -> ClientResponse:

        if self._session:
            response = await self._session.request(
                method=method,
                url=url,
                headers=headers,
                proxy=self._session.proxy if self._session.proxy else kwargs.get('proxy'),
                proxy_auth=self._session.proxy_auth if self._session.proxy_auth else kwargs.get('proxy_auth'),
                ssl=self._session.verify_ssl,
                **kwargs
            )
        else:
            response = await bs.request(
                method=method,
                url=url,
                headers=headers,
                **kwargs
            )
        return response

    async def __html(self) -> etree:
        """ 下载对应BID或URL的HTML页面 """
        if self._session:
            response = await self._request(method=settings.METHOD_GET, url=self.url)
            text = await response.text()
        else:
            async with BilibiliSession(auto_proxy=True) as bs:
                response = await self._request(method=settings.METHOD_GET, url=self.url, bs=bs)
                text = await response.text()
        return etree.HTML(text)

    async def _html(self) -> str:
        """将HTML页面保存至HTML数据属性中"""
        if not self._HTML:
            self._HTML = await self.__html()
        return self._HTML


class BilibiliVideoInfo(BilibiliBase):

    _cache_init_state = None

    async def _get_init_state(self) -> dict:

        if self._cache_init_state:
            return self._cache_init_state
        if self._HTML is None:
            await self._html()

        init = self._HTML.xpath("/html/head/script[6]/text()")[0]
        a = re.search(r'{.*(?=;\(function)', init).group()
        self._cache_init_state = json.loads(a)

        return self._cache_init_state

    async def _get_init(self, *keys):
        init_ = await self._get_init_state()
        ret = init_.copy()
        for k in keys:
            ret = ret[k]
        return ret

    @property
    async def bvid(self) -> str:
        if self._bid:
            return self._bid
        elif self.url and re.search(r'BV[\w]{10}', self.url):
            return re.search(r'BV[\w]{10}', self.url).group()
        else:
            return await self._get_init('bvid')

    @property
    async def avid(self) -> int:
        return await self._get_init('aid')

    @property
    async def title(self) -> str:
        return await self._get_init('videoData', 'title')

    @property
    async def desc(self) -> str:
        return await self._get_init('videoData', 'desc')

    @property
    async def count(self) -> int:
        return await self._get_init('videoData', 'videos')

    @property
    async def tags(self) -> List[str]:
        tags = await self._get_init('tags')
        return [tag['tag_name'] for tag in tags]

    @property
    async def image_url(self) -> str:
        url = re.sub(r'/i2\.', r'/i0\.', await self._get_init('videoData', 'pic'))
        url = re.sub(r'\\', '', url)
        return url

    async def image(self) -> bytes:
        if self._session:
            image_ = await self._request(
                method=settings.METHOD_GET,
                url=await self.image_url,
                headers=self._session.request_headers
            )
            return await image_.read()
        else:
            async with BilibiliSession(auto_proxy=True) as bs:
                image_ = await self._request(
                    bs=bs,
                    method=settings.METHOD_GET,
                    url=await self.image_url
                )
                content = await image_.read()
            return content


class BilibiliVideo(BilibiliBase):

    _cache_play_info = None
    _init_get_video = None

    def __init__(
            self,
            p: int = 1,
            session: BilibiliSession = None,
            url: str = None,
            bid: str = None
    ) -> None:
        super().__init__(session, url, bid)
        self.p = p
        self._params = {'p': p}

    async def _get_play_info(self) -> dict:
        if self._cache_play_info:
            return self._cache_play_info

        if self._HTML is None:
            await self._html()

        info = self._HTML.xpath("/html/head/script[5]/text()").pop()
        self._cache_play_info = json.loads(re.search('{.+}', info).group())

        return self._cache_play_info

    async def _get_play(self, *keys):
        play_ = await self._get_play_info()
        ret = play_.copy()
        for k in keys:
            ret = ret[k]
        return ret

    @property
    async def video_urls(self) -> List[str]:
        try:
            video_result = await self._get_play('data', 'dash', 'video')
            return [video_['baseUrl'] for video_ in video_result]
        except KeyError:
            video_result = await self._get_play('data', 'durl')
            return [video_['url'] for video_ in video_result]

    @property
    async def audio_urls(self) -> List[str]:
        try:
            audios_result = await self._get_play('data', 'dash', 'audio')
            return [audio_['baseUrl'] for audio_ in audios_result]
        except KeyError:
            return []

    async def _fetch(self, cls: str):
        if self._session:
            headers = self._session.request_headers
        else:
            headers = {'User-Agent': settings.USER_AGENT[0]}

        headers['referer'] = self.BASEURL + '/'

        if cls == 'video':
            urls = await self.video_urls
        else:
            urls = await self.audio_urls
            if not urls:
                return b''

        if self._init_get_video is None:

            if self._session:
                await self._request(
                    method=settings.METHOD_OPTIONS,
                    url=urls[0],
                    headers=headers
                )
            else:
                async with BilibiliSession(auto_proxy=True) as bs:
                    await self._request(
                        method=settings.METHOD_OPTIONS,
                        url=urls[0],
                        headers=headers,
                        bs=bs
                    )
            self._init_get_video = True

        if self._session:
            video_ = await self._request(
                method=settings.METHOD_GET,
                url=urls[0],
                headers=headers,
                params=self._params
            )
            content = await video_.read()
        else:
            async with BilibiliSession(auto_proxy=True) as bs:
                video_ = await self._request(
                    bs=bs,
                    method=settings.METHOD_GET,
                    url=urls[0],
                    headers=headers,
                    params=self._params
                )
                content = await video_.read()
        return content

    async def fetch_video(self) -> bytes:
        return await self._fetch('video')

    async def fetch_audio(self) -> bytes:
        return await self._fetch('audio')

    async def fetch(self) -> bytes:
        tmp_file_mp4_fn = str(uuid4()) + '.mp4'
        tmp_file_mp4 = await self.fetch_video()
        tmp_file_mp3_fn = str(uuid4()) + '.mp3'
        tmp_file_mp3 = await self.fetch_audio()

        if not tmp_file_mp3:
            return tmp_file_mp4

        with open(tmp_file_mp4_fn, 'wb') as tf4:
            tf4.write(tmp_file_mp4)

        with open(tmp_file_mp3_fn, 'wb') as tf3:
            tf3.write(tmp_file_mp3)

        out_tmp_file = '[finish]' + tmp_file_mp4_fn

        subprocess.call(
            'ffmpeg -i ' + tmp_file_mp4_fn + ' -i ' + tmp_file_mp3_fn + '  -c copy ' + out_tmp_file, shell=True
        )

        with open(out_tmp_file, 'rb') as tmp:
            ret = tmp.read()

        os.remove(tmp_file_mp4_fn)
        os.remove(tmp_file_mp3_fn)
        os.remove(out_tmp_file)

        return ret
