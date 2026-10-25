# 图片来源

- `shanghai-street.jpg`：Tom Ru，上海街景，[Unsplash 原图页面](https://unsplash.com/photos/bicycles-are-lined-up-next-to-a-sidewalk-HundYXZl9fA)，[Unsplash License](https://unsplash.com/license)。用于 demo 配图，研究者可替换或删除。
- `avatar-default.svg`：项目内绘制的通用未设置头像。

头像及配图均由 JSON 引用；本地资源以内嵌图片传给浏览器，参与者浏览时不会向图片站点发送请求。

## 演示头像（2026-10-25）

以下图片从 Unsplash 图片 CDN 获取 192×192 的 JPEG 小图，质量参数 70。共 58,842 字节（约 57.5 KiB），单张不超过 19 KB；保留原街景配图，不用大图充当头像。授权条款：[Unsplash License](https://unsplash.com/license)。

| 文件 | 内容 | 来源 |
| --- | --- | --- |
| avatars/city-192.jpg | 街景 | [Tom Ru 原图页面](https://unsplash.com/photos/bicycles-are-lined-up-next-to-a-sidewalk-HundYXZl9fA) |
| avatars/cat-192.jpg | 猫 | [Kabo 原图页面](https://unsplash.com/photos/orange-and-white-cat-on-yellow-surface-sR0cTmQHPug) |
| avatars/dog-192.jpg | 狗 | [Bill Stephan 原图页面](https://unsplash.com/photos/golden-retriever-puppy-on-focus-photo-9LkqymZFLrE) |
| avatars/mountain-192.jpg | 山景 | [Unsplash 原始图片](https://images.unsplash.com/photo-1464822759023-fed622ff2c3b) |
| avatars/plant-192.jpg | 绿植 | [Unsplash 原始图片](https://images.unsplash.com/photo-1501004318641-b39e6451bec6) |

头像作为模拟账户的素材，不代表摄影者发布或支持实验中的帖子／评论。旧会话继续引用原配置；新配置版本附加 `-avatars1`。

## 省市区数据

`regions.json` 来自 [Administrative-divisions-of-China 的 pca-code.json](https://github.com/modood/Administrative-divisions-of-China)，2026-10-25 下载的本地快照，许可证见 `regions-LICENSE.txt`。该社区数据集不代表当前官方行政区划的实时结果。正式采集前核对覆盖地区与行政代码，并固定数据版本；参与者填写时不请求第三方地址服务。
