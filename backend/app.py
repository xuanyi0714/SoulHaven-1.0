"""SoulHaven Flask 入口。

作用：
1. 创建 Flask 应用；
2. 启动时由 CharacterRegistry 从 characters 目录恢复角色，按英文名保存在字典中；
3. 注册 backend.api.routes 中的 API 蓝图；
4. 托管 web 目录下的前端页面。

项目根目录是 SoulHaven，推荐从根目录启动：
    python -m backend.app

也可以直接运行：
    python backend/app.py

启动后打开终端显示的 http://127.0.0.1:5000 即可使用前端。
创建角色时会写入 characters/<英文名>/description.json。
启动时会扫描该目录恢复角色资料，并从 history/original/original.json
恢复最近一次总结边界之后的上下文；每轮成功对话都已独立追加到该文件。
"""

import sys
from pathlib import Path

from flask import Flask

# 兼容直接运行 backend/app.py 的情况，把项目根目录 SoulHaven 加入导入路径。
PROJECT_ROOT = Path(__file__).resolve().parent.parent  # 项目根目录
if str(PROJECT_ROOT) not in sys.path:  # 项目根目录
    sys.path.insert(0, str(PROJECT_ROOT))  # 项目根目录

from backend.api.routes import create_api_blueprint
from backend.chat.get_character import CharacterRegistry

# 前端静态文件目录 SoulHaven/web，页面、脚本和样式分别放在 html/js/css 子目录。
WEB_DIR = PROJECT_ROOT / "web"  # 前端目录 = 项目根目录 / "web"

# Flask 应用对象；/static 映射到 web 目录，根路径 / 返回灵栖首页，/chat.html 保留现有聊天页面。
app = Flask(
    __name__,
    static_folder=str(WEB_DIR),  # 前端目录
    static_url_path="/static",
)

# 让 jsonify 直接输出中文，而不是 \uXXXX 转义。
app.json.ensure_ascii = False

# 这里位于模块顶层，因此每次启动新的 Python 进程、导入 backend.app 时
# 都会执行一次。它发生在下面 if __name__ == "__main__" 中的 app.run()
# 之前，保证 Flask 开始接收请求时角色字典已经加载完成。
CharacterRegistry.load_all()

# 指向注册表的同一个字典；API 蓝图和后续创建流程共享这份数据。
characters: dict = CharacterRegistry.characters

# 注册 API 路由，并把角色字典注入蓝图闭包。
app.register_blueprint(create_api_blueprint(characters))


@app.get("/")
@app.get("/lingqi_home_v1.html")
def index():
    """返回前端入口页面。

    Args:
        无。直接读取 WEB_DIR（前端目录）/html/lingqi_home_v1.html。

    Returns:
        Flask 静态文件响应；文件存在时状态码为 200。
    """
    return app.send_static_file("html/lingqi_home_v1.html")


@app.get("/chat.html")
def chat_page():
    """兼容直接访问 /chat.html 的方式。

    Args:
        无。返回现有完整聊天页面，不使用旧灵栖聊天半成品。

    Returns:
        Flask 静态文件响应；文件存在时状态码为 200。
    """
    return app.send_static_file("html/chat.html")


@app.get("/characters.html")
@app.get("/lingqi_characters.html")
def characters_page():
    """返回通过角色列表接口动态展示卡片的角色档案页面。"""
    return app.send_static_file("html/lingqi_characters.html")


@app.get("/character-detail.html")
@app.get("/lingqi_character_detail.html")
def character_detail_page():
    """返回旧灵栖角色详情视觉原型，不编造角色资料。"""
    return app.send_static_file("html/lingqi_character_detail.html")


@app.get("/lingqi_MainChat.html")
def legacy_frontend_page():
    """兼容旧前端书签，统一转到当前页面。"""
    from flask import redirect, request

    pages = {
        "/lingqi_home_v1.html": "/",
        "/lingqi_characters.html": "/characters.html",
        "/lingqi_character_detail.html": "/character-detail.html",
        "/lingqi_MainChat.html": "/chat.html",
    }
    return redirect(pages[request.path])


# 只有直接运行 python backend/app.py 或 python -m backend.app 时才启动
# 开发服务器；被其他模块 import 时不会自动监听端口。
if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)
