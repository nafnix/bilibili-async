# Python爬取Bilibili示例

需下载模块模块：

- aiohttp：用于异步请求Bilibili网站
- lxml：用于解析返回的页面内容
- ffmpeg：用于合成音视频



## 使用示例

再使用abilibili模块时，可以指定BVID或者URL获取想要的内容。在获取内容的时候，你可以传入一个abilibili.BilibiliSession或者aiohttp的ClientSession或者不传入任何会话(如果没有传入任何会话，那么abilibili会在使用时自动创建)。

### 方式一

获取视频标题以及标签，可以通过创建一个连接会话来获取：

```python
import abilibili

BVID = '***'

async def main():
    async with abilibili.BilibiliSession() as bs:
        info = abilibili.BilibiliVideoInfo(session=bs, bid=BVID)
        title = await info.title
        tags = await info.tags
```

### 方式二

下载视频，这里不创建连接会话

```python
import abilibili

BVID = '***'

async def main():
    info = abilibili.BilibiliVideo(bid=BVID)
    with open('视频', 'wb') as mp4:
        mp4.write(await info.fetch())
```

## 示例

```python
import abilibili


async def example1():
    bid = 'BV1WK411577y'
    async with abilibili.BilibiliSession() as bs:

        bi = abilibili.BilibiliVideoInfo(session=bs, bid=bid)
        print(await bi.avid)            # AVID
        print(await bi.bvid)            # BVID
        print(await bi.title)           # 标题
        print(await bi.count)           # 文件计数
        print(await bi.desc)            # 简介
        print(await bi.tags)            # 标签
        print(await bi.image_url)       # 封面链接
        with open(await bi.title + '.png', 'wb') as img:
            img.write(await bi.image())             # 下载封面图片

        bv = abilibili.BilibiliVideo(session=bs, bid=bid, p=1)
        print(await bv.video_urls)
        print(await bv.audio_urls)
        with open(await bi.title + '.mp4', 'wb') as mp4:
            mp4.write(await bv.fetch())             # 下载视频


async def example2():
    bid = 'BV1WK411577y'

    bi = abilibili.BilibiliVideoInfo(bid=bid)
    print(await bi.avid)            # AVID
    print(await bi.bvid)            # BVID
    print(await bi.title)           # 标题
    print(await bi.count)           # 文件计数
    print(await bi.desc)            # 简介
    print(await bi.tags)            # 标签
    print(await bi.image_url)       # 封面链接
    with open(await bi.title + '.png', 'wb') as img:
        img.write(await bi.image())             # 下载封面图片

    bv = abilibili.BilibiliVideo(bid=bid, p=1)
    print(await bv.video_urls)
    print(await bv.audio_urls)
    with open(await bi.title + '.mp4', 'wb') as mp4:
        mp4.write(await bv.fetch())             # 下载视频

```

[示例文件](./example.py)
