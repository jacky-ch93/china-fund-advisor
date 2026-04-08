#!/usr/bin/env python3
"""
盘前分析脚本 - 08:30定时执行
输出：完整盘前分析（外围市场 + A股展望 + 持仓参考）
"""

import json
import sys
import subprocess
import os

SKILL_DIR = "/root/.openclaw/workspace-feishu-investment/skills/china-fund-advisor"
PORTFOLIO_FILE = f"{SKILL_DIR}/portfolio.json"

def run_script(script_name, timeout=30):
    script_path = f"{SKILL_DIR}/scripts/{script_name}"
    try:
        result = subprocess.run(
            ["python3", script_path],
            capture_output=True, text=True, timeout=timeout,
            cwd=SKILL_DIR
        )
        if result.stdout:
            return json.loads(result.stdout.strip())
    except Exception as e:
        print(f"脚本{script_name}失败: {e}", file=sys.stderr)
    return {}

def main():
    print("=== 盘前分析开始 ===", file=sys.stderr)
    
    # 1. 获取市场数据（包含A股+外围+外汇+大宗）
    print("获取市场数据...", file=sys.stderr)
    market = run_script("market.py", timeout=40)
    
    # 2. 获取持仓基金数据
    print("获取持仓数据...", file=sys.stderr)
    funds = run_script("fund_data.py", timeout=60)
    
    # 3. 生成报告
    today = subprocess.run(
        ["python3", "-c", "from datetime import date; print(date.today().strftime('%Y-%m-%d'))"],
        capture_output=True, text=True
    ).stdout.strip()
    
    report = []
    report.append(f"# 📈 盘前分析 {today}")
    
    # === 1. 外围市场 ===
    us_list = market.get("外围", [])
    if us_list:
        report.append("")
        report.append("## 🌏 外围市场（昨夜收盘）")
        for us in us_list:
            pct = us.get("change_pct", 0)
            emoji = "🟢" if pct >= 0 else "🔴"
            sign = "+" if pct >= 0 else ""
            report.append(f"{emoji} **{us['name']}**: {us.get('price', 'N/A'):,.2f} {sign}{pct:.2f}%")
    
    # === 2. 外汇 ===
    forex = market.get("汇率", {})
    if forex:
        report.append("")
        report.append("## 💱 汇率（美元/离岸人民币）")
        usdcny = forex.get("USDCNY", {})
        if usdcny:
            curr = usdcny.get("current", 0)
            prev = usdcny.get("prev_close", 0)
            pct = usdcny.get("change_pct", 0)
            sign = "+" if pct >= 0 else ""
            emoji = "🟢" if pct < 0 else "🔴"  # CNY stronger when USD/CNY goes down
            report.append(f"{emoji} **美元/人民币**: {curr:.4f}（{sign}{pct:.4f}%）")
    
    # === 3. 大宗商品 ===
    commodities = market.get("大宗商品", {})
    if commodities:
        report.append("")
        report.append("## 🛢️ 大宗商品")
        for code, c in commodities.items():
            pct = c.get("change_pct", 0)
            sign = "+" if pct >= 0 else ""
            emoji = "🟢" if pct >= 0 else "🔴"
            report.append(f"{emoji} **{c['name']}**: {c.get('current', 'N/A')}（{sign}{pct:.2f}%）")
    
    # === 4. A50期货 ===
    a50 = market.get("a50")
    if a50:
        pct = a50.get("change_pct", 0)
        sign = "+" if pct >= 0 else ""
        emoji = "🟢" if pct >= 0 else "🔴"
        report.append(f"{emoji} **{a50['name']}**: {a50.get('current', 'N/A')}（{sign}{pct:.2f}%）")
    
    # === 5. A股大盘 ===
    report.append("")
    report.append("## 🏛️ A股大盘（今日竞价/昨收）")
    indices = market.get("indices", [])
    if indices:
        for idx in indices:
            pct = idx.get("change_pct", 0)
            emoji = "🔴" if pct < 0 else "🟢"
            report.append(f"{emoji} **{idx['name']}**: {idx.get('price', 'N/A'):,.2f}（{pct:+.2f}%）")
    else:
        report.append("指数数据暂不可用")
    
    # 涨停情绪
    zt_count = market.get("zt_count", 0)
    sentiment = market.get("market_sentiment", "")
    zt_note = f"{zt_count}只涨停" if zt_count > 0 else "暂无数据"
    report.append(f"")
    report.append(f"**涨停情绪**: {zt_note} {sentiment}")
    
    # 热门/冷门行业
    sectors = market.get("hot_sectors", [])
    if sectors:
        report.append("")
        report.append("## 🔥 热门行业（昨日）")
        for s in sectors[:5]:
            report.append(f"- {s['name']}: {s['change_pct']:+.2f}%")
    
    # === 6. 持仓基金 ===
    portfolio = {}
    try:
        with open(PORTFOLIO_FILE, 'r') as f:
            portfolio = json.load(f)
    except:
        pass
    
    funds_held = portfolio.get("funds", [])
    if funds_held and funds:
        report.append("")
        report.append("## 💰 持仓基金参考（昨日净值）")
        fund_dict = {f['code']: f for f in funds}
        for held in funds_held:
            code = held.get("code", "")
            amount = held.get("amount", 0)
            fd = fund_dict.get(code, {})
            nav = fd.get("nav")
            chg = fd.get("change_pct", 0)
            nav_str = f"{nav:.4f}" if nav else "N/A"
            sign = "+" if chg >= 0 else ""
            report.append(f"- **{held.get('name', code)}**({code}): 净值{nav_str}（{sign}{chg:.2f}%）持仓¥{amount}")
    
    report.append("")
    report.append("---")
    report.append("*🌏 外围昨夜收盘 | 💱 汇率为实时 | 🏛️ A股为今日竞价/昨涨跌 | 💰 基金净值为昨日估算，仅供参考*")
    
    output = "\n".join(report)
    print(output)
    
    # 保存输出
    try:
        with open(f"{SKILL_DIR}/.last_pre_market.txt", 'w') as f:
            f.write(output)
    except:
        pass

if __name__ == "__main__":
    main()
