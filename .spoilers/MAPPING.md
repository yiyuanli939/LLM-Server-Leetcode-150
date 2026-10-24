# 练习 ↔ LeetCode 完整对应表（剧透！）

★ = 来自 LeetCode Top Interview 150；其余为其它 LeetCode 题。每个练习都在引擎里有真实调用点（见各模块 docstring 的 "Exercises this file calls"）。

## M1 · 分词、采样、流式输出：单请求生成（12 题）

| | LC | 题目 | 练习 id | 位置 | 在引擎里做什么 |
|---|---|---|---|---|---|
| ★ | 139 | Word Break | `tok.segment` | `nanoserve/tokenizer/segment.py::can_segment` | 编码前校验：文本能否被完整切分为词表中的 token（token 可重复使用） |
| ★ | 14 | Longest Common Prefix | `tok.common_prefix` | `nanoserve/tokenizer/prefix.py::common_prefix` | 找出一批 prompt 的最长公共前缀，用于检测共享 system prompt |
| ★ | 28 | Find the Index of the First Occurrence in a String | `stream.find_stop` | `nanoserve/stream/stop.py::find_stop` | stop string 在已生成文本中首次出现的位置，没有则 -1 |
| ★ | 68 | Text Justification | `stream.justify` | `nanoserve/stream/render.py::justify` | CLI 输出的两端对齐排版 |
| ★ | 58 | Length of Last Word | `stream.holdback` | `nanoserve/stream/detok.py::trailing_word_len` | 最后一个单词的长度（忽略尾部空白），流式输出时用来扣住半个单词 |
| ★ | 3 | Longest Substring Without Repeating Characters | `stream.unique_run` | `nanoserve/stream/repetition.py::longest_unique_run` | 退化检测指标：输出中不含重复字符的最长连续片段长度 |
| ★ | 219 | Contains Duplicate II | `stream.repeat_window` | `nanoserve/stream/repetition.py::repeats_within` | no-repeat 窗口：是否有同一 token 在距离 ≤ k 内重复出现 |
| ★ | 35 | Search Insert Position | `sample.cdf_index` | `nanoserve/sampling/search.py::cdf_index` | 按累积分布采样：返回 r 在严格递增 CDF 中的位置或插入点（O(log n)） |
| ★ | 215 | Kth Largest Element in an Array | `sample.kth_largest` | `nanoserve/sampling/topk.py::kth_largest` | top-k 采样的阈值：第 k 大的 logit |
|  | 347 | Top K Frequent Elements | `tok.top_pieces` | `nanoserve/tokenizer/train.py::top_k_pieces` | 训练词表：出现频率最高的 k 个片段（保证答案唯一），优于 O(n log n) |
|  | 1032 | Stream of Characters | `stream.multi_stop` | `nanoserve/stream/multistop.py::MultiStopMatcher` | 流式多 stop string 检测：每喂入一个字符，判断当前输出是否以任一 stop string 结尾 |
|  | 1392 | Longest Happy Prefix | `stream.stop_overlap` | `nanoserve/stream/overlap.py::longest_border` | 最长的「既是真前缀又是后缀」的子串（KMP 前缀函数）；引擎用它精确算出输出尾部与 stop string 开头重叠多少，只扣留这么多字符 |

## M2 · 服务器：连续 batching、准入、多 worker、传输、离线批任务规划（25 题）

