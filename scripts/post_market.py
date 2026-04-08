#!/usr/bin/env python3
"""
盘后分析脚本 - 22:30定时执行
输出：今日收益总结 + 热点新闻 + 明日投资机会
"""

import json
import sys
import subprocess
import os
import urllib.request
import re
from datetime import date, datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

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
    except subprocess.TimeoutExpired:
        print(f"脚本{script_name}超时", file=sys.stderr)
    return {}

def get_today():
    result = subprocess.run(
        ["python3", "-c", "from datetime import date; print(date.today().strftime('%Y-%m-%d'))"],
        capture_output=True, text=True
    )
    return result.stdout.strip()

def fetch_news():
    """获取今日市场热点新闻"""
    today_str = date.today().strftime('%Y-%m-%d')
    news_by_cat = {}
    
    categories = [
        ('101', '宏观'),
        ('102', '股市'),
        ('103', '基金'),
    ]
    
    for cat_id, cat_name in categories:
        try:
            url = f'https://newsapi.eastmoney.com/kuaixun/v1/getlist_{cat_id}_ajaxResult_50_1_.html'
            req = urllib.request.Request(url, headers={
                'User-Agent': 'Mozilla/5.0',
                'Referer': 'https://www.eastmoney.com'
            })
            with urllib.request.urlopen(req, timeout=8) as resp:
                data = resp.read().decode('utf-8', errors='replace')
                m = re.search(r'ajaxResult=(\{.*\})', data, re.DOTALL)
                if m:
                    obj = json.loads(m.group(1))
                    lives = obj.get('LivesList', [])
                    # Filter to today's news
                    today_news = [
                        {"title": item.get('title', ''), "time": item.get('showtime', ''), "url": item.get('url_w', '')}
                        for item in lives
                        if item.get('showtime', '').startswith(today_str)
                    ]
                    news_by_cat[cat_name] = today_news
        except Exception as e:
            print(f"新闻获取失败 {cat_name}: {e}", file=sys.stderr)
    
    return news_by_cat

def analyze_fund(fund_info, market_data):
    """分析单只基金的持仓建议"""
    code = fund_info["code"]
    name = fund_info.get("name", code)
    amount = float(fund_info.get("amount", 0))
    chg = fund_info.get("change_pct", 0)
    
    hot_names = " ".join([s["name"] for s in market_data.get("hot_sectors", [])])
    sentiment = market_data.get("market_sentiment", "")
    
    # 判断基金类型
    is_semiconductor = any(k in name for k in ["半导体", "芯片", "电子"])
    is_power = any(k in name for k in ["电力", "电网", "公用事业", "能源"])
    is_medical = any(k in name for k in ["医药", "医疗", "生物"])
    is_qdii = any(k in name for k in ["QDII", "全球", "沪港深", "海外", "港股"])
    is_industrial = any(k in name for k in ["工业", "有色", "材料", "金属"])
    
    action = "持有"
    reason = ""
    
    if chg <= -2:
        action = "关注减仓"
        reason = f"单日下跌{chg:.2f}%，关注是否破支撑"
    elif chg >= 2:
        action = "可适度止盈"
        reason = f"单日上涨{chg:.2f}%，高位注意回撤风险"
    else:
        reason = f"今日{chg:+.2f}%，{'短期承压' if chg < 0 else '表现正常'}"
    
    if is_semiconductor:
        if any(k in hot_names for k in ['半导', '电子']):
            action = "持有/持有+"
            reason = "半导体板块强势，延续持有"
        else:
            action = "持有"
            reason = "半导体波动大，高位注意回撤"
    elif is_power:
        action = "持有"
        reason = "电力公用事业防御性强，长期持有"
    elif is_medical:
        action = "持有/长线布局" if chg < 0 else "持有"
        reason = "医药短期偏弱，长周期布局思路"
    elif is_qdii:
        action = "持有"
        reason = "QDII分散风险，长期配置思路"
    elif is_industrial:
        action = "持有"
        reason = "工业有色题材，区间操作"
    
    return {"code": code, "name": name, "amount": amount, "change_pct": chg, "action": action, "reason": reason}

