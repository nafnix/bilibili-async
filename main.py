from typing import List
import subprocess
import brequest
import asyncio
import os
import sys
import time


async def download(session: brequest.BilibiliSession, bid: str):
    url = 'https://www.bilibili.com/video/' + bid
    video_info = brequest.BilibiliVideo(session, url)
    title = await video_info.title

    # with open(title + '.png', 'wb') as img:
    #     img.write(await video_info.image())             # 下载封面图片

    print(f'---------------------------------------------------------------------------')
    print(f"开始下载 {bid}")
    with open(f'{title}.mp4', 'wb') as mp4:
        mp4.write(await video_info.fetch())             # 下载视频


async def main(argv: List[str]):
    async with brequest.BilibiliSession() as bilibili_session:
        tasks = [asyncio.create_task(download(bilibili_session, arg)) for arg in argv]
        done, pending = await asyncio.wait(tasks)


if __name__ == '__main__':
    
    start_time = time.time()
    _args: List[str] = sys.argv[1:]
    asyncio.run(main(_args))
    run_time = time.time() - start_time
    print('完成!总耗时:', run_time)