| | LC | 题目 | 练习 id | 位置 | 在引擎里做什么 |
|---|---|---|---|---|---|
|  | 271 | Encode and Decode Strings | `stream.frame_codec` | `nanoserve/stream/protocol.py::FrameCodec` | 流式协议分帧：把任意字符串列表（可含任何字符）编码成一个字符串并无损解码 |
| ★ | 295 | Find Median from Data Stream | `metrics.median` | `nanoserve/metrics/latency.py::MedianTracker` | 在线 p50 延迟 |
| ★ | 4 | Median of Two Sorted Arrays | `metrics.merged_median` | `nanoserve/metrics/latency.py::merged_median` | 合并两个 worker 各自有序的延迟样本求中位数，O(log(m+n)) |
| ★ | 56 | Merge Intervals | `sched.merge_busy` | `nanoserve/scheduler/timeline.py::merge_busy` | 合并 GPU 忙碌区间，计算利用率 |
| ★ | 57 | Insert Interval | `sched.insert_busy` | `nanoserve/scheduler/timeline.py::insert_busy` | 向已排序且不重叠的忙碌时间线插入新区间 |
| ★ | 452 | Minimum Number of Arrows to Burst Balloons | `sched.min_launches` | `nanoserve/scheduler/batching.py::min_launches` | 每个请求有 [最早, 最晚] 可服务窗口，一次 batch 发射在时刻 t 服务所有包含 t 的窗口；求最少发射次数 |
| ★ | 169 | Majority Element | `metrics.dominant` | `nanoserve/metrics/tenants.py::dominant_tenant` | 热点租户检测：返回占请求一半以上的租户（无多数时返回任意候选，由调用方计数确认），O(1) 额外空间 |
| ★ | 53 | Maximum Subarray | `metrics.max_burst` | `nanoserve/metrics/burst.py::max_burst` | 队列长度每秒变化量，求最大连续累计增长（最大突发） |
| ★ | 918 | Maximum Sum Circular Subarray | `metrics.max_burst_circular` | `nanoserve/metrics/burst.py::max_burst_circular` | 同上，但数据是按天循环的周期序列（可跨越末尾回到开头） |
|  | 528 | Random Pick with Weight | `sched.weighted_route` | `nanoserve/scheduler/routing.py::WeightedRouter` | 按权重把请求路由到 worker：返回下标 i 的概率为 w[i]/sum(w) |
|  | 1094 | Car Pooling | `sched.capacity_ok` | `nanoserve/scheduler/capacity.py::fits_capacity` | 每个请求 [占用块数, 开始, 结束)，判断任意时刻总占用都不超过显存容量 |
|  | 1834 | Single-Threaded CPU | `sched.sjf` | `nanoserve/scheduler/simulate.py::sjf_order` | 单 worker 最短作业优先调度模拟：tasks[i]=[到达时间, 处理时长]，返回处理顺序 |
|  | 1882 | Process Tasks Using Servers | `sched.assign_workers` | `nanoserve/scheduler/simulate.py::assign_workers` | 多 worker 分配模拟：第 j 秒到达任务 j，交给空闲中权重最小（再按下标）的 worker |
|  | 2402 | Meeting Rooms III | `sched.busiest_worker` | `nanoserve/scheduler/simulate.py::busiest_worker` | n 个 worker，任务延后但保持时长；返回承接任务最多的 worker（并列取最小下标） |
|  | 621 | Task Scheduler | `sched.cooldown` | `nanoserve/scheduler/cooldown.py::min_slots_with_cooldown` | 同一 LoRA adapter 两次加载之间至少间隔 n 个时间片，求执行完所有任务的最少时间片 |
|  | 933 | Number of Recent Calls | `metrics.qps` | `nanoserve/metrics/window.py::QpsCounter` | 最近 3000ms 内的请求数（t 严格递增） |
|  | 239 | Sliding Window Maximum | `metrics.window_max` | `nanoserve/metrics/window.py::window_max` | 滚动窗口最大延迟，O(n) |
|  | 480 | Sliding Window Median | `metrics.window_median` | `nanoserve/metrics/window.py::window_median` | 滚动窗口 p50 延迟 |
|  | 393 | UTF-8 Validation | `server.utf8_ok` | `nanoserve/server/utf8.py::utf8_valid` | 流式传输按字节切包，客户端在缓冲区构成合法 UTF-8 时才解码预览 |
|  | 1797 | Design Authentication Manager | `server.tokens` | `nanoserve/server/auth_tokens.py::TokenManager` | API token 管理：带 TTL 的签发、续期、统计有效 token |
|  | 1845 | Seat Reservation Manager | `sched.slots` | `nanoserve/scheduler/batch_slots.py::SlotAllocator` | 运行中 batch 的槽位分配器：总是分配编号最小的空闲槽（1..n） |
|  | 729 | My Calendar I | `sched.maintenance` | `nanoserve/scheduler/calendar.py::MaintenanceCalendar` | 维护窗口预约：半开区间 [start, end) 不得与已有预约重叠 |
|  | 2406 | Divide Intervals Into Minimum Number of Groups | `sched.min_workers` | `nanoserve/scheduler/planning.py::min_workers` | 容量规划：请求占用闭区间 [start, end]，同一 worker 上不能重叠，最少需要几个 worker |
|  | 630 | Course Schedule III | `sched.slo_bound` | `nanoserve/scheduler/planning.py::max_on_time` | SLO 上界：jobs[i]=[时长, 截止时刻]，单 worker 串行最多能按时完成多少个请求 |
|  | 1606 | Find Servers That Handled Most Number of Requests | `sched.rr_busiest` | `nanoserve/scheduler/lb.py::busiest_servers` | 轮询负载均衡（第 i 个请求从 i%k 号开始找第一个空闲 worker，全忙则丢弃）后，处理请求最多的 worker |

