import abilibili
import asyncio
import os
# 
# try:
#     asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
# except AttributeError:
#     pass

async def example1():
    bid = 'BV1NL41157ph'
    async with abilibili.BilibiliSession() as bs:

        bi = abilibili.BilibiliVideoInfo(session=bs, bvid=bid)

        # os.mkdir(f'./{await bi.title}')
        os.chdir(f'./{await bi.title}')

        print(await bi.avid)            # AVID
        print(await bi.bvid)            # BVID
        print(await bi.title)           # 标题
        print(await bi.count)           # 文件计数
        print(await bi.desc)            # 简介
        print(await bi.tags)            # 标签
        print(await bi.image_url)       # 封面链接
        parts = await bi.pages
        with open(await bi.title + '.png', 'wb') as img:
            img.write(await bi.image())             # 下载封面图片

        
        for video in range(65, await bi.count):
            print(f'开始下载第{video+1}个文件，共计{await bi.count}个。')
            print(f'---------------------------------------------------------------------------')
            bv = abilibili.BilibiliVideo(session=bs, bvid=bid, p=video+1)
            with open(f'第{str(video+1)}集 {parts[video]}.mp4', 'wb') as mp4:
                mp4.write(await bv.fetch())             # 下载视频


if __name__ == '__main__':

    import time

    start_time = time.time()
    asyncio.run(example1())
    run_time = time.time() - start_time
    print('完成!总耗时:', run_time)


# import requests
# a = requests.get('https://bilibili.com/video/BV1WK411577y')

# print(a.text)
