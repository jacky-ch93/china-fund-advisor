#!/usr/bin/env python3
"""
持仓管理脚本 - 增删改基金持仓
首次使用：若未配置持仓（portfolio.json不存在），返回 setup_required 引导信息

用法:
  python3 portfolio.py add 000001 10000 "混合基金"
  python3 portfolio.py remove 000001
  python3 portfolio.py list
  python3 portfolio.py clear
  python3 portfolio.py setup_feishu <feishu_doc_url>   # 从飞书文档导入
  python3 portfolio.py setup_local                      # 创建本地文件管理
  python3 portfolio.py ask_setup                         # 首次引导：询问存储方式
"""

import json
import sys
import os
import re

PORTFOLIO_FILE = "/root/.openclaw/workspace-feishu-investment/skills/china-fund-advisor/portfolio.json"
LOCAL_PORTFOLIO_MD = "/root/.openclaw/workspace-feishu-investment/skills/china-fund-advisor/portfolio.md"
FEISHU_WIKI_RE = re.compile(r'wiki/([A-Za-z0-9]+)')
FEISHU_DOCX_RE = re.compile(r'docx/([A-Za-z0-9]+)')

def get_default_portfolio():
    return {
        "version": "1.0",
        "storage": "local",  # "feishu" or "local"
        "feishu_doc_token": None,
        "updated_at": None,
        "holder": None,
        "funds": []
    }

def load_portfolio():
    try:
        if os.path.exists(PORTFOLIO_FILE):
            with open(PORTFOLIO_FILE, 'r') as f:
                data = json.load(f)
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
            "action": "ask_setup",
            "message": (
                "首次使用，需要先配置你的持仓存储方式。\n\n"
                "请选择存储方式：\n"
                "1️⃣ 回复「飞书」— 使用飞书文档存储（推荐）：助手创建模板文档，你填入数据后保存\n"
                "2️⃣ 回复「本地」— 使用本地文件存储：助手创建本地持仓文件管理\n\n"
                "请直接回复「飞书」或「本地」选择存储方式。"
            )
        }, ensure_ascii=False))
        return
    
    funds = data.get("funds", [])
    storage = data.get("storage", "local")
    result = {
        "status": "ok",
        "holder": data.get("holder"),
        "storage": storage,
        "feishu_doc_token": data.get("feishu_doc_token"),
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

def cmd_setup_feishu(feishu_url=""):
    """
    配置飞书文档存储：
    1. 解析URL并验证
    2. 创建配置记录
    3. 返回创建模板文档的指令
    """
    if not feishu_url:
        print(json.dumps({
            "status": "setup_required",
            "action": "provide_feishu_url",
            "message": (
                "请提供你的飞书文档链接（可以是空白文档或现有持仓文档）。\n\n"
                "如果你还没有创建文档，可以直接给我任意一个飞书文档链接，"
                "助手会帮你创建模板。或者先回复「跳过」用本地文件方式。"
            )
        }, ensure_ascii=False))
        return
    
    parsed = parse_feishu_url(feishu_url)
    if not parsed:
        print(json.dumps({
            "status": "error",
            "message": "无法解析链接，请确认是飞书文档链接（docx或wiki格式）"
        }))
        return
    
    doc_type, doc_token = parsed
    
    # 创建配置
    data = get_default_portfolio()
    data["storage"] = "feishu"
    data["feishu_doc_token"] = doc_token
    data["feishu_doc_type"] = doc_type
    save_portfolio(data)
    
    print(json.dumps({
        "status": "ok",
        "storage": "feishu",
        "doc_type": doc_type,
        "doc_token": doc_token,
        "message": (
            "✅ 飞书文档配置成功！\n\n"
            "请前往你的飞书文档，在文档中添加以下格式的持仓信息：\n\n"
            "| 基金代码 | 基金名称 | 持仓金额（元） |\n"
            "|---------|---------|--------------|\n"
            "| 012922 | 易方达全球成长精选混合(QDII)C | 47179 |\n"
            "| 017193 | 天弘中证工业有色金属主题ETF联接C | 22343 |\n"
            "...（按实际持仓填写）\n\n"
            "填好后回复「已完成」，助手会读取并导入数据。"
        )
    }, ensure_ascii=False))

def cmd_setup_local():
    """
    配置本地文件存储：创建空白持仓模板
    """
    data = get_default_portfolio()
    data["storage"] = "local"
    save_portfolio(data)
    
    # 创建本地持仓模板
    template = """# 基金持仓记录

> 本文件由基金智能投顾助手管理，请勿手动修改格式

## 基本信息
- 持有人：（请填写）
- 更新时间：（自动）

## 持仓明细

| 基金代码 | 基金名称 | 持仓金额（元） | 备注 |
|---------|---------|--------------|------|
| （请填写） | （请填写） | （请填写） | |

## 合计
- 总持仓金额：¥（请填写）
- 持有收益：¥（请填写）

---

格式说明：请按上述表格格式填写基金代码、名称和持仓金额，多只基金请添加更多行。
"""
    
    try:
        with open(LOCAL_PORTFOLIO_MD, 'w') as f:
            f.write(template)
    except:
        pass
    
    print(json.dumps({
        "status": "ok",
        "storage": "local",
        "message": (
            "✅ 本地文件存储配置成功！\n\n"
            "已创建本地持仓文件，请直接通过助手命令添加持仓：\n\n"
            "示例：\n"
            "添加持仓：012922 47179 易方达全球成长精选混合(QDII)C\n"
            "添加持仓：017193 22343 天弘中证工业有色金属主题ETF联接C\n\n"
            "助手会读取并管理你的持仓数据。"
        )
    }, ensure_ascii=False))

def cmd_ask_setup():
    """返回首次引导信息"""
    print(json.dumps({
        "status": "setup_required",
        "action": "ask_setup",
        "message": (
            "🔧 首次使用，需要配置持仓存储方式\n\n"
            "请选择：\n\n"
            "1️⃣ 回复「飞书」— 使用飞书文档存储（推荐）\n"
            "   · 助手创建持仓模板文档\n"
            "   · 你填入基金代码/金额后保存\n"
            "   · 每日盘后自动更新文档\n\n"
            "2️⃣ 回复「本地」— 使用本地文件存储\n"
            "   · 完全离线，数据保留在服务器\n"
            "   · 通过文字命令管理持仓\n\n"
            "请直接回复「飞书」或「本地」"
        )
    }, ensure_ascii=False))

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
    elif args[0] == "setup_feishu":
        cmd_setup_feishu(args[1] if len(args) > 1 else "")
    elif args[0] == "setup_local":
        cmd_setup_local()
    elif args[0] == "ask_setup":
        cmd_ask_setup()
    else:
        print(__doc__)

if __name__ == "__main__":
    main()