## M3 · KV Cache 块管理器：分页分配、空闲表、淘汰策略、快照与泄漏检测（30 题）

| | LC | 题目 | 练习 id | 位置 | 在引擎里做什么 |
|---|---|---|---|---|---|
| ★ | 146 | LRU Cache | `kv.lru` | `nanoserve/kvcache/lru.py::LRUBlockCache` | KV 块 LRU 缓存，get/put 均 O(1) |
| ★ | 138 | Copy List with Random Pointer | `kv.fork` | `nanoserve/kvcache/block_table.py::fork_chain` | 并行采样时 fork 一条块链：每个块有 next 和指向链中任意块的 random（共享引用），深拷贝 |
| ★ | 141 | Linked List Cycle | `kv.has_cycle` | `nanoserve/kvcache/block_table.py::has_cycle` | 块链损坏检测：是否成环，O(1) 空间 |
| ★ | 86 | Partition List | `kv.partition_hot` | `nanoserve/kvcache/block_table.py::partition_by_heat` | 热度 < x 的块排到前面，两部分内部保持原相对顺序 |
| ★ | 21 | Merge Two Sorted Lists | `kv.merge_free` | `nanoserve/kvcache/free_list.py::merge_free_lists` | 合并两条按块号有序的空闲链表 |
| ★ | 23 | Merge k Sorted Lists | `kv.merge_free_k` | `nanoserve/kvcache/free_list.py::merge_k_free_lists` | 合并 k 个 worker 回收的有序空闲链表 |
| ★ | 148 | Sort List | `kv.sort_free` | `nanoserve/kvcache/free_list.py::sort_free_list` | 碎片整理：把空闲链表按块号排序，O(n log n) |
| ★ | 82 | Remove Duplicates from Sorted List II | `kv.drop_double_free` | `nanoserve/kvcache/free_list.py::drop_double_freed` | 有序空闲链表中被重复释放的块号全部隔离（凡出现多次的块号一个不留） |
| ★ | 27 | Remove Element | `kv.compact` | `nanoserve/kvcache/compact.py::remove_freed` | 原地压缩：去掉所有等于 freed 标记的槽位，返回剩余长度 |
| ★ | 26 | Remove Duplicates from Sorted Array | `kv.dedupe` | `nanoserve/kvcache/compact.py::dedupe_sorted` | 有序块号原地去重，返回唯一元素个数 |
| ★ | 88 | Merge Sorted Array | `kv.merge_arrays` | `nanoserve/kvcache/compact.py::merge_into` | 把有序空闲块号数组 b 原地合并进 a（a 尾部预留 n 个 0） |
| ★ | 189 | Rotate Array | `kv.rotate_buffer` | `nanoserve/kvcache/ring.py::rotate_right` | 环形缓冲区原地右移 k 位，O(1) 额外空间 |
| ★ | 33 | Search in Rotated Sorted Array | `kv.ring_search` | `nanoserve/kvcache/ring.py::ring_search` | 在旋转过的有序环形缓冲（元素互不相同）中查找，O(log n) |
| ★ | 153 | Find Minimum in Rotated Sorted Array | `kv.ring_head` | `nanoserve/kvcache/ring.py::ring_min` | 找到环形缓冲的逻辑起点（最小值），O(log n) |
| ★ | 128 | Longest Consecutive Sequence | `kv.longest_run` | `nanoserve/kvcache/allocator.py::longest_free_run` | 无序空闲块号中最长连续块号段的长度，O(n) |
| ★ | 228 | Summary Ranges | `kv.free_ranges` | `nanoserve/kvcache/allocator.py::free_ranges` | 把有序不重复空闲块号压缩成 'a->b' / 'a' 区间描述 |
| ★ | 34 | Find First and Last Position of Element in Sorted Array | `kv.seq_range` | `nanoserve/kvcache/allocator.py::owner_range` | 按所属序列号排序的块表中，某序列占用的首尾下标，没有则 [-1,-1]，O(log n) |
| ★ | 74 | Search a 2D Matrix | `kv.page_lookup` | `nanoserve/kvcache/page_table.py::page_exists` | 二维页表（每行有序，下一行首元素大于上一行末元素）中查找地址，O(log(mn)) |
| ★ | 191 | Number of 1 Bits | `kv.popcount` | `nanoserve/kvcache/bitmap.py::popcount` | 位图分配器：统计已占用块数 |
| ★ | 136 | Single Number | `kv.leaked` | `nanoserve/kvcache/leak.py::find_leaked` | 分配与释放日志中每个块号出现两次，唯一只出现一次的就是泄漏块；O(1) 空间 |
| ★ | 380 | Insert Delete GetRandom O(1) | `kv.random_evict` | `nanoserve/kvcache/evict.py::RandomEvictSet` | 随机淘汰策略的候选集合，三个操作均摊 O(1) |
|  | 460 | LFU Cache | `kv.lfu` | `nanoserve/kvcache/lfu.py::LFUBlockCache` | LFU 淘汰策略（频率相同按 LRU），O(1) |
|  | 622 | Design Circular Queue | `kv.ring_queue` | `nanoserve/kvcache/ring_queue.py::RingQueue` | 固定容量环形请求队列 |
|  | 1146 | Snapshot Array | `kv.snapshot` | `nanoserve/kvcache/snapshot.py::SnapshotTable` | copy-on-write 块表快照：只记录变化，按快照号查询历史值 |
|  | 981 | Time Based Key-Value Store | `kv.versioned` | `nanoserve/kvcache/versioned.py::VersionedStore` | 带时间戳的多版本缓存条目，查询不晚于 ts 的最新版本 |
|  | 2502 | Design Memory Allocator | `kv.mem_alloc` | `nanoserve/kvcache/memalloc.py::MemoryAllocator` | first-fit 显存分配器：分配最左侧连续空闲段，按 owner 释放 |
|  | 432 | All O(1) Data Structure | `kv.refcount` | `nanoserve/kvcache/refcount.py::RefCounter` | 块引用计数，O(1) 取引用最多/最少的块 |
|  | 706 | Design HashMap | `kv.block_hash` | `nanoserve/kvcache/hashmap.py::BlockHashMap` | 块内容哈希 → 块号的去重表，不许用内置 dict/set |
|  | 352 | Data Stream as Disjoint Intervals | `kv.free_tracker` | `nanoserve/kvcache/free_tracker.py::FreeRangeTracker` | 在线维护空闲块号的不相交区间 |
|  | 715 | Range Module | `kv.address_ranges` | `nanoserve/kvcache/address_ranges.py::AddressRanges` | 已分配地址区间跟踪（半开区间），支持增、删、整段查询 |

