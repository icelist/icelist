"""
CEX-DEX 套利模块

架构：
  price_feed  —— 从 DEX (Uniswap/Jupiter) 和 CEX (Binance/OKX) 获取实时报价
  engine      —— 价差计算、利润评估、Gas 成本估算、信号产生
  executor    —— 双边同时执行：链上 swap + 交易所下单
  arb_functions —— 集成到 REGISTRY 的策略入口
"""
