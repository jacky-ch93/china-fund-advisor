#!/usr/bin/env python3
"""
市场数据获取脚本 - 盘前/盘后分析用
优先akshare → 备用Sina API → 缓存
新增：外围市场(美股)、汇率、大宗商品
"""

import json
import sys
import signal
import urllib.request
import re
from datetime import datetime, date

CACHE_FILE = "/root/.openclaw/workspace-feishu-investment/skills/china-fund-advisor/.market_cache.json"

def load_cache():
    try:
        with open(CACHE_FILE, 'r') as f:
            return json.load(f)
    except:
        return {}

def save_cache(data):
    try:
        with open(CACHE_FILE, 'w') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except:
        pass

def fetch_sina(symbol, timeout=8):
    """通用新浪API获取器"""
    try:
        url = f"https://hq.sinajs.cn/list={symbol}"
        req = urllib.request.Request(url, headers={
            'User-Agent': 'Mozilla/5.0',
            'Referer': 'https://finance.sina.com.cn'
        })
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = resp.read().decode('gbk')
            m = re.search(r'"([^"]*)"', data)
            if m and m.group(1).strip():
                return m.group(1).strip()
    except:
        pass
    return None

def get_us_market():
    """外围市场 - 美股/外汇/大宗/A50"""
    result = {"us": [], "forex": {}, "commodities": {}, "a50": None}
    
    # 美股指数 via Sina int_*
    us_symbols = {
        'int_sp500': ('标普500', 'US'),
        'int_nasdaq': ('纳斯达克', 'US'),
        'int_dji': ('道琼斯', 'US'),
    }
    
    for sym, (name, region) in us_symbols.items():
        raw = fetch_sina(sym)
        if raw:
            parts = raw.split(',')
            try:
                if len(parts) >= 4:
                    price = float(parts[1])
                    change = float(parts[2])
                    pct = float(parts[3])
                    result["us"].append({
                        "name": name,
                        "price": price,
                        "change": change,
                        "change_pct": pct
                    })
            except:
                pass
    
    # 外汇 via Sina
    forex_symbols = {
        'USDCNY': ('美元/人民币', 'CNY'),
        'EURUSD': ('欧元/美元', 'EUR'),
        'GBPUSD': ('英镑/美元', 'GBP'),
    }
    
    for sym, (name, ccy) in forex_symbols.items():
        raw = fetch_sina(sym)
        if raw:
            parts = raw.split(',')
            try:
                # 格式: 时间,当前,开,高,量,昨收,...
                if len(parts) >= 9:
                    curr = float(parts[1])
                    prev = float(parts[5])  # 昨收
                    if prev > 0:
                        pct = round((curr - prev) / prev * 100, 4)
                        result["forex"][sym] = {
                            "name": name,
                            "current": curr,
                            "prev_close": prev,
                            "change_pct": pct
                        }
            except:
                pass
    
    # 大宗商品 via Sina hf_*
    # 格式: [0]当前, [1]结算(空), [2]开, [3]高, [4]低, [5]昨结算, [6]时间,...
    commodity_symbols = {
        'hf_GC': ('纽约黄金', 'GC'),
        'hf_SI': ('纽约白银', 'SI'),
        'hf_CL': ('WTI原油', 'CL'),
    }
    
    for sym, (name, code) in commodity_symbols.items():
        raw = fetch_sina(sym)
        if raw:
            parts = raw.split(',')
            try:
                if len(parts) >= 9:
                    curr = float(parts[0])
                    prev = float(parts[5])  # 昨结算
                    if prev and prev > 0:
                        pct = round((curr - prev) / prev * 100, 2)
                        result["commodities"][code] = {
                            "name": name,
                            "current": curr,
                            "prev": prev,
                            "change_pct": pct
                        }
            except:
                pass
    
    # A50期货 via Sina hf_*
    a50_raw = fetch_sina('hf_A50') or fetch_sina('hf_CHA50')
    if a50_raw and len(a50_raw) > 5:
        parts = a50_raw.split(',')
        try:
            if len(parts) >= 6:
                curr = float(parts[0])
                prev = float(parts[5])  # 昨结算
                if prev and prev > 0:
                    pct = round((curr - prev) / prev * 100, 2)
                    result["a50"] = {
                        "name": "A50指数",
                        "current": curr,
                        "prev_close": prev,
                        "change_pct": pct
                    }
        except:
            pass
    
    return result

