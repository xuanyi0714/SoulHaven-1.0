# 前端视频素材

视频统一放入本目录，与 `web/pictures/` 同级，通过 `/static/videos/` 引用。文件使用简短的英文用途名，不保留重复副本或图片目录中的旧视频。

## home_breeze.mp4

Current revision: continuous-5, 2026-11-01. Same paid Seedance source; no new paid generation. 1920x1080, 24fps, 102 frames, 4.25 seconds, H.264 CRF16. Trims the near-static head/tail from clean-seam-4, retaining frames 3 through 104 without additional face interpolation. Script: D:/GitHub_projects/comfyUI/workflows/trim_home_hold.py; source: D:/GitHub_projects/comfyUI/output/seedance_trial/seedance_clean.mp4, produced by make_home_loop_clean.py. White-haired girl retains one blink using the previously tracked open-eye repair. Black-haired and brown-haired girls have no newly added blinks. Tree/light effects remain separate frontend Canvas/CSS. No API key is included.

- 前端文件：`web/videos/home_breeze.mp4`
- 播放地址：`/static/videos/home_breeze.mp4?v=continuous-5`
- 本次只迁移文件，SHA256：`7447594A1556C6F0624476C8161B17E96672C83A04B5A5A100A51C926A801CC1`。
- 已撤销黑发/棕发女生额外眼部贴图动画，播放原视频里的表情。

## seaside_breeze.mp4

聊天试玩页的茶会动态背景。当前版本使用火山方舟 Seedance 2.0（`doubao-seedance-2-0-260128`，任务 `cgt-20261103203201-vbxjc`），以 `seaside_tea.webp` 为首帧，生成一条 1080p、16:9、7 秒无声视频。固定机位下，大云团向右移动，海面反光流动、帆船缓行，三人闭嘴并错开眨眼，身体有轻微动作。

原片 169 帧。对石地的枝影加入从每帧活动枝叶推导的局部亮度变化。选取第 24–148 帧（从 0 起计），接上第 149–168 帧过渡到第 4–23 帧的 20 帧交叠。天空用带方向的局部渐散，水面交叠用双向光流对齐帆船，减少重影。用 FFmpeg 导出 1920×1080、24 fps、145 帧（约 6.04 秒）的无声 H.264 MP4，CRF 17，像素格式 yuv420p。

桌面欢迎页静音循环播放 `/static/videos/seaside_breeze.mp4?v=cloud-drift`。角色聊天和隐藏标签页暂停，窄屏、减少动态效果或播放失败时使用对应静态茶会插画。


## world_breeze.mp4

世界设定列表页动态背景。使用火山方舟 Seedance 2.0，以 `web/pictures/world_jianghu.png` 同时作为首帧和尾帧，生成 8 秒、1080p、无声视频；提示固定机位，让瀑布、河流、山谷水雾、阳光与少量红叶缓慢变化。

从 193 帧原片取第 18–174 帧，之后将第 175–192 帧与第 1–18 帧做 18 帧交叠，输出 175 帧（约 7.29 秒）、24fps、1920×1080 的 H.264/yuv420p 无声 MP4。首尾画面差异经缩略帧检查约为 1.03，相邻帧平均约为 0.91（0–255 像素差，不表示严格无缝）。

`web/html/world.html` 与 `web/js/world-motion.js` 静音循环播放；视频失败和减少动态效果时使用原始图片，页面隐藏时暂停。桌面与窄屏都可播放。
