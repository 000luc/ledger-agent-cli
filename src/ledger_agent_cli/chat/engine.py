from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from openai import OpenAI

from ledger_agent_cli.chat.tools import TOOL_DEFINITIONS, execute_tool
from ledger_agent_cli.db import connect

MAX_ROUNDS = 10  # max tool-call rounds per user question
MAX_HISTORY = 20  # max conversation turns to keep


def _load_db_context(db_path: str | Path) -> str:
    """加载数据库上下文（可用公司和年份），用于构建系统提示词。"""
    try:
        with connect(db_path) as conn:
            companies = conn.execute(
                "SELECT name FROM companies ORDER BY name"
            ).fetchall()
            if not companies:
                return "数据库中暂无公司数据，请先导入序时账和科目余额表。"
            parts: list[str] = ["可用公司："]
            for c in companies:
                name: str = c["name"]
                years = conn.execute(
                    """
                    SELECT DISTINCT year FROM journal_lines
                    WHERE company_id = (SELECT id FROM companies WHERE name=?)
                    ORDER BY year
                    """,
                    (name,),
                ).fetchall()
                year_list = [str(y["year"]) for y in years]
                if year_list:
                    parts.append(f"  - {name}（有 {', '.join(year_list)} 年序时账数据）")
                else:
                    parts.append(f"  - {name}（已录入但无序时账数据）")
            return "\n".join(parts)
    except Exception:
        return "数据库连接失败，请检查数据库路径是否正确。"


SYSTEM_PROMPT_TEMPLATE = """你是一个专业的财务数据查询助手，帮助用户查询和分析账簿数据。

{db_context}

## 可用工具
你可以调用以下工具来查询数据：
1. list_companies - 列出所有公司
2. search_accounts - 按关键字搜索科目
3. tb_variance - 科目余额表年度差异对比
4. gl_variance - 序时账年度差异对比（含明细凭证）
5. trace_depreciation - 追踪折旧费用分配到哪些科目
6. reconcile_gl_tb - 序时账与科目余额表勾稽核对
7. run_sql - 执行只读 SQL 查询（当固定工具不够用时使用）
8. get_schema - 查看数据库表结构
9. run_saved_query - 执行已保存的查询模板

## 回答规则
1. 始终用中文回答，语言简洁专业
2. 金额显示为"元"，保留两位小数
3. 回答中引用你使用的数据来源（工具名称和查询条件），便于审计追溯
4. 如果查询结果为空，如实告知用户，不要编造数据
5. 如果用户的问题需要多条数据综合分析，拆分成多个步骤逐步查询
6. 对于差异分析，不仅要指出差异金额，还要结合数据特征分析可能的原因
7. 如果用户问"有什么问题"或类似表达，主动检查勾稽关系、异常波动等"""


class ChatEngine:
    """对话引擎，管理对话历史、工具调用和 DeepSeek API 交互。"""

    def __init__(
        self,
        db_path: str | Path,
        api_key: str,
        model: str = "deepseek-chat",
    ):
        self.db_path = Path(db_path)
        self.model = model
        self.client = OpenAI(
            api_key=api_key,
            base_url="https://api.deepseek.com",
        )
        db_context = _load_db_context(self.db_path)
        self.system_prompt = SYSTEM_PROMPT_TEMPLATE.format(db_context=db_context)
        self.messages: list[dict[str, Any]] = []
        self._reset()

    def _reset(self) -> None:
        self.messages = [{"role": "system", "content": self.system_prompt}]

    def _truncate_history(self) -> None:
        """保留最近 MAX_HISTORY 轮对话，控制上下文窗口。"""
        system = [m for m in self.messages if m["role"] == "system"]
        others = [m for m in self.messages if m["role"] != "system"]
        if len(others) > MAX_HISTORY * 2:
            others = others[-(MAX_HISTORY * 2):]
        self.messages = system + others

    def chat(self, user_input: str) -> str:
        """处理一条用户消息，返回 AI 的自然语言回答。"""
        self.messages.append({"role": "user", "content": user_input})

        for _ in range(MAX_ROUNDS):
            response = self.client.chat.completions.create(
                model=self.model,
                messages=self.messages,
                tools=TOOL_DEFINITIONS,
            )

            message = response.choices[0].message

            # 没有工具调用 → 这就是最终回答
            if not message.tool_calls:
                content = message.content or ""
                self.messages.append(
                    {"role": "assistant", "content": content}
                )
                self._truncate_history()
                return content

            # 有工具调用 → 记录 assistant 消息含 tool_calls
            assistant_msg: dict[str, Any] = {
                "role": "assistant",
                "content": message.content or "",
            }
            assistant_msg["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments,
                    },
                }
                for tc in message.tool_calls
            ]
            self.messages.append(assistant_msg)

            # 执行每个工具调用
            for tc in message.tool_calls:
                try:
                    args = json.loads(tc.function.arguments)
                    result = execute_tool(self.db_path, tc.function.name, args)
                    result_str = json.dumps(
                        result, ensure_ascii=False, default=str
                    )
                except Exception as e:
                    result_str = json.dumps(
                        {"error": str(e)}, ensure_ascii=False
                    )

                self.messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": result_str,
                })

        return "查询步骤较多，请简化问题或分步提问。"

    def is_empty(self) -> bool:
        """检查数据库是否有公司数据。"""
        try:
            with connect(self.db_path) as conn:
                row = conn.execute(
                    "SELECT COUNT(*) AS cnt FROM companies"
                ).fetchone()
                return int(row["cnt"]) == 0
        except Exception:
            return True
