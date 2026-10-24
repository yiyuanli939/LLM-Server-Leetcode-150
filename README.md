# LLM-Server-Leetcode-150 · nano-serve

用 Python 从零写一个迷你 LLM 推理服务器。写完它，你也顺手做完了 117 道 LeetCode 题。

这些题不是贴上去的：**每一道题都是引擎里一个真正被调用的函数或类**。KV cache 的 LRU / LFU 淘汰、batch 槽位分配、前缀缓存的 Trie、EDF 队列背后的 BST、计算图的拓扑排序与关键路径、投机解码的草稿树、ROUGE-L 的最长公共子序列……练习的题面写的是领域需求，不写题号：你得先认出这是哪种模式，再动手写。

```
117 个练习 = 63 道来自 LeetCode Top Interview 150 ★ + 54 道其它 LeetCode 题
```

**关于"150"**：Top Interview 150 里只有 63 道能*自然地*放进推理引擎，我们只保留了这些；硬换壳的题（把股票买卖说成算力交易、把罗马数字塞进日志格式……）全部删掉了。引擎还缺的组件，用 LeetCode 其它题来补，标准相同：引擎里必须有真实的调用点。这一点是可以检查的——`make callsites` 会在参考模式下跑全部集成测试，确认 117 个练习每一个都被引擎执行到。

## 快速开始

```bash
git clone https://github.com/yiyuanli939/LLM-Server-Leetcode-150
cd LLM-Server-Leetcode-150
pip install numpy pyyaml pytest
make progress        # 进度面板（无剧透）
make m1              # M1 要实现哪些函数
```

想先看看做完是什么样？参考解在 `solutions` 分支（**含剧透**）：

```bash
git fetch origin solutions
git restore --source=origin/solutions -- reference   # 只把 reference/ 放进工作区（已在 .gitignore 里，不会误提交）
make demos                                      # 参考模式下把每个里程碑的 demo 跑一遍
```

两种参考模式：

- `NANOSERVE_REFERENCE=1`（或 `pytest --reference`）：所有练习都用参考解，看完成后的引擎。
- `NANOSERVE_REFERENCE=auto`（或 `pytest --fill`、`make test-fill`）：**只有你还没动过的练习**（函数体仍是 `raise TODO(...)`）用参考解，你写过的都跑你自己的代码。这样就能**跳着做**：比如先写 M3 的 KV cache，`NANOSERVE_REFERENCE=auto python -m nanoserve kv` 就是你的 KV cache 跑在参考实现的 M1/M2 之上。

## 怎么做一个练习

1. `make m3`（或看 `exercises.yaml`）挑一个 ⬜ 的练习。
2. 打开它所在的文件，读 docstring 里的领域需求和规格，把 `raise TODO(...)` 换成你的实现。
3. `make progress` 看它变 ✅；单独跑它的测试：`python -m pytest -q -k kv_lru`。
4. 一个里程碑的练习都做完后，它的集成测试（`tests/domain/`）变绿，引擎就能端到端多做一件事，对应的 `python -m nanoserve <子命令>` 也能用你自己的代码跑起来。（只做完一部分时，`make test-fill` 看你的代码放进引擎里是否正确。）
5. 想知道刚做的是哪道 LeetCode：`make reveal`（只揭晓已完成的）。

## 里程碑

| | 内容 | 练习（★150 + 其它） | 端到端能跑的东西 |
|---|---|---|---|
| M1 | 分词、采样、流式输出 | 12（9 + 3） | `python -m nanoserve "The scheduler" --stop "."` 单请求流式生成 |
| M2 | 服务器：连续 batching、准入控制、会话 TTL、维护窗口、多 worker 路由、传输协议、离线批任务规划 | 25（8 + 17） | `nanoserve serve [--workers 3 --policy weighted\|rr\|weighted_free --plan]` |
| M3 | 分页 KV cache：空闲链表、fork / 写时复制、回滚、块去重、淘汰策略、泄漏与双重释放检测 | 30（21 + 9） | `nanoserve kv` 显存吃紧时抢占、换出、仍然输出不变 |
| M4 | 前缀缓存（Trie）、EDF 截止时间队列（BST）、checkpoint / restore | 16（10 + 6） | `nanoserve prefix` 缓存命中省下的 prefill、EDF vs FCFS |
| M5 | 模型计算图 IR（编译、剪枝、并行性、关键路径、设备放置）、配置系统 | 17（7 + 10） | `nanoserve compile`、`nanoserve config` |
| M6 | 投机解码草稿树、评测（编辑距离 / ROUGE-L / 正则约束 / 流完整性）、benchmark 与 fuzz | 8（6 + 2） | `nanoserve eval --spec`、`nanoserve bench` |
| M7 | 可观测性面板、自动扩缩容 | 9（2 + 7） | `nanoserve dashboard`、`nanoserve autoscale` |

