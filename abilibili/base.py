#!/usr/bin/python
# -*- coding: UTF-8 -*-

from typing import List, Union
from uuid import uuid4
import random
import json
import re
import os

from . import settings
from .net import BilibiliSession

from lxml import etree
import subprocess
from aiohttp import ClientResponse


# 重试模块
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


class BilibiliBase(object):

    BASEURL = 'https://bilibili.com/video'
    _HTML: etree = None

    def __init__(self, session: BilibiliSession, url: str = None, bvid: str = None, p: int = 1):
        """
        :param session: 请求客户端
        :param url: 请求URL
        """
        if bvid:
            self.url = '/'.join((self.BASEURL, bvid, f'?p={p}'))
        else:
            self.url = url
        self.session = session

    @retry(settings.RETRY)
    async def _request(self, method: str, url: str, headers: dict=None, **kwargs) -> ClientResponse:
        response = await self.session.request(method=method, url=url, headers=headers, **kwargs)
        return response

    async def _html(self) -> etree:
        """ 下载对应BID或URL的HTML页面并存储到 _HTML 属性中 """
        if not self._HTML:
            response = await self._request(method="GET", url=self.url)
            text = await response.text()
            self._HTML = etree.HTML(text)
        return self._HTML


class BilibiliVideoInfo(BilibiliBase):

    _cache_init_state = None

    # 缓存信息的页面
    async def _get_init_state(self) -> dict:

        if self._cache_init_state:                  # 如果已经有缓存了就直接返回缓存
            return self._cache_init_state

        if self._HTML is None:                      # 如果什么都没有就先下载页面
            await self._html()

        # 取出字典格式的内容
        init = self._HTML.xpath("/html/head/script[5]/text()")[0]
        init = init.split(';')[0]
        init = init.split('=', 1)[1]
        
        self._cache_init_state = json.loads(init)
        return self._cache_init_state

    async def _get_init(self, *keys):
        init_ = await self._get_init_state()
        ret = init_.copy()
        for k in keys:
            ret = ret[k]
        return ret

    @property
    async def bvid(self) -> str:
        if self.url and re.search(r'BV[\w]{10}', self.url):
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
    
    @property
    async def pages(self) -> List[str]:
        results = await self._get_init('videoData', 'pages')
        return [result['part'] for result in results]

    async def image(self) -> bytes:
        image_ = await self._request(method="GET", url=await self.image_url)
        return await image_.read()


class BilibiliVideo(BilibiliBase):

    _cache_play_info = None
    _init_get_video = None

    async def _get_play_info(self) -> dict:

        if self._cache_play_info:               # 检验是否已缓存页面
            return self._cache_play_info

        if self._HTML is None:                  # 检验初始页面是否已获取
            await self._html()

        info = self._HTML.xpath("/html/head/script[4]/text()")[0]
        self._cache_play_info = json.loads(re.search('{.+}', info).group())
        return self._cache_play_info

    async def _get_play(self, *keys):
        ''' 从缓存中提取需要的值 '''
        play_ = await self._get_play_info()
        ret = play_.copy()
        for k in keys:
            ret = ret[k]
        return ret

    @property
    async def video_urls(self) -> List[str]:
        ''' 获取视频资源地址 '''
        try:
            video_result = await self._get_play('data', 'dash', 'video')
            return [video_['baseUrl'] for video_ in video_result]
        except KeyError:
            video_result = await self._get_play('data', 'durl')
            return [video_['url'] for video_ in video_result]

    @property
    async def audio_urls(self) -> List[str]:
        ''' 获取音频资源地址 '''
        try:
            audios_result = await self._get_play('data', 'dash', 'audio')
            return [audio_['baseUrl'] for audio_ in audios_result]
        except KeyError:
            return []

    async def _fetch(self, cls: str):
        ''' 负责下载资源 选择最高清晰度 ''' 
        headers = self.session.request_headers
        headers['referer'] = self.BASEURL + '/'

        if cls == 'video':
            urls = await self.video_urls
        else:
            urls = await self.audio_urls
            if not urls:
                return b''

        # urls[0]是清晰度最高的资源
        if self._init_get_video is None:
            await self._request(method="OPTIONS", url=urls[0], headers=headers)
            self._init_get_video = True

        video_ = await self._request(method="GET", url=urls[0], headers=headers)
        content = await video_.read()
        return content

    async def fetch_video(self) -> bytes:
        ''' 获取视频 '''
        return await self._fetch('video')

    async def fetch_audio(self) -> bytes:
        ''' 获取音频 '''
        return await self._fetch('audio')

    async def fetch(self) -> bytes:
        ''' 下载视频和音频，并且使用ffmpeg将它们合成 '''
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