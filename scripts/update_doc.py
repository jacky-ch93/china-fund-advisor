#!/usr/bin/env python3
"""
更新飞书持仓文档 - 每日盘后自动调用
读取当前持仓，对比今日数据，更新文档表格
"""

import json
import sys
import subprocess
from datetime import datetime

SKILL_DIR = "/root/.openclaw/workspace-feishu-investment/skills/china-fund-advisor"
PORTFOLIO_FILE = f"{SKILL_DIR}/portfolio.json"
DOC_TOKEN = "BltvdVn1moGnOAxT3Qtceg15nqg"  # 飞书文档token

def get_fund_realtime_data():
    """获取基金实时数据（今日净值/涨跌幅）"""
    script = f"{SKILL_DIR}/scripts/fund_data.py"
    try:
        result = subprocess.run(
            ["python3", script],
            capture_output=True, text=True, timeout=90,
            cwd=SKILL_DIR
        )
        if result.stdout:
            return json.loads(result.stdout.strip())
    except:
        pass
    return []

def load_portfolio():
    try:
        with open(PORTFOLIO_FILE, 'r') as f:
            return json.load(f)
    except:
        return {"funds": [], "holder": ""}

def get_today_str():
    return datetime.now().strftime('%Y-%m-%d %H:%M')

def build_doc_content(portfolio, funds_data, market):
    """构建文档markdown内容"""
    holder = portfolio.get("holder", "陈昊")
    funds_config = portfolio.get("funds", [])
    fund_dict = {f["code"]: f for f in funds_data}
    
    # 构建表格行（7列）
    total_amount = 0
    total_profit = 0
    
    rows = []
    for fc in funds_config:
        code = fc["code"]
        fr = fund_dict.get(code, {})
        amount = float(fc.get("amount", 0))
        name = fc.get("name", code)
        
        # 今日数据（优先用配置中手动填入的值，否则用系统抓取）
        today_chg = fr.get("change_pct", 0)
        today_nav = fr.get("nav")
        # 尝试从配置中读手动填入的今日收益
        today_profit = float(fc.get("today_profit")) if fc.get("today_profit") is not None else None
        if today_profit is None and today_chg and amount:
            today_profit = amount * today_chg / 100
        elif today_profit is None:
            today_profit = 0
        
        # 累计持有数据
        profit = float(fc.get("profit", 0))
        profit_rate = fc.get("profit_rate", 0)
        
        total_amount += amount
        total_profit += profit
        
        # 当日收益率：净值日期必须是今天或昨天（交易日）才填入，否则显示—
        from datetime import datetime, timedelta
        nav_date_str = fr.get("nav_date", "")
        today_str = datetime.now().strftime('%Y-%m-%d')
        yesterday_str = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
        is_recent = nav_date_str in (today_str, yesterday_str)
        prev_day_rate = f"{today_chg:+.2f}" if (today_chg and is_recent) else "—"
        today_profit_str = f"{'+' if today_profit >= 0 else ''}{today_profit:.2f}"
        
        rows.append([
            name,
            code,
            f"¥{amount:,.2f}",
            f"{'+' if profit >= 0 else ''}{profit:.2f}",
            f"{profit_rate:+.2f}%" if profit_rate else "N/A",
            prev_day_rate,
            today_profit_str
        ])
    
    # 汇总行
    summary_rate = (total_profit / total_amount * 100) if total_amount > 0 else 0
    
    # markdown表格
    lines = []
    lines.append(f"# {holder}基金持仓 - 实时追踪")
    lines.append("")
    lines.append(f"> 文档更新时间：{get_today_str()}")
    lines.append(f"> 数据来源：支付宝基金持仓 / akshare")
    lines.append(f"> 说明：本页'当日收益率'、'当日收益金额'由系统每日20:00自动更新（数据为上一交易日实际数据，供次日盘前参考）")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## 基本信息")
    lines.append("")
    lines.append(f"- **持有人**：{holder}")
    lines.append(f"- **总持仓金额**：¥{total_amount:,.2f}")
    lines.append(f"- **总持有收益**：{'+' if total_profit >= 0 else ''}¥{total_profit:.2f}")
    lines.append(f"- **整体收益率**：{summary_rate:+.2f}%")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## 持仓明细")
    lines.append("")
    lines.append("> ⚠️ 以下两列每日20:00自动更新（数据为上一交易日实际数据，供次日盘前参考）")
    lines.append("")
    lines.append("| 基金名称 | 基金代码 | 持有金额（元） | 持有收益（元） | 持有收益率 | 当日收益率（%） | 当日收益金额（元） |")
    lines.append("|----------|----------|--------------|--------------|----------|--------------|----------------|")
    for row in rows:
        lines.append(f"| {' | '.join(str(x) for x in row)} |")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append(f"*本报告生成时间：{get_today_str()}*")
    
    return "\n".join(lines)

def main():
    print("=== 更新飞书文档 ===", file=sys.stderr)
    
    # 1. 加载持仓
    portfolio = load_portfolio()
    
    # 2. 获取今日数据
    print("获取今日基金数据...", file=sys.stderr)
    funds_data = get_fund_realtime_data()
    
    # 3. 构建内容
    content = build_doc_content(portfolio, funds_data, {})
    print(f"文档内容已构建，共{len(content)}字符", file=sys.stderr)
    
    # 4. 输出JSON给agent调用飞书API
    result = {
        "doc_token": DOC_TOKEN,
        "content": content,
        "funds_count": len(portfolio.get("funds", [])),
        "updated_at": get_today_str()
    }
    print(json.dumps(result, ensure_ascii=False))

if __name__ == "__main__":
    main()
