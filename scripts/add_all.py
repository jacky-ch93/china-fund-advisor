import json

PORTFOLIO_FILE = "/root/.openclaw/workspace-feishu-investment/skills/china-fund-advisor/portfolio.json"

funds = [
    {"code": "012922", "name": "易方达全球成长精选混合(QDII)C", "amount": 47179.01, "profit": 9679.01, "profit_rate": 25.81},
    {"code": "017731", "name": "嘉实全球产业升级股票(QDII)C", "amount": 7371.91, "profit": 871.91, "profit_rate": 13.41},
    {"code": "025833", "name": "天弘中证电网设备主题指数C", "amount": 10228.58, "profit": 228.58, "profit_rate": 2.29},
    {"code": "016186", "name": "广发电力公用事业ETF联接C", "amount": 4884.47, "profit": -115.53, "profit_rate": -2.31},
    {"code": "025209", "name": "永赢先锋半导体智选混合C", "amount": 18483.90, "profit": -1516.10, "profit_rate": -7.58},
    {"code": "017193", "name": "天弘中证工业有色金属主题ETF联接C", "amount": 22342.51, "profit": -2416.71, "profit_rate": -9.76},
    {"code": "018156", "name": "创金合信全球医药生物股票(QDII)C", "amount": 1720.51, "profit": -279.49, "profit_rate": -13.97},
    {"code": "012183", "name": "广发沪港深精选混合C", "amount": 10187.13, "profit": -4812.87, "profit_rate": -32.09},
]

data = {
    "version": "1.0",
    "holder": "陈昊",
    "updated_at": "2026-04-07",
    "funds": funds
}

with open(PORTFOLIO_FILE, 'w') as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

total = sum(f["amount"] for f in funds)
total_profit = sum(f["profit"] for f in funds)
print(f"已录入{len(funds)}只基金，总持仓¥{total:,.2f}，总收益{'+' if total_profit >= 0 else ''}¥{total_profit:.2f}")