## M4 · 前缀缓存与 deadline 索引：Trie、BST 索引、持久化（16 题）

| | LC | 题目 | 练习 id | 位置 | 在引擎里做什么 |
|---|---|---|---|---|---|
| ★ | 208 | Implement Trie (Prefix Tree) | `prefix.trie` | `nanoserve/prefix/trie.py::PrefixTrie` | 前缀缓存的字典树（每个 token 映射为一个字符） |
| ★ | 236 | Lowest Common Ancestor of a Binary Tree | `prefix.fork_point` | `nanoserve/prefix/tree_ops.py::fork_point` | deadline 索引的区间查询：两个节点的最近公共祖先就是区间的分叉节点，只需遍历它的子树 |
| ★ | 104 | Maximum Depth of Binary Tree | `prefix.depth` | `nanoserve/prefix/tree_ops.py::max_depth` | deadline 索引的平衡监控：树高超过阈值就整体重建 |
| ★ | 102 | Binary Tree Level Order Traversal | `prefix.level_dump` | `nanoserve/prefix/dump.py::level_dump` | 按层 dump deadline 索引（调试视图） |
| ★ | 100 | Same Tree | `prefix.same_snapshot` | `nanoserve/prefix/snapshot.py::same_tree` | checkpoint 读回校验：恢复出的索引与原索引结构、取值完全一致 |
| ★ | 173 | Binary Search Tree Iterator | `index.iter` | `nanoserve/index/deadline.py::DeadlineIterator` | 按 deadline 从早到晚迭代 BST 索引，O(h) 空间 |
| ★ | 230 | Kth Smallest Element in a BST | `index.kth` | `nanoserve/index/deadline.py::kth_earliest` | 第 k 早的 deadline（1-based） |
| ★ | 98 | Validate Binary Search Tree | `index.validate` | `nanoserve/index/deadline.py::is_valid_index` | 索引不变量检查：是否为严格 BST |
| ★ | 530 | Minimum Absolute Difference in BST | `index.min_gap` | `nanoserve/index/deadline.py::min_gap` | 任意两个 deadline 的最小间隔 |
| ★ | 108 | Convert Sorted Array to Binary Search Tree | `index.build` | `nanoserve/index/deadline.py::build_balanced` | 从有序 deadline 数组构建高度平衡的 BST 索引 |
|  | 297 | Serialize and Deserialize Binary Tree | `prefix.codec` | `nanoserve/prefix/codec.py::TreeCodec` | 缓存树持久化：任意格式，只要能无损往返（值可重复、可为负） |
|  | 677 | Map Sum Pairs | `prefix.hit_sum` | `nanoserve/prefix/hit_sum.py::PrefixHitSum` | 前缀缓存统计：以某前缀开头的所有键的命中值之和（重复 insert 覆盖） |
|  | 307 | Range Sum Query - Mutable | `index.range_sum` | `nanoserve/index/fenwick.py::RangeCounter` | 按 deadline 桶统计 token 数，支持单点修改和区间求和（O(log n)） |
|  | 701 | Insert into a Binary Search Tree | `index.insert` | `nanoserve/index/bst_ops.py::insert_key` | 向 deadline 索引插入新请求（val 不在树中） |
|  | 450 | Delete Node in a BST | `index.delete` | `nanoserve/index/bst_ops.py::delete_key` | 请求完成后从 deadline 索引删除 |
|  | 1008 | Construct Binary Search Tree from Preorder Traversal | `index.restore` | `nanoserve/index/bst_ops.py::bst_from_preorder` | 从 checkpoint 中的前序序列恢复索引，O(n) |

