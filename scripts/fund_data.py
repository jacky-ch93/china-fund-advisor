#!/usr/bin/env python3
"""
基金数据获取脚本 - 获取基金净值、涨跌
支持多源fallback，并行获取加速
"""

import json
import sys
import os
from datetime import date
from concurrent.futures import ThreadPoolExecutor, as_completed

PORTFOLIO_FILE = "/root/.openclaw/workspace-feishu-investment/skills/china-fund-advisor/portfolio.json"

def load_portfolio():
    try:
        with open(PORTFOLIO_FILE, 'r') as f:
            return json.load(f)
    except:
        return {"funds": []}

def get_fund_via_akshare(fund_code):
    """通过akshare获取单只基金数据"""
    import akshare as ak
    
    result = {"code": fund_code, "name": "", "nav": None, "nav_date": "", "change_pct": 0, "source": "akshare"}
    
    try:
        df_nav = ak.fund_open_fund_info_em(symbol=fund_code)
        if not df_nav.empty:
            latest = df_nav.iloc[-1]
            nav_date_raw = latest.get('净值日期', '')
            if hasattr(nav_date_raw, 'strftime'):
                result["nav_date"] = nav_date_raw.strftime('%Y-%m-%d')
            else:
                result["nav_date"] = str(nav_date_raw)
            result["nav"] = float(latest.get('单位净值', 0))
            result["change_pct"] = float(latest.get('日增长率', 0))
    except Exception as e:
        print(f"净值获取失败 {fund_code}: {e}", file=sys.stderr)
    
    return result

def get_fund_nav_backup(fund_code):
    """备用：通过fund_open_fund_daily_em获取基金净值"""
    import akshare as ak
    
    try:
        df = ak.fund_open_fund_daily_em(symbol=fund_code)
        if not df.empty:
            latest = df.iloc[-1]
            return {
                "nav": float(latest.get('单位净值', 0)),
                "nav_date": str(latest.get('日期', '')),
            }
    except:
        pass
    return {"nav": None, "nav_date": ""}

def get_single_fund(code):
    """单只基金获取"""
    code = code.strip()
    if not code:
        return None
    
    # 优先akshare
    try:
        data = get_fund_via_akshare(code)
        if data.get("nav"):
            return data
    except Exception:
        pass
    
    # 备选
    try:
        nav_data = get_fund_nav_backup(code)
        if nav_data.get("nav"):
            return {
                "code": code, "name": "", "nav": nav_data["nav"],
                "nav_date": nav_data["nav_date"], "change_pct": 0, "source": "ths"
            }
    except Exception:
        pass
    
    return {"code": code, "name": "", "nav": None, "nav_date": "", "change_pct": 0, "source": "none"}

def get_funds_parallel(codes, max_workers=5):
    """并行获取多只基金数据"""
    results = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_code = {executor.submit(get_single_fund, code): code for code in codes}
        for future in as_completed(future_to_code):
            result = future.result()
            if result:
                results.append(result)
    return results

def main():
    portfolio = load_portfolio()
    codes = [f["code"] for f in portfolio.get("funds", [])]
    
    if not codes:
        print(json.dumps({"error": "无持仓基金，请先录入"}))
        return
    
    funds_data = get_funds_parallel(codes, max_workers=5)
    print(json.dumps(funds_data, ensure_ascii=False))

if __name__ == "__main__":
    main()
