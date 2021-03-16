from aiohttp import ClientSession, TCPConnector, ClientTimeout, ClientResponse
from lxml import etree
from typing import List
import json
import re
import asyncio
import subprocess
from uuid import uuid4
import os


class BilibiliClient(object):

    def __init__(
            self,
            pool: int = 8,
            timeout: int = 2333,
            ssl: bool = False,
            retry: int = 3
    ):
        """
        :param pool: 同时发起线程数
        :param timeout: 会话总超时时间
        :param ssl: 验证SSL
        :param retry: 报错重试次数
        """
        self._session = ClientSession(connector=TCPConnector(limit=pool), timeout=ClientTimeout(total=timeout))
        self._verify_ssl = ssl
        self._user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) " \
                           "Chrome/88.0.4324.190 Safari/537.36"
        self._retry = retry

    def headers(self, old_headers: dict = None):
        if old_headers is None:
            return {'User-Agent': self._user_agent}
        old_headers['User-Agent'] = self._user_agent
        return old_headers

    async def GET(
            self,
            url: str,
            timeout: int = None,
            headers: dict = None,
            params: dict = None
    ) -> ClientResponse:
        headers = self.headers(headers)
        for _ in range(self._retry):
            try:
                response = await self._session.get(
                    url=url,
                    headers=headers,
                    params=params,
                    timeout=timeout,
                    ssl=self._verify_ssl
                )
                return response
            except Exception as error:
                print(error)
                continue
        raise Exception(f'请求错误:\t{url}')

    async def OPTIONS(
            self,
            url: str,
            timeout: int = None,
            headers: dict = None,
            params: dict = None
    ):
        headers = self.headers(headers)
        for _ in range(self._retry):
            try:
                response = await self._session.options(
                    url=url,
                    headers=headers,
                    params=params,
                    timeout=timeout,
                    ssl=self._verify_ssl
                )
                return response
            except Exception as error:
                print(error)
                continue
        raise Exception(f'请求错误:\t{url}')

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await asyncio.sleep(0)
        await self._session.close()


class BilibiliVideo(object):

    BASEURL = 'https://www.bilibili.com'

    def __init__(
            self,
            session: BilibiliClient,
            url: str = None,
            bid: str = None,
            p: int = 1
    ):
        if url is None and bid is None:
            raise ValueError("'url' 或 'bid' 参数必须有值!")

        self._session = session
        self._html_tree = None
        self.url = url if url else '/'.join((self.BASEURL, 'video', bid))
        self._bid = bid
        self.params = {'p': p}

        self._cache_play_info = None
        self._cache_init_state = None
        self._init_get_video = None

    async def _html(self) -> str:
        response = await self._session.GET(self.url)
        text = await response.text()
        self._html_tree = etree.HTML(text)
        return self._html_tree

    async def _get_play_info(self) -> dict:
        if self._cache_play_info:
            return self._cache_play_info

        if self._html_tree is None:
            await self._html()
        info = self._html_tree.xpath("/html/head/script[5]/text()").pop()
        self._cache_play_info = json.loads(re.search('{.+}', info).group())
        return self._cache_play_info

    async def _get_init_state(self) -> dict:
        if self._cache_init_state:
            return self._cache_init_state

        if self._html_tree is None:
            await self._html()
        init = self._html_tree.xpath("/html/head/script[6]/text()")[0]
        self._cache_init_state = json.loads(re.search('{[^;]+}', init).group())
        return self._cache_init_state

    async def _get_init(self, *keys):
        init_ = await self._get_init_state()
        ret = init_.copy()
        for k in keys:
            ret = ret[k]
        return ret

    async def _get_play(self, *keys):
        play_ = await self._get_play_info()
        ret = play_.copy()
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
    async def image_url(self) -> str:
        return re.sub(r'/i2\.', r'/i0\.', await self._get_init('videoData', 'pic'))

    async def image(self) -> bytes:
        response = await self._session.GET(url=await self.image_url)
        return await response.read()

    @property
    async def tags(self) -> List[str]:
        tags = await self._get_init('tags')
        return [tag['tag_name'] for tag in tags]

    @property
    async def videos(self) -> List[str]:
        video_result = await self._get_play('data', 'dash', 'video')
        return [video_['baseUrl'] for video_ in video_result]

    @property
    async def audios(self) -> List[str]:
        audios_result = await self._get_play('data', 'dash', 'audio')
        return [audio_['baseUrl'] for audio_ in audios_result]

    async def _fetch(self, cls: str):
        headers = {'referer': self.BASEURL + '/'}

        if cls == 'video':
            urls = await self.videos
        else:
            urls = await self.audios

        if self._init_get_video is None:
            if self.params['p'] > await self.count:
                raise ValueError('超出最大范围视频')
            await self._session.OPTIONS(
                url=urls[0],
                headers=headers
            )
        mkv = await self._session.GET(url=urls[0], headers=headers, params=self.params)
        return await mkv.read()

    async def fetch_video(self) -> bytes:
        return await self._fetch('video')

    async def fetch_audio(self) -> bytes:
        return await self._fetch('audio')

    async def fetch(self) -> bytes:
        tmp_file_mp4_fn = str(uuid4()) + '.mp4'
        tmp_file_mp4 = await self.fetch_video()
        tmp_file_mp3_fn = str(uuid4()) + '.mp3'
        tmp_file_mp3 = await self.fetch_audio()

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


async def fetch_bilibili_video(bc: BilibiliClient, url: str, begin_p: int = 1, end_p: int = 1) -> List[bytes]:
    returns = []
    while begin_p <= end_p:
        video = BilibiliVideo(bc, url=url, p=begin_p)
        begin_p += 1
        returns.append(await video.fetch())
    return returns


