# Product Scraper · 1688 / 拼多多 商品批量抓取（GUI + EXE）

一个 PySide6 桌面应用，批量抓取 **1688** 和 **拼多多** 商品，按 **价格 / 图片 / 规格 / 特点 / 类型** 自动分类，**一键全选 + 一键导出**，可打包成 Windows EXE。

```
product-scraper/
├── app.py                       # GUI 入口（双击 EXE 启动这里）
├── product-scraper.spec         # PyInstaller 配置
├── build.bat / build.sh         # 一键打包脚本
├── .github/workflows/build-exe.yml  # GitHub Actions 自动出 EXE
├── config.yaml                  # 默认参数（关键词/类型规则/价格区间）
├── requirements.txt
├── gui/
│   ├── main_window.py           # 主窗口（参数 + 分类Tab + 表格 + 一键操作 + 日志）
│   ├── scrape_worker.py         # 后台 QThread 驱动抓取
│   └── theme.py
└── scraper/
    ├── base.py                  # Product 数据模型
    ├── alibaba1688.py           # 1688 抓取器
    ├── pinduoduo.py             # 拼多多 抓取器
    ├── classifier.py            # 自动按"类型 + 价格区间"打标
    ├── storage.py               # Excel(分Sheet) / JSON / 图片下载
    └── utils.py
```

## 界面

```
┌─ 抓取参数 ─────────────────────────────────────────────┐
│ 关键词: [蓝牙耳机, 充电宝, 保温杯]   URL: [...]          │
│ 平台: ☑1688 ☑拼多多   每词:30  翻页:2  ☑下载图片        │
│ [▶ 开始抓取]  [⏹ 停止]   ████████░░░ 80%                │
├─ 商品列表（按类别分类） ──────────────────────────────┤
│ 价格区间: [全部▾]                共 45 件 · 已选 20 件 │
│ ┌ Tabs: 全部(45) 数码电器(20) 家居日用(15) 母婴玩具(10)│
│ │ ☑ 1688  蓝牙耳机...     ¥88   数码电器  50-200  5图  │
│ │ ☑ PDD   保温杯...       ¥29.9 家居日用  0-50    3图  │
│ │ ...                                                  │
├─ 一键操作 ─────────────────────────────────────────────┤
│ [☑全选当前视图] [☐全不选] [⇅反选] [☑全选所有类别]      │
│                              [📁打开输出] [📤一键导出] │
├─ 运行日志 ────────────────────────────────────────────┤
│ 12:00:01 [INFO] [1688] 搜索 蓝牙耳机 第1页              │
│ 12:00:05 [INFO] 抓取完成，共 45 件                      │
└────────────────────────────────────────────────────────┘
```

## 三种获取 EXE 的方式

### 方式 A：在 Windows 本机打包（最快）

```bat
git clone <你的仓库 URL>
cd product-scraper
build.bat
```

完成后产物在 `dist\ProductScraper.exe`。

### 方式 B：用 GitHub Actions 自动出 EXE（推荐 ⭐）

把代码推到 GitHub 后：

1. **每次 push 到 main** → Actions 自动构建，在 *Actions → Build Windows exe → Artifacts* 下载 `ProductScraper-Windows-*.zip`
2. **打 tag** `v0.1.0` 推送 → 自动创建 GitHub Release，附带 `ProductScraper.exe` 和 `ProductScraper-macOS.tar.gz`

```bash
git tag v0.1.0
git push origin v0.1.0
```

### 方式 C：本地直接跑 Python 版（开发调试）

```bash
pip install -r requirements.txt
python app.py
```

## 操作流程

1. 在顶部填关键词，勾选平台 → **▶ 开始抓取**
2. 抓取过程中商品**实时**显示在表格里，按 **类型自动分 Tab**（数码电器 / 家居日用 / 母婴玩具 / ...）
3. 切到任意 Tab 看该类别下的商品
4. 用底部按钮选商品：
   - **☑ 全选当前视图**：当前 Tab + 价格区间 下的全部商品
   - **☐ 全不选** / **⇅ 反选**
   - **☑ 全选所有类别**：跨 Tab 一次性选中所有
