from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ledger_agent_cli.db import connect
from ledger_agent_cli.queries.accounts import search_accounts
from ledger_agent_cli.queries.reconcile import reconcile_gl_tb
from ledger_agent_cli.queries.saved import run_saved_query
from ledger_agent_cli.queries.trace import trace_depreciation
from ledger_agent_cli.queries.variance import gl_variance, tb_variance
from ledger_agent_cli.sql_guard import assert_read_only_select


def _list_companies(db_path: str | Path) -> list[dict]:
    with connect(db_path) as conn:
        rows = conn.execute(
            "SELECT id, name FROM companies ORDER BY name"
        ).fetchall()
    return [dict(row) for row in rows]


def _get_schema(db_path: str | Path) -> list[dict]:
    with connect(db_path) as conn:
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
    return [{"table": row["name"]} for row in rows]


TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "list_companies",
            "description": "列出数据库中所有公司",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_accounts",
            "description": "按关键字搜索科目，返回科目编码、名称、级别、是否末级等信息",
            "parameters": {
                "type": "object",
                "properties": {
                    "company": {
                        "type": "string",
                        "description": "公司名称",
                    },
                    "year": {
                        "type": "integer",
                        "description": "年份",
                    },
                    "keyword": {
                        "type": "string",
                        "description": "搜索关键词，如差旅费、管理费等",
                    },
                },
                "required": ["company", "year", "keyword"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "tb_variance",
            "description": "科目余额表年度差异分析，对比指定科目在两年间的期末余额变化",
            "parameters": {
                "type": "object",
                "properties": {
                    "company": {
                        "type": "string",
                        "description": "公司名称",
                    },
                    "year": {
                        "type": "integer",
                        "description": "当前年份",
                    },
                    "compare_year": {
                        "type": "integer",
                        "description": "对比年份",
                    },
                    "account": {
                        "type": "string",
                        "description": "科目名称关键词，如差旅费、管理费等",
                    },
                },
                "required": ["company", "year", "compare_year", "account"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "gl_variance",
            "description": "序时账年度差异分析，对比指定科目在两年间的凭证级发生额变化及明细",
            "parameters": {
                "type": "object",
                "properties": {
                    "company": {
                        "type": "string",
                        "description": "公司名称",
                    },
                    "year": {
                        "type": "integer",
                        "description": "当前年份",
                    },
                    "compare_year": {
                        "type": "integer",
                        "description": "对比年份",
                    },
                    "account": {
                        "type": "string",
                        "description": "科目名称关键词，如差旅费、管理费等",
                    },
                },
                "required": ["company", "year", "compare_year", "account"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "trace_depreciation",
            "description": "追踪折旧费用分配到哪些部门/科目，返回折旧的借方去向、金额和凭证数",
            "parameters": {
                "type": "object",
                "properties": {
                    "company": {
                        "type": "string",
                        "description": "公司名称",
                    },
                    "year": {
                        "type": "integer",
                        "description": "年份",
                    },
                },
                "required": ["company", "year"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "reconcile_gl_tb",
            "description": "序时账与科目余额表勾稽核对，找出借贷方金额不一致的科目",
            "parameters": {
                "type": "object",
                "properties": {
                    "company": {
                        "type": "string",
                        "description": "公司名称",
                    },
                    "year": {
                        "type": "integer",
                        "description": "年份",
                    },
                },
                "required": ["company", "year"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_sql",
            "description": "执行只读 SQL 查询（SELECT/WITH 语句），用于灵活查库",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "只读 SQL 查询语句（仅 SELECT / WITH）",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "返回行数上限，默认200，最大1000",
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_schema",
            "description": "查看数据库中有哪些表，了解数据表结构",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_saved_query",
            "description": "执行已保存的查询模板",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "查询模板名称",
                    },
                    "values": {
                        "type": "string",
                        "description": "SQL参数，JSON对象字符串，如 '{\"year\": 2025}'",
                    },
                },
                "required": ["name"],
            },
        },
    },
]


def execute_tool(
    db_path: str | Path,
    tool_name: str,
    arguments: dict[str, Any],
) -> Any:
    """Execute a tool by name with the given arguments."""
    if tool_name == "list_companies":
        return _list_companies(db_path)
    elif tool_name == "search_accounts":
        return search_accounts(
            db_path,
            arguments["company"],
            arguments["year"],
            arguments["keyword"],
        )
    elif tool_name == "tb_variance":
        return tb_variance(
            db_path,
            arguments["company"],
            arguments["year"],
            arguments["compare_year"],
            arguments["account"],
        )
    elif tool_name == "gl_variance":
        return gl_variance(
            db_path,
            arguments["company"],
            arguments["year"],
            arguments["compare_year"],
            arguments["account"],
        )
    elif tool_name == "trace_depreciation":
        return trace_depreciation(
            db_path,
            arguments["company"],
            arguments["year"],
        )
    elif tool_name == "reconcile_gl_tb":
        return reconcile_gl_tb(
            db_path,
            arguments["company"],
            arguments["year"],
        )
    elif tool_name == "run_sql":
        query = arguments["query"]
        assert_read_only_select(query)
        limit = min(max(arguments.get("limit", 200), 1), 1000)
        wrapped = f"SELECT * FROM ({query.rstrip(';')}) LIMIT ?"
        with connect(db_path) as conn:
            rows = conn.execute(wrapped, (limit,)).fetchall()
        return [dict(row) for row in rows]
    elif tool_name == "get_schema":
        return _get_schema(db_path)
    elif tool_name == "run_saved_query":
        values = {}
        if arguments.get("values"):
            values = json.loads(arguments["values"])
        return run_saved_query(db_path, arguments["name"], values)
    else:
        raise ValueError(f"未知工具: {tool_name}")