def build_tomorrow_outlook(market, news, analyzed):
    """构建明日投资展望"""
    indices = market.get("indices", [])
    sentiment = market.get("market_sentiment", "")
    hot = market.get("hot_sectors", [])[:3]
    cold = market.get("cold_sectors", [])[:3]
    
    # 市场整体判断
    if indices:
        avg_pct = sum(i.get("change_pct", 0) for i in indices) / len(indices)
    else:
        avg_pct = 0
    
    outlook_parts = []
    
    # 1. 今日总结
    outlook_parts.append(f"**今日市场**: A股整体{'大涨' if avg_pct > 1.5 else '上涨' if avg_pct > 0.5 else '震荡'}，科创/创业/深证强势领涨。")
    
    # 2. 关键新闻摘要
    macro_news = news.get("宏观", [])
    stock_news = news.get("股市", [])
    if macro_news:
        key_news = [n['title'] for n in macro_news[:3]]
        outlook_parts.append(f"**今日宏观**: {'；'.join(key_news)}。")
    
    # 3. 明日关注方向
    tomorrow_focus = []
    if avg_pct > 1:
        tomorrow_focus.append("市场大涨后有整理需求，忌追高")
    if any('科创' in i['name'] or '创业' in i['name'] for i in indices if avg_pct > 1):
        tomorrow_focus.append("科技/成长板块注意短线回调风险")
    if hot:
        tomorrow_focus.append(f"今日强势板块（{'/'.join(h['name'] for h in hot)}）可关注延续性")
    if cold:
        tomorrow_focus.append(f"弱势板块（{'/'.join(c['name'] for c in cold)}）谨慎抄底")
    
    # 医药/电力防御板块
    has_defensive = any(f['change_pct'] < -0.5 for f in analyzed if any(k in f['name'] for k in ['医药', '电力']))
    if has_defensive:
        tomorrow_focus.append("医药/电力等防御板块可中长线布局")
    
    outlook_parts.append("**明日关注**: " + " / ".join(tomorrow_focus) if tomorrow_focus else "**明日关注**: 市场暂无明确方向，观望为主")
    
    return "\n".join(outlook_parts)

