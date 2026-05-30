# Kraken Klash 离线分析工具

> ⚠️ **只做离线模拟，不连真服，不下真单**。
> The Beacon 是 airdrop farming 项目，自动化对真实账户下注 = Sybil 行为，
> 大概率封号 + 没收奖励。这个工具只帮你算明白「该不该下」「下多少不会破产」。

---

## A. 游戏机制拆解（Kraken Klash）

### 1. 这是个什么游戏

The Beacon Season 1 "Goblin's Gambit" 提供两条赚 BCN 的路线：

| 路线 | 风险 | 流程 |
|---|---|---|
| 安全 | 低 | 打 Dungeon → 攒 Umbra Shards → 开 Umbra/Shadow Chest → 拿 BCN |
| 博弈 | 高 | Umbra Shards → 在 Cellar 兑换成 **Gobloonz** → 进 **Kraken Klash** 押注 |

**Kraken Klash** 是一个棋盘式 prediction 小游戏：
- 你押"哪个格子会被随机选中"
- 命中赢 Gobloonz / 直接 BCN
- **关键机制**：每花 1 个 Gobloon，**Kraken Favor** 涨 1（无论输赢）
- Kraken Favor 决定排行榜排名，排行榜决定 770 万 BCN 奖池怎么分

> 所以即便你押注全输，只要花掉 Gobloonz，依然能拿到一部分空投 —— 这是工具里 `airdrop` 配置项存在的根本原因。

