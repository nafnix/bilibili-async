from typing import List, Union
from uuid import uuid4
import random
import json
import re
import os
import asyncio

from lxml import etree
import subprocess
from aiohttp import ClientSession, ClientResponse, ClientTimeout, TCPConnector, BasicAuth



USER_AGENT = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    "Mozilla/5.0 (Macintosh; U; Intel Mac OS X 10_6_8; en-us)",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_7_0)",
    "AppleWebKit/537.36 (KHTML, like Gecko)",
    "AppleWebKit/535.11 (KHTML, like Gecko)",
    "Chrome/89.0.4389.90",
    "Chrome/17.0.963.56",
    "Safari/537.36",
    "Safari/534.50",
    "Safari/535.11",
    "Edg/89.0.774.57",
    "Opera/9.80 (Macintosh; Intel Mac OS X 10.6.8; U; en) Presto/2.8.131 Version/11.11",
    "Opera/9.80 (Windows NT 6.1; U; en) Presto/2.8.131 Version/11.11",
]


RETRY = 3


class BilibiliSession(ClientSession):

    request_headers = {'User-Agent': random.choice(USER_AGENT)}

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


class BilibiliVideo(object):

    BASEURL = 'https://bilibili.com/video'
    _HTML: etree = None
    _info_cache = None
    _cache_play_info = None
    _init_get_video = None

    def __init__(self, session: BilibiliSession, url: str, p: int = 1):
        """
        :param session: 请求客户端
        :param url: 请求URL
        :param p:请求视频集数
        """
        self.url = url
        self.session = session

    @retry(RETRY)
    async def _request(self, method: str, url: str, headers: dict=None, **kwargs) -> ClientResponse:
        response = await self.session.request(method=method, url=url, headers=headers, **kwargs)
        return response

    async def _html(self) -> etree:
        """ 下载HTML页面并存储到 _HTML 属性中 """
        if not self._HTML:
            response = await self.session.get(self.url)
            text = await response.text()
            self._HTML = etree.HTML(text)
        return self._HTML

    # 缓存页面上信息的部分，不缓存的话每次请求都会去下载一次页面
    async def _get_info_cache(self) -> dict:

        if self._info_cache:                  # 如果已经有缓存了就直接返回缓存
            return self._info_cache

        if self._HTML is None:                # 如果什么都没有就先下载页面
            await self._html()

        # 取出字典格式的内容
        init = self._HTML.xpath("/html/head/script[5]/text()")[0]
        init = ''.join(init.split(';')[0: -4])
        init = init.split('=', 1)[1]
        self._info_cache = json.loads(init)
        return self._info_cache

    async def _get_info(self, *keys):
        _info = await self._get_info_cache()
        _data = _info.copy()
        for k in keys:
            _data = _data[k]
        return _data

    @property
    async def bvid(self) -> str:
        """BVID号"""
        search_bvid = re.search(r'BV[\w]{10}', self.url)
        if search_bvid:
            return search_bvid.group()
        else:
            return await self._get_info('bvid')

    @property
    async def avid(self) -> int:
        """AVID号"""
        return await self._get_info('aid')

    @property
    async def title(self) -> str:
        """标题"""
        return await self._get_info('videoData', 'title')

    @property
    async def desc(self) -> str:
        """视频介绍"""
        return await self._get_info('videoData', 'desc')

    @property
    async def count(self) -> int:
        """视频集数"""
        return await self._get_info('videoData', 'videos')

    @property
    async def tags(self) -> List[str]:
        """视频标签"""
        tags = await self._get_info('tags')
        return [tag['tag_name'] for tag in tags]

    @property
    async def image_url(self) -> str:
        """封面地址"""
        url = re.sub(r'/i2\.', r'/i0\.', await self._get_info('videoData', 'pic'))
        url = re.sub(r'\\', '', url)
        return url
    
    @property
    async def pages(self) -> List[str]:
        """忘记是啥了"""
        results = await self._get_info('videoData', 'pages')
        return [result['part'] for result in results]

    async def image(self) -> bytes:
        """图片"""
        image_ = await self._request(method="GET", url=await self.image_url)
        return await image_.read()

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
        ''' 获取视频 不带音频 '''
        return await self._fetch('video')

    async def fetch_audio(self) -> bytes:
        ''' 获取音频 '''
        return await self._fetch('audio')

    async def fetch(self) -> bytes:
        ''' 下载视频和音频，并用ffmpeg将它们合成 '''
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
            f'ffmpeg -i {tmp_file_mp4_fn} -i {tmp_file_mp3_fn} -c:v copy -c:a aac -strict experimental {out_tmp_file}', shell=True
        )   
        # 'ffmpeg -i video.mp4 -i audio.wav -c:v copy -c:a aac -strict experimental output.mp4'
        with open(out_tmp_file, 'rb') as tmp:
            ret = tmp.read()

        os.remove(tmp_file_mp4_fn)
        os.remove(tmp_file_mp3_fn)
        os.remove(out_tmp_file)

        return ret