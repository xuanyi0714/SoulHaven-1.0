# 网页字体

存放随项目提供的网页字体及其许可证。

- `maiyuan.ttf`：荆南麦圆体（Kingnam Maiyuan Regular），用于心声正文的圆润手写效果，是参考图“甜甜淡奶油体”的近似风格，并非同款。
- 官方仓库：https://github.com/maoken-fonts/KNMaiyuan
- 原始文件：https://raw.githubusercontent.com/maoken-fonts/KNMaiyuan/main/fonts/TTF/KNMaiyuan-Regular.ttf
- 许可证：SIL Open Font License 1.1，完整文本保存在 `OFL-maiyuan.txt`。字体文件未作修改，仅使用简短英文文件名。

字体通过 `/static/fonts/maiyuan.ttf` 本地提供，不需要用户安装，也不在运行时请求外部字体服务。文件约 8 MB；加载期间回退到系统圆体或无衬线字体。行书标题与操作界面仍使用各自的字体层级。