def main():
    print("=== 盘后分析开始 ===", file=sys.stderr)
    
    # 1. 并行获取：市场数据 + 新闻
    print("获取市场数据...", file=sys.stderr)
    print("获取热点新闻...", file=sys.stderr)
    
    with ThreadPoolExecutor(max_workers=2) as ex:
        f_market = ex.submit(run_script, "market.py", 35)
        f_news = ex.submit(fetch_news)
        
        market = f_market.result()
        news = f_news.result()
    
    # 2. 获取持仓基金数据（并行）
    print("获取持仓数据...", file=sys.stderr)
    funds_raw = run_script("fund_data.py", 30)
    funds_raw_dict = {f["code"]: f for f in funds_raw} if isinstance(funds_raw, list) else {}
    
    # 3. 加载持仓配置
    portfolio = {}
    try:
        with open(PORTFOLIO_FILE, 'r') as f:
            portfolio = json.load(f)
    except:
        pass
    
    funds_config = portfolio.get("funds", [])
    holder = portfolio.get("holder", "")
    today = get_today()
    
    # 4. 构建基金完整信息
    analyzed = []
    total_amount = 0
    total_estimate = 0
    
    for fc in funds_config:
        code = fc["code"]
        fr = funds_raw_dict.get(code, {})
        fund_info = {
            "code": code,
            "name": fc.get("name", code),
            "amount": float(fc.get("amount", 0)),
            "nav": fr.get("nav"),
            "nav_date": fr.get("nav_date", ""),
            "change_pct": fr.get("change_pct", 0),
        }
        fund_info.update(analyze_fund(fund_info, market))
        analyzed.append(fund_info)
        total_amount += fund_info["amount"]
        if fund_info["change_pct"] and fund_info["amount"]:
            total_estimate += fund_info["amount"] * fund_info["change_pct"] / 100
    
    # 5. 生成报告
    report = []
    report.append(f"# 📉 盘后总结 {today}")
    
    # 大盘表现
    report.append("")
    report.append("## 今日大盘")
    indices = market.get("indices", [])
    sentiment = market.get("market_sentiment", "数据不可用")
    
    if indices:
        for idx in indices:
            pct = idx.get("change_pct", 0)
            emoji = "🔴" if pct < 0 else "🟢"
            report.append(f"{emoji} **{idx['name']}**: {idx.get('price', 'N/A'):,.2f} ({pct:+.2f}%)")
        report.append(f"**市场情绪**: {sentiment}")
    else:
        report.append(f"指数数据暂不可用（今日网络波动）")
        report.append(f"**涨停家数**: {market.get('zt_count', 'N/A')}只")
    
    # 热点新闻
    report.append("")
    report.append("## 📰 今日热点（22:00前）")
    
    all_news = []
    for cat, news_list in news.items():
        for n in news_list[:3]:
            all_news.append((n['time'][11:16], n['title']))  # time HH:MM, title
    
    # Deduplicate by title
    seen = set()
    for t, title in all_news:
        if title not in seen:
            seen.add(title)
            report.append(f"- [{t}] {title[:55]}{'...' if len(title) > 55 else ''}")
        if len(seen) >= 8:
            break
    
    if not all_news:
        report.append("（新闻数据暂未更新，明日早参提供）")
    
    # 行业表现
    hot = market.get("hot_sectors", [])
    cold = market.get("cold_sectors", [])
    if hot or cold:
        report.append("")
        report.append("## 行业表现")
        if hot:
            report.append("**今日强势**: " + " / ".join(f"{s['name']}({s['change_pct']:+.2f}%)" for s in hot[:3]))
        if cold:
            report.append("**今日弱势**: " + " / ".join(f"{s['name']}({s['change_pct']:+.2f}%)" for s in cold[:3]))
    
    # 持仓基金
    report.append("")
    report.append("## 持仓基金今日表现")
    for f in analyzed:
        nav_str = f"{f['nav']:.4f}" if f['nav'] else "N/A"
        est = f["amount"] * f["change_pct"] / 100 if f["change_pct"] and f["amount"] else 0
        emoji = "🟢" if f["change_pct"] > 0 else "🔴" if f["change_pct"] < 0 else "⚪"
        report.append(f"{emoji} **{f['name']}**({f['code']}): {nav_str} ({f['change_pct']:+.2f}%) 估算{'+' if est >= 0 else ''}¥{est:.2f} → {f['action']}")
    
    if total_amount > 0:
        report.append(f"**组合估算**: {'+' if total_estimate >= 0 else ''}¥{total_estimate:.2f} ({(total_estimate/total_amount)*100:+.2f}%)")
    
    # 涨停股
    zt_pool = market.get("zt_pool", [])
    if zt_pool:
        report.append("")
        report.append("## 今日涨停（部分）")
        for zt in zt_pool[:5]:
            report.append(f"- {zt['name']}({zt['code']}): {zt['stats']}")
    
    # 明日展望
    report.append("")
    report.append("## 📅 明日展望与机会")
    tomorrow_outlook = build_tomorrow_outlook(market, news, analyzed)
    report.append(tomorrow_outlook)
    
    # 仓位提醒
    report.append("")
    report.append(f"**持仓提醒**: 总计¥{total_amount:,.0f}，整体{'偏重' if total_amount > 100000 else '适中'}，建议留足子弹")
    
    report.append("")
    report.append("---")
    report.append("🤖 *数据来源akshare/同花顺/东方财富，存在延迟；基金净值为昨日估算，支付宝数据更准确；投资建议仅供参考，不构成操作建议*")
    
    output = "\n".join(report)
    print(output)
    
    # 保存
    try:
        with open(f"{SKILL_DIR}/.last_post_market.txt", 'w') as f:
            f.write(output)
    except:
        pass

if __name__ == "__main__":
    main()