## M5 · 模型 IR 与配置：计算图编译执行、配置解析（17 题）

| | LC | 题目 | 练习 id | 位置 | 在引擎里做什么 |
|---|---|---|---|---|---|
| ★ | 207 | Course Schedule | `ir.order_ok` | `nanoserve/ir/graph.py::can_schedule` | 算子依赖 [a, b] 表示 a 依赖 b；判断计算图是否无环可调度 |
| ★ | 210 | Course Schedule II | `ir.order` | `nanoserve/ir/graph.py::topo_order` | 给出任一合法算子执行顺序，有环返回 [] |
| ★ | 133 | Clone Graph | `ir.clone` | `nanoserve/ir/graph.py::clone_graph` | 图优化 pass 前深拷贝计算图 |
| ★ | 150 | Evaluate Reverse Polish Notation | `ir.rpn` | `nanoserve/ir/interp.py::eval_rpn` | IR 字节码（后缀表达式）解释器，除法向零截断 |
| ★ | 20 | Valid Parentheses | `config.brackets` | `nanoserve/config/parser.py::brackets_balanced` | 配置解析前检查 ()[]{} 是否正确配对 |
| ★ | 71 | Simplify Path | `config.norm_path` | `nanoserve/config/paths.py::normalize_path` | 规范化 Unix 风格模型路径 |
| ★ | 224 | Basic Calculator | `config.expr` | `nanoserve/config/expr.py::eval_expr` | 配置中的 + - ( ) 表达式求值（含一元负号），不许用 eval |
|  | 743 | Network Delay Time | `ir.op_latency` | `nanoserve/ir/latency.py::broadcast_latency` | 设备 1..n 间有向带权链路，从 src 广播到所有设备的最短完成时间，不可达 -1 |
|  | 2050 | Parallel Courses III | `ir.critical_path` | `nanoserve/ir/latency.py::critical_path_time` | 算子 1..n，[a,b] 表示 b 依赖 a，无限并行下跑完整张图的最短时间（关键路径） |
|  | 547 | Number of Provinces | `ir.device_groups` | `nanoserve/ir/topology.py::count_device_groups` | 设备互联邻接矩阵中直接或间接互联的设备组数（用并查集） |
|  | 394 | Decode String | `config.expand` | `nanoserve/config/template.py::expand_template` | 配置模板展开：k[片段] 表示片段重复 k 次，可嵌套 |
|  | 227 | Basic Calculator II | `config.arith` | `nanoserve/config/arith.py::eval_arith` | 配置中的 + - * / 表达式（无括号，除法向零截断），不许用 eval |
|  | 1462 | Course Schedule IV | `ir.depends_on` | `nanoserve/ir/reach.py::depends_queries` | [a, b] 表示 a 必须先于 b；回答 [u, v]：u 是否（传递地）必须先于 v，用于判断两个算子能否并行 |
|  | 2115 | Find All Possible Recipes from Given Supplies | `ir.computable` | `nanoserve/ir/reach.py::computable_outputs` | 给定已提供的张量，哪些算子输出可以被算出来（输出也可作为别人的输入） |
|  | 722 | Remove Comments | `config.strip_comments` | `nanoserve/config/comments.py::strip_comments` | 配置文件去掉 // 行注释和 /* */ 块注释（块注释可跨行），删除变空的行 |
|  | 1106 | Parsing A Boolean Expression | `config.flags` | `nanoserve/config/flags.py::eval_flag_expr` | feature flag 条件表达式：t、f、!(x)、&(x,y,...)、|(x,y,...) |
|  | 44 | Wildcard Matching | `config.glob` | `nanoserve/config/glob.py::glob_match` | 路由规则的模型名 glob 匹配：? 匹配单字符，* 匹配任意串，整串匹配 |

