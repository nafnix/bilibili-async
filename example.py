import abilibili
import asyncio

try:
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
except AttributeError:
    pass


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

if __name__ == '__main__':

    import time

    start_time = time.time()
    asyncio.run(example1())
    run_time = time.time() - start_time
    print(run_time)

    start_time = time.time()
    asyncio.run(example2())
    run_time = time.time() - start_time
    print(run_time)