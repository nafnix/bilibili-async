import abilibili


"""
此处借用 https://www.bilibili.com/video/BV1vJ411X74Z
"""


async def main():
    async with abilibili.BilibiliClient()as bilibili_client:
        bilibili_video = abilibili.BilibiliVideo(session=bilibili_client, bid='BV1vJ411X74Z')

        print(bilibili_video.url)              # 打印视频链接

        print(await bilibili_video.bvid)             # 打印BV号
        print(await bilibili_video.avid)             # 打印AV号
        print(await bilibili_video.title)            # 打印标题
        print(await bilibili_video.desc)             # 打印视频介绍
        print(await bilibili_video.count)            # 打印该视频数量
        print(await bilibili_video.image_url)        # 打印视频链接
        print(await bilibili_video.tags)             # 打印视频标签

        print(await bilibili_video.videos)           # 打印视频真正链接 列表 第一个是最清晰 最后一个是最低清晰度
        print(await bilibili_video.audios)           # 打印视频的音频真正链接 列表 第一个是最清晰 最后一个是最低清晰度

        # 下载
        title = await bilibili_video.title

        # 下载视频
        video_filename = title + '.mp4'
        with open(video_filename, 'wb') as video:
            video_content = await bilibili_video.fetch()
            video.write(video_content)

        # 下载显示的图片
        image_filename = title + '.jpg'
        with open(image_filename, 'wb') as image:
            image_content = await bilibili_video.image()
            image.write(image_content)

        # 下载所有的视频
        count = await bilibili_video.count
        videos = await abilibili.fetch_bilibili_video(bilibili_client, url=bilibili_video.url, end_p=count)
        for c in range(count):
            filename = f"[{c}]{title}.mp4"
            with open(filename, 'wb') as video:
                video.write(videos[c])