## M6 · 解码与评测：投机解码草稿树、评测指标、benchmark 与 fuzz（8 题）

| | LC | 题目 | 练习 id | 位置 | 在引擎里做什么 |
|---|---|---|---|---|---|
| ★ | 72 | Edit Distance | `eval.edit_distance` | `nanoserve/eval/metrics.py::edit_distance` | 输出与参考答案的编辑距离 |
| ★ | 97 | Interleaving String | `eval.interleave_ok` | `nanoserve/eval/streams.py::is_interleaving` | 校验多路复用输出流 merged 是否由两个请求的输出交错而成 |
| ★ | 373 | Find K Pairs with Smallest Sums | `decode.beam_pairs` | `nanoserve/decode/beam.py::k_best_pairs` | 两步 beam 扩展：两个升序代价列表中代价和最小的 k 对 |
| ★ | 77 | Combinations | `bench.choose` | `nanoserve/bench/sweep.py::choose` | 从 1..n 个特性开关中选 k 个的所有组合 |
| ★ | 46 | Permutations | `bench.orders` | `nanoserve/bench/fuzz.py::arrival_orders` | 调度器确定性测试：枚举请求的所有到达顺序 |
| ★ | 22 | Generate Parentheses | `bench.json_fuzz` | `nanoserve/bench/fuzz.py::balanced_brackets` | 约束解码 fuzzer：生成所有 n 对括号的合法嵌套结构 |
|  | 1143 | Longest Common Subsequence | `eval.rouge_l` | `nanoserve/eval/rouge.py::lcs_length` | ROUGE-L 的核心：输出与参考的最长公共子序列长度 |
|  | 10 | Regular Expression Matching | `decode.regex` | `nanoserve/decode/regex.py::full_match` | 约束解码校验：输出是否完整匹配只含 '.' 与 '*' 的正则 |