里程碑大致按依赖排序，难度也大致递增；但借助参考模式，顺序可以随意。

## 架构

```
             ┌──────────── M5 config/loader ── 配置文件 → ServerConfig + 路由规则
             │
 trace ──► Server (M2) ──────────────────────────────────────────────► ServerReport ──► M7 dashboard / autoscaler
           │  arrivals → 会话 TTL、QPS
           │  admission → batch 槽位、token 预算预留、维护窗口
           │      ├─ WaitingQueue   ← FCFS │ M4 DeadlineQueue（BST）
           │      ├─ KVBackend      ← M3 BlockManager（分页 KV）
           │      └─ PrefixCache    ← M4 PrefixCache（Trie）
           │  compute → Engine.step (M1) ──► sampler / stop 检测 / 流式扣留
           │                 └─ model: NGramModel │ M5 IRModel（编译后的计算图，逐位等价）
           └─ events ──► M2 transport（分帧 + UTF-8 分包）──► client
 Cluster (M2) = 多个 Server + 路由策略；M6 在 Server 之上做评测、投机解码和 benchmark。
```

模型是一个 numpy 写的 5-gram 玩具模型，用来代替 transformer：输出很傻，但服务器围绕它做的一切（batching、KV cache、前缀缓存、调度、投机解码）与真实引擎是同一套逻辑，并且全部可以在笔记本 CPU 上秒级跑完。时间是模拟的：1 tick = batch 的一次 decode step。

每个框架模块的 docstring 都写了它调用了哪些练习（"Exercises this file calls"），读框架代码就能看到你写的函数在哪里、为什么被用到。

## 目录

```
nanoserve/
  engine.py, __main__.py           M1 生成循环 + CLI
  model/ tokenizer/ sampling/ stream/   M1
  server/ scheduler/ metrics/      M2（server/ 是框架，scheduler/ metrics/ 主要是练习）
  kvcache/                         M3（manager.py 等是框架，其余是练习）
  prefix/ index/                   M4
  ir/ config/                      M5
  decode/ eval/ bench/             M6
  dashboard/ autoscale/            M7
  common/nodes.py                  ListNode / TreeNode / GraphNode 等节点类型
tests/lc/                          每个练习的单元测试（与原题等价）
tests/domain/                      每个里程碑的端到端集成测试
tools/progress.py                  进度面板
tools/callsites.py                 维护者自检：每个练习都被引擎真实执行
exercises.yaml                     练习清单：id、文件、签名、领域需求（无剧透）
.spoilers/MAPPING.md               练习 ↔ LeetCode 对应表（剧透）
```

## 讲义（PDF，含剧透）

[`docs/nano-serve-guide.pdf`](docs/nano-serve-guide.pdf)（289 页）：
系统设计（总览 + 七个里程碑各一章，每个设计取舍都与替代方案对比）、117 道题逐题讲解（引擎角色、算法、复杂度、参考实现、对比讲解、易错点）、按模式索引。
**它包含参考实现**，建议做完一道题再翻到对应的那一页。

## 关于剧透

- 练习文件、`exercises.yaml`、进度面板都不出现题号。
- `tests/lc/` 的用例取自原题示例，熟悉 LeetCode 的人一眼能认出——想练"认模式"，先别读测试。
- 少数练习为了适配真实调用场景放宽了原题的约束（比如允许任意字符、时间从 0 开始、数据规模更大），算法本身不变。
- 参考解在 `solutions` 分支；`docs/` 里的讲义也包含参考实现。

## 做完之后

在项目语境里写过一遍，理解会深很多；但面试要的是空白编辑器加计时。建议全部做完后用 `make reveal` 拿到题号，去 LeetCode 上从零快速重写一遍。
