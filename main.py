import json
from collections import deque

import astrbot.api.message_components as Comp
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.star import Context, Star, register
from astrbot.core.agent.tool import FunctionTool
from mcp.types import CallToolResult


@register(
    "astrbot_plugin_search_history",
    "JimmyYu01",
    "让AstrBot能够自动缓存搜索记录，并允许用户使用指令进行查询。",
    "1.0.5",
)
class MyPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)

    async def initialize(self):
        """可选择实现异步的插件初始化方法，当实例化该插件类之后会自动调用该方法。"""
        self.search_providers = [
            "web_search_baidu",
            "web_search_tavily",
            "tavily_extract_web_page",
            "web_search_bocha",
            "web_search_brave",
            "web_search_firecrawl",
            "firecrawl_extract_web_page",
            "web_search_exa",
            "exa_get_contents",
            "web_search_anysearch",
        ]
        self.search_history = {}

    @filter.on_llm_tool_respond()
    async def on_llm_tool_respond(
        self,
        event: AstrMessageEvent,
        tool: FunctionTool,
        tool_args: dict | None,
        tool_result: CallToolResult | None,
    ):
        "当搜索完成时，自动将搜索记录按会话缓存。"
        if tool.name in self.search_providers:
            unified_msg_origin = event.unified_msg_origin
            if unified_msg_origin not in self.search_history:
                self.search_history[unified_msg_origin] = deque(maxlen=10)
            self.search_history[unified_msg_origin].appendleft((tool_args, tool_result))

    @filter.command("search_history", alias={"搜索记录"})
    async def check_search_history(self, event: AstrMessageEvent, index: int = 0):
        "查询搜索记录。"
        search_history = self.search_history.get(
            event.unified_msg_origin, deque(maxlen=10)
        )
        if index == 0:
            search_history_list = []
            i = 0
            for h in search_history:
                tool_args = h[0] or {}
                i = i + 1
                if "query" in tool_args:
                    search_history_list.append(f"{i}.搜索：{tool_args.get('query')}")
                elif "url" in tool_args:
                    search_history_list.append(f"{i}.抓取：{tool_args.get('url')}")
                else:
                    search_history_list.append(f"{i}.未识别此搜索记录")
            yield event.plain_result(
                "\n".join(search_history_list or ["当前会话暂无搜索记录"])
            )
        elif index in range(1, len(search_history) + 1):
            tool_args, tool_result = search_history[index - 1]
            if "query" in tool_args:
                search_history_list = []
                search_history_list.append(f"参数：{tool_args}")
                try:
                    results_dict = json.loads(tool_result.content[0].text)["results"]
                    for r in results_dict:
                        results_str = f"[{r['index']}] {r['title']}\n{r['url']}"
                        search_history_list.append(results_str)
                except Exception as e:  # noqa: BLE001
                    search_history_list.append(f"不支持输出此搜索记录：{e}")
                nodes = [
                    Comp.Node(
                        uin=event.get_self_id(),
                        name="AstrBot",
                        content=[Comp.Plain(h)],
                    )
                    for h in search_history_list
                ]
                yield event.chain_result([Comp.Nodes(nodes)])
            elif "url" in tool_args:
                yield event.plain_result("不支持输出此搜索记录")
            else:
                yield event.plain_result("未识别此搜索记录")
        else:
            yield event.plain_result("未找到此搜索记录")

    async def terminate(self):
        """可选择实现异步的插件销毁方法，当插件被卸载/停用时会调用。"""