## M7 · 可观测性与自动扩缩容：指标面板、容量规划（9 题）

| | LC | 题目 | 练习 id | 位置 | 在引擎里做什么 |
|---|---|---|---|---|---|
| ★ | 73 | Set Matrix Zeroes | `dash.mask_failed` | `nanoserve/dashboard/health.py::mask_failures` | worker×model 健康矩阵：出现 0 的行与列整体置 0，原地，O(1) 额外空间为进阶 |
|  | 304 | Range Sum Query 2D - Immutable | `dash.region_sum` | `nanoserve/dashboard/region.py::RegionSum` | 热力图任意矩形区域求和，查询 O(1) |
| ★ | 392 | Is Subsequence | `dash.fuzzy` | `nanoserve/dashboard/filter.py::fuzzy_match` | 面板里的 fzf 式模糊过滤：query 的字符是否按顺序（可不连续）出现在 text 中 |
|  | 703 | Kth Largest Element in a Stream | `metrics.slowest_k` | `nanoserve/metrics/slowest.py::KthSlowest` | 在线跟踪第 k 慢的请求延迟（「最慢 k 个」面板的门槛） |
|  | 2034 | Stock Price Fluctuation | `metrics.corrected` | `nanoserve/metrics/series.py::CorrectableSeries` | 可被迟到数据修正的指标序列：最新时间戳的值、当前最大/最小值 |
|  | 2276 | Count Integers in Intervals | `metrics.busy_time` | `nanoserve/metrics/busy.py::BusyTimeCounter` | 利用率统计：不断加入闭区间忙碌时段，查询被覆盖的总时刻数 |
|  | 1011 | Capacity To Ship Packages Within D Days | `autoscale.min_throughput` | `nanoserve/autoscale/sizing.py::min_throughput` | 按顺序处理的批任务，每个周期吞吐上限相同，days 个周期内完成所需的最小吞吐 |
|  | 875 | Koko Eating Bananas | `autoscale.min_rate` | `nanoserve/autoscale/sizing.py::min_drain_rate` | 每个时间片只服务一个队列、最多服务 rate 个请求，hours 内清空所有队列的最小 rate |
|  | 2187 | Minimum Time to Complete Trips | `autoscale.min_time` | `nanoserve/autoscale/sizing.py::min_time_for` | 异构 worker 并行、各自每 t_i 完成一个请求，完成 total 个请求的最短时间 |
