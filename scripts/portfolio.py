#!/usr/bin/env python3
"""
持仓管理脚本 - 增删改基金持仓
首次使用：若未配置持仓（portfolio.json不存在），返回 setup_required 引导信息

用法:
  python3 portfolio.py add 000001 10000 "混合基金"
  python3 portfolio.py remove 000001
  python3 portfolio.py list
  python3 portfolio.py clear
  python3 portfolio.py setup "<feishu_doc_url>"   # 从飞书文档导入
"""

import json
import sys
import os
import re
import urllib.request

PORTFOLIO_FILE = "/root/.openclaw/workspace-feishu-investment/skills/china-fund-advisor/portfolio.json"
FEISHU_WIKI_RE = re.compile(r'wiki/([A-Za-z0-9]+)')
FEISHU_DOCX_RE = re.compile(r'docx/([A-Za-z0-9]+)')

def get_default_portfolio():
    return {
        "version": "1.0",
        "updated_at": None,
        "holder": None,
        "funds": []
    }

def load_portfolio():
    try:
        if os.path.exists(PORTFOLIO_FILE):
            with open(PORTFOLIO_FILE, 'r') as f:
                data = json.load(f)
                # 验证格式
                if "funds" in data:
                    return data
        raise FileNotFoundError("portfolio.json not found or invalid")
    except:
        return None

def save_portfolio(data):
    import subprocess
    updated_at = subprocess.run(
        ["python3", "-c", "from datetime import datetime; print(datetime.now().strftime('%Y-%m-%d %H:%M'))"],
        capture_output=True, text=True
    ).stdout.strip()
    data["updated_at"] = updated_at
    with open(PORTFOLIO_FILE, 'w') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def subprocess_run(cmd, **kwargs):
    import subprocess
    return subprocess.run(cmd, capture_output=True, text=True, **kwargs)

def cmd_add(code, amount, name=""):
    data = load_portfolio()
    if data is None:
        print(json.dumps({"status": "setup_required", "message": "请先配置持仓"}))
        return
    
    code = code.strip().zfill(6)
    existing = [f for f in data["funds"] if f["code"] == code]
    if existing:
        existing[0]["amount"] = float(amount)
        if name:
            existing[0]["name"] = name
        print(f"更新持仓: {code} -> ¥{amount}")
    else:
        added_at = subprocess_run(
            ["python3", "-c", "from datetime import datetime; print(datetime.now().strftime('%Y-%m-%d'))"],
            capture_output=True, text=True
        ).stdout.strip()
        data["funds"].append({
            "code": code,
            "name": name or code,
            "amount": float(amount),
            "added_at": added_at
        })
        print(f"添加持仓: {code} ({name}) -> ¥{amount}")
    
    save_portfolio(data)
    print(json.dumps({"status": "ok", "funds_count": len(data["funds"])}))

def cmd_remove(code):
    data = load_portfolio()
    if data is None:
        print(json.dumps({"status": "setup_required", "message": "请先配置持仓"}))
        return
    code = code.strip().zfill(6)
    before = len(data["funds"])
    data["funds"] = [f for f in data["funds"] if f["code"] != code]
    if len(data["funds"]) < before:
        save_portfolio(data)
        print(f"已移除: {code}")
        print(json.dumps({"status": "ok", "removed": code}))
    else:
        print(f"未找到: {code}")
        print(json.dumps({"status": "not_found", "code": code}))

def cmd_list():
    data = load_portfolio()
    if data is None:
        print(json.dumps({
            "status": "setup_required",
            "message": "首次使用需要配置持仓",
            "instruction": "请提供你的飞书持仓文档链接，或回复「创建模板文档」让助手自动创建"
        }))
        return
    
    funds = data.get("funds", [])
    result = {
        "status": "ok",
        "holder": data.get("holder"),
        "funds": funds,
        "total": sum(float(f.get("amount", 0)) for f in funds)
    }
    print(json.dumps(result, ensure_ascii=False))

def cmd_clear():
    data = load_portfolio()
    if data is None:
        print(json.dumps({"status": "setup_required", "message": "请先配置持仓"}))
        return
    data["funds"] = []
    save_portfolio(data)
    print(json.dumps({"status": "ok", "message": "已清空持仓"}))

def cmd_set_holder(name):
    data = load_portfolio()
    if data is None:
        print(json.dumps({"status": "setup_required", "message": "请先配置持仓"}))
        return
    data["holder"] = name
    save_portfolio(data)
    print(json.dumps({"status": "ok", "holder": name}))

def parse_feishu_url(url):
    """从飞书文档URL中提取token"""
    m = FEISHU_DOCX_RE.search(url)
    if m:
        return ("docx", m.group(1))
    m = FEISHU_WIKI_RE.search(url)
    if m:
        return ("wiki", m.group(1))
    return None

def cmd_setup(feishu_url=""):
    """
    首次配置：尝试从飞书文档导入，或引导用户创建模板
    """
    if not feishu_url:
        # 返回引导信息
        print(json.dumps({
            "status": "setup_required",
            "action": "provide_url",
            "message": (
                "首次使用，需要先配置你的持仓。\n\n"
                "请选择：\n"
                "1. 提供你的飞书持仓文档链接（推荐），助手自动迁移\n"
                "2. 回复「创建模板」，助手自动创建空白持仓文档，你填入数据后再保存\n\n"
                "已有持仓文档链接请直接粘贴过来。"
            )
        }, ensure_ascii=False))
        return
    
    # 尝试解析URL并提取数据
    parsed = parse_feishu_url(feishu_url)
    if not parsed:
        print(json.dumps({
            "status": "error",
            "message": "无法解析链接，请确认是飞书文档链接（docx或wiki格式）"
        }))
        return
    
    print(json.dumps({
        "status": "importing",
        "message": f"正在从飞书文档导入持仓数据...",
        "doc_type": parsed[0],
        "doc_token": parsed[1]
    }))

def main():
    args = sys.argv[1:]
    
    if not args or args[0] == "list":
        cmd_list()
    elif args[0] == "add" and len(args) >= 3:
        cmd_add(args[1], args[2], args[3] if len(args) > 3 else "")
    elif args[0] == "remove" and len(args) >= 2:
        cmd_remove(args[1])
    elif args[0] == "clear":
        cmd_clear()
    elif args[0] == "holder" and len(args) >= 2:
        cmd_set_holder(" ".join(args[1:]))
    elif args[0] == "setup":
        cmd_setup(args[1] if len(args) > 1 else "")
    else:
        print(__doc__)

if __name__ == "__main__":
    main()