参考来源:
[panewslab](https://www.panewslab.com/en/articles/019e6327-55dc-735e-a677-946e134f2b1e),
[odaily](https://www.odaily.news/en/post/5210969),
[gam3s.gg](https://gam3s.gg/news/the-beacon-goblins-gambit-pre-season-1-event/),
[airdrops.io](https://airdrops.io/the-beacon/),
[playtoearn](https://playtoearn.com/news/the-beacon-season-1-goblins-gambit-goes-live-with-77-million-bcn-in-rewards),
[binance square](https://www.binance.com/en-AE/square/post/325236192455970)（信息已重述以符合许可要求）

### 2. 你需要进游戏自己确认的数字

公开资料里**没有**给出 Kraken Klash 的完整赔率表。你需要在游戏里看到再填进 `config.example.yaml`：

| 配置字段 | 含义 | 怎么看 |
|---|---|---|
| `bets[].cost` | 1 注消耗多少 Gobloonz | 下注界面"min bet" |
| `bets[].win_prob` | 命中概率 | 看格子总数。例：6 格里押 1 格 = 1/6 |
| `bets[].payout` | 命中返回多少（含本金） | 界面会显示赔率，如 "5.5x" |
| `airdrop.bcn_per_gobloon_spent` | 估算每花 1 Gobloon 能从空投拿回几个 BCN | 看排行榜 + 奖池分布 |
| `airdrop.gobloon_per_bcn` | 1 BCN 折合多少 Gobloon | 用兑换比 / 市场价折算 |

**示例配置已经按"6 格盘 + 庄家抽水 8%"假设填了占位值**。这只是举例，请改成你看到的真值。

### 3. 必须先想清楚的事

1. **house edge > 0 时，纯赌博必然长期亏。** 任何"下注规律"都不能改变这一点。
2. **唯一的正期望来源**是 airdrop 保底（每注 = 1 Favor）。所以你真正在玩的是「**用最小本金成本最大化 Favor 累积**」，而不是「赢这一把」。
3. 想要正 EV，就要让 `effective_ev_pct >= 0`：
   ```
   effective_ev = bet_ev_per_unit + bcn_per_gobloon_spent * gobloon_per_bcn
   ```
   先用本工具的 `ev` 命令检查这一点。如果配置下"含空投有效 EV"还是负的，**说明这赛季对你来说不值得下注**，安全路线（开宝箱）反而更好。

---

## B. 模拟器使用

### 安装

工具用的全是 stdlib + `pyyaml` + `typer`，主仓库 `requirements.txt` 已包含。

### 三个命令

#### 1) `ev` — 算清楚每种押法的期望

```bash
python -m tools.kraken_klash_sim ev
```

输出示例（用 `config.example.yaml` 占位数）：

```
==================================================================
押法              命中率  实际赔  公平赔     EV%   抽水%  空投+%  有效EV%   说明
------------------------------------------------------------------
single_tile      16.67%    5.50    6.00   -8.32   +8.32   +25.00   +16.68  ✓ 含空投后正 EV
pair             33.33%    2.75    3.00   -8.34   +8.34   +25.00   +16.66  ✓ 含空投后正 EV
half_board       50.00%    1.83    2.00   -8.50   +8.50   +25.00   +16.50  ✓ 含空投后正 EV
==================================================================
```

含空投后正 EV ≠ 你今晚一定赚，**只是说长期挂下去期望为正**。

#### 2) `sim` — 跑某个策略 1 万次会话

```bash
# 平注 single_tile
python -m tools.kraken_klash_sim sim --bet single_tile --strategy flat --units 1

# 马丁格尔（典型自杀策略，跑出来给你看）
python -m tools.kraken_klash_sim sim --bet half_board --strategy martingale --base-units 1 --cap-units 64

# 半凯利（数学最优，但有空投保底时它会因为含空投 EV 修正再下大）
python -m tools.kraken_klash_sim sim --bet single_tile --strategy kelly --factor 0.5
```

输出包含：
- 平均/中位/分位最终余额
- **破产率**（最重要的风险指标）
- 累计 Gobloonz 下注量（= 累计 Kraken Favor）
- **含空投等效价值**（这个是真正的"我赚了多少"）
- ASCII 直方图

#### 3) `compare` — 横向对比所有策略

```bash
python -m tools.kraken_klash_sim compare --bet single_tile
```

一张表对比 6 种策略在同样押法下的破产率 / 期望余额 / 等效价值，挑出最稳的一个。

---

## 内置策略

| 策略 | 思路 | 典型用法 |
|---|---|---|
| `flat` | 每局固定单位数 | 最稳，长期 EV 最贴近理论 |
| `martingale` | 输了翻倍，赢一把回本 | **会爆仓**。写出来是为了让你看到它有多危险 |
| `anti_martingale` | 赢了翻倍，连胜 N 次重置 | 利润奔跑，但平均不会比 flat 好多少 |
| `fixed_fraction` | 当前余额的 f% | 永远不破产（理论上），但会无限缩小 |
| `kelly` | 最优 f*，按净赔率算 | 含空投修正后 EV>0 才下，否则 0 |

---

## 工作流建议

1. 第一次进游戏，先**手动玩几局**，把真实赔率填进 `config.example.yaml`。
2. 跑 `ev` 看哪些押法在「考虑空投后」是正 EV。如果全是负的，**就别玩了，去打 dungeon**。
3. 在正 EV 的押法上跑 `compare`，挑破产率最低 + 等效价值最高的策略。
4. 用 **flat 平注**手动跟着算法的建议押。**不要自动化点击**——会被反女巫识别。

---

## FAQ

**Q: 可以接到游戏自动下吗？**
不会写。原因前面说过了：自动化会被项目方识别为 Sybil，封号 + 没收奖池。模拟器只输出策略建议，让你自己手动操作。

**Q: 凯利公式跑出来 f* = 0 怎么办？**
说明这押法的"含空投有效 EV ≤ 0"，凯利在告诉你：**别下**。这是它最大的价值。

**Q: 为什么模拟出来 Martingale 平均余额还行？**
平均值会被「未爆仓的会话」拉高。看 **`P5 分位`** 和 **`破产率`** —— 这俩才是 Martingale 真面目。



---

## 单机 exe 版本（纯娱乐）

如果只想"过瘾玩一下"，不写脚本，直接下个 exe 双击运行：

### 拿现成的（推荐）
1. 去 GitHub Actions 页面 → `Build Kraken Klash Sim (offline)` workflow
2. 下载最新 artifact `KrakenKlashSim-Windows-<sha>`
3. 解压双击 `KrakenKlashSim.exe` 就进交互模式了

### 自己 build
```bash
# Windows
build-sim.bat

# macOS / Linux
./build-sim.sh

# 产物在 dist-sim/
```

### 交互模式 4 个动作
- 选押法 → 输入下注单位 → 看结果（带动画）
- `📊 查看本场统计` —— 实时面板
- `⚡ 快进自动跑 N 局` —— 一次跑 100/1000 局看长期分布
- `📜 查看历史会话` —— 之前所有局都存在 `~/.kraken_klash_sim/sessions.jsonl`
- `💾 保存退出` —— 写入会话总结

### CLI 模式（带参数运行）
```bash
KrakenKlashSim ev                                    # EV 分析
KrakenKlashSim sim --bet half_board --strategy flat  # 蒙特卡洛
KrakenKlashSim compare --bet single_tile             # 策略对比
KrakenKlashSim play --bankroll 5000                  # 自定义本金交互
```

### exe 是怎么"单机"的
- 只用 `typer + rich + questionary + pyyaml`，零网络代码
- **没有** HTTP 客户端，**没有** Web3 库，**没有** 钱包模块
- 想自己确认？反编译看 strings：找不到任何 thebeacon.gg 的字符串
- 数据只写本地 `~/.kraken_klash_sim/sessions.jsonl`
- 体积 ~15MB（vs 主仓 ChainSniper 的 ~100MB），就是因为剥离了所有联网组件