5. **📤 一键导出选中** → 选目录 → 自动生成：
   - `products_{时间戳}.xlsx`
     - `ALL` Sheet：全部
     - **每个类型一个 Sheet**：`数码电器` `家居日用` ...
     - **每个价格区间一个 Sheet**：`价_0-50` `价_50-200` ...
   - `products_{时间戳}.json`：完整结构化数据
   - `images/<平台>/<类型>/<商品ID>/*.jpg`：本地图片（勾选了"下载图片"时）

每条商品包含字段：

| 字段 | 含义 |
| --- | --- |
| `platform` / `product_id` / `url` | 平台 / ID / 详情链接 |
| `title` | 标题 |
| `price` / `price_text` | 数字价格 / 原始价格文案 |
| `images` / `local_images` | 图片 URL / 本地路径 |
| `specs` | 规格属性（dict） |
| `features` | 卖点 / 特点（list） |
| `category_path` / `shop` / `sales` | 平台类目 / 店铺 / 销量 |
| **`bucket_type`** | 自动分类后的类型 |
| **`bucket_price`** | 自动分类后的价格区间 |

## 自定义分类规则

编辑 `config.yaml`：

```yaml
type_rules:
  数码电器: ["耳机", "音箱", "充电宝", "数据线", "充电器", "手机"]
  家居日用: ["保温杯", "水杯", "毛巾", "牙刷", "收纳", "拖鞋"]
  服饰鞋包: ["T恤", "卫衣", "外套", "鞋", "包"]
  # 想加细分类直接加：
  无线耳机: ["蓝牙耳机", "TWS"]
  其他: []   # 兜底，必须保留

price_buckets:
  - { name: "0-50",   min: 0,   max: 50 }
  - { name: "50-200", min: 50,  max: 200 }
  - { name: "200+",   min: 200, max: 999999999 }
```

GUI 启动时会自动读取 `config.yaml`（找不到就用内置默认值）。

## 重要前置条件

| 要求 | 说明 |
| --- | --- |
| **本机已装 Chrome** | DrissionPage 需要调用系统 Chrome / Edge。EXE 不会捆绑 Chrome |
| **首次运行需登录** | 1688 / 拼多多 都会要求登录或滑块。**勾掉"无头浏览器"**，弹出来的窗口手动登录一次，登录态会持久化到 `.browser_profile/`，下次免登 |
| **请求频率** | 默认每次请求随机 1.5~3.5 秒间隔。抓得太快会触发滑块 |
| **合规** | 仅作个人选品 / 行情研究使用，遵守目标站点 ToS，不要做大规模抓取或商业转售 |

## 常见问题

**Q: EXE 打开闪退？**
把 spec 文件中 `console=False` 改为 `True`，重新打包，黑窗口里能看到 Python 报错。

**Q: 提示找不到 Chrome？**
DrissionPage 会自动找已安装的 Chrome / Edge。如果都没有，到 Chrome 官网装一个。

**Q: 抓不到结果？**
99% 是被风控或没登录。把"无头浏览器"取消，开始抓取后会弹出真实浏览器，手动通过滑块/登录后回到 GUI 即可继续。

**Q: 想加细分类（比如"无线耳机/有线耳机"分开）？**
改 `config.yaml` 的 `type_rules`，重启 GUI 即可。

## 开发自检（已在沙箱通过）

- `py_compile` 全量编译通过
- GUI 离屏启动 + 5 件假数据 → Tabs 正确分类（数码电器 3 / 家居日用 1 / 母婴玩具 1）
- 一键全选当前视图 / 全选所有类别 → 选中数量正确
- 一键导出 → Excel 包含 `ALL` + 各类型 Sheet + `价_*` Sheet，JSON 含 5 条