def get_ab_market_via_akshare():
    """akshare - A股大盘（指数+涨停+行业）"""
    import akshare as ak
    
    today = date.today().strftime('%Y%m%d')
    result = {
        "indices": [],
        "hot_sectors": [],
        "cold_sectors": [],
        "zt_count": 0,
        "zt_pool": [],
    }
    
    # 指数 (东方财富)
    try:
        df = ak.stock_zh_index_spot_em()
        indices_map = {
            '000001': '上证指数',
            '399001': '深证成指',
            '399006': '创业板指',
            '000688': '科创50',
            '000300': '沪深300'
        }
        for code, name in indices_map.items():
            row = df[df['代码'] == code]
            if not row.empty:
                result["indices"].append({
                    "name": name,
                    "price": float(row.iloc[0]['最新价']),
                    "change_pct": float(row.iloc[0]['涨跌幅']),
                })
    except Exception as e:
        print(f"指数获取失败: {e}", file=sys.stderr)
    
    # 涨停股
    try:
        zt = ak.stock_zt_pool_em(date=today)
        result["zt_count"] = len(zt)
        result["zt_pool"] = [
            {"code": r['代码'], "name": r['名称'], "stats": r['涨停统计']}
            for _, r in zt.head(10).iterrows()
        ]
    except Exception as e:
        print(f"涨停池获取失败: {e}", file=sys.stderr)
    
    # 行业板块
    try:
        ind = ak.stock_board_industry_name_em()
        ind = ind.sort_values('涨跌幅', ascending=False)
        result["hot_sectors"] = [
            {"name": r['板块名称'], "change_pct": float(r['涨跌幅'])}
            for _, r in ind.head(5).iterrows()
        ]
        result["cold_sectors"] = [
            {"name": r['板块名称'], "change_pct": float(r['涨跌幅'])}
            for _, r in ind.tail(5).iterrows()
        ]
    except Exception as e:
        print(f"行业数据获取失败: {e}", file=sys.stderr)
    
    return result

def get_ab_market_via_sina():
    """Sina API - A股指数备用方案"""
    result = {
        "indices": [],
        "hot_sectors": [],
        "cold_sectors": [],
        "zt_count": 0,
        "zt_pool": [],
    }
    
    index_codes = [
        ('sh000001', '上证指数'),
        ('sz399001', '深证成指'),
        ('sz399006', '创业板指'),
        ('sh000688', '科创50'),
        ('sh000300', '沪深300'),
    ]
    
    for sid, name in index_codes:
        raw = fetch_sina(sid)
        if raw:
            parts = raw.split(',')
            try:
                # 格式: 名称,当前价,昨收,开盘价,最高,最低,...
                # parts[1]=当前(竞价价), parts[2]=昨收
                if len(parts) >= 6:
                    price = float(parts[1])
                    prev = float(parts[2])
                    if price > 0 and prev > 0:
                        pct = round((price - prev) / prev * 100, 2)
                        result["indices"].append({
                            "name": name,
                            "price": price,
                            "change_pct": pct
                        })
            except:
                pass
    
    return result

def build_sentiment(result):
    """根据数据构建市场情绪"""
    zt_count = result.get("zt_count", 0)
    indices = result.get("indices", [])
    
    if indices:
        avg_pct = sum(i["change_pct"] for i in indices) / len(indices)
    else:
        avg_pct = 0
    
    if zt_count >= 100:
        sentiment = "🔥极热"
    elif zt_count >= 80:
        sentiment = "🔥偏热"
    elif zt_count >= 50:
        sentiment = "📊正常"
    elif zt_count >= 30:
        sentiment = "❄️偏冷"
    else:
        sentiment = "❄️极冷"
    
    if avg_pct > 1:
        sentiment += " / 普涨"
    elif avg_pct < -1:
        sentiment += " / 普跌"
    elif avg_pct > 0.3:
        sentiment += " / 偏强"
    elif avg_pct < -0.3:
        sentiment += " / 偏弱"
    else:
        sentiment += " / 震荡"
    
    result["market_sentiment"] = sentiment
    return result

def main():
    print("正在获取市场数据...", file=sys.stderr)
    
    # 1. 先获取外围市场数据（独立快速）
    print("获取外围市场...", file=sys.stderr)
    global_data = get_us_market()
    
    # 2. 尝试akshare获取A股数据
    ab_data = {}
    try:
        def timeout_handler(signum, frame):
            raise TimeoutError("akshare超时")
        
        signal.signal(signal.SIGALRM, timeout_handler)
        signal.alarm(25)
        
        try:
            ab_data = get_ab_market_via_akshare()
            signal.alarm(0)
            print(f"akshare成功: {len(ab_data.get('indices', []))}个指数, {ab_data.get('zt_count', 0)}只涨停", file=sys.stderr)
        except TimeoutError:
            print("akshare超时，跳过", file=sys.stderr)
            signal.alarm(0)
        except Exception as e:
            print(f"akshare异常: {e}", file=sys.stderr)
            signal.alarm(0)
    except:
        pass
    
    # 3. 如果akshare没有指数数据，用Sina备用
    if not ab_data.get("indices"):
        print("尝试Sina API备用...", file=sys.stderr)
        ab_data = get_ab_market_via_sina()
        if ab_data.get("indices"):
            print(f"Sina成功: {len(ab_data['indices'])}个指数", file=sys.stderr)
    
    # 4. 合并结果
    result = {
        "source": "akshare" if ab_data.get("indices") else ("sina" if not ab_data else "none"),
        "time": date.today().strftime('%Y%m%d'),
        **ab_data,
        "外围": global_data.get("us", []),
        "汇率": global_data.get("forex", {}),
        "大宗商品": global_data.get("commodities", {}),
        "a50": global_data.get("a50"),
    }
    build_sentiment(result)
    
    # 5. 保存缓存
    cache_entry = {k: v for k, v in result.items() if k not in ["外围", "汇率", "大宗商品", "a50"]}
    save_cache(cache_entry)
    
    print(json.dumps(result, ensure_ascii=False))

if __name__ == "__main__":
    main()
