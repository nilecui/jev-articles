# 文章实战案例

Python 3.10+，标准库即可。从仓库根目录运行：

```bash
python3 articles-jev/examples/run_examples.py
```

脚本不联网、不读取密钥、不执行命令或发送消息。所有模型侧数字均为手写策略输入；CSV 中的预测与标签也都是教学构造，不能作为 Jev 准确率证据。输入只保留策略用到的字段，不是完整 API 响应。

| 子命令 | 对应文章 | 输入与可观察结果 |
|---|---|---|
| `triage` | [07 客服分诊](../07-实战客服分诊-从分类到优先级.md) | 分类与三个 Score；得到工程队列、0.79 排序值或复核 |
| `sponsor` | [08 赞助邀约](../08-实战赞助邀约-给自媒体做合作筛选.md) | 意图与产品分类；只生成合作资料回复的草稿建议 |
| `compact` | [09 Agent](../09-实战Agent-何时压缩先读哪个文件.md) | 换任务、编辑中、token 边界；得到四档压缩建议 |
| `files` | [09 Agent](../09-实战Agent-何时压缩先读哪个文件.md) | 相关性与失败记录；保留候选和失败文件 |
| `evaluation` | [10 批量评测](../10-实战批量评测-阈值预算与故障排查.md) | 8 条合成记录；计算各阈值的覆盖率、误分率 |

单独运行时将子命令放在脚本路径后：

```bash
python3 articles-jev/examples/run_examples.py sponsor
python3 articles-jev/examples/run_examples.py evaluation
```

## 导出真实接口可以接收的教学请求

以下命令仅在当前目录创建请求文件，不调用 API：

```bash
python3 articles-jev/examples/run_examples.py --request triage > triage-request.json
python3 articles-jev/examples/run_examples.py --request sponsor > sponsor-request.json
```

请求统一采用 TypeSafe 的 `model + state + questions` 形状，`model` 为 `jev-latest`。实际效果未验证。若自行在线调用，按 [第二篇](../02-第一次调用Jev-把一条工单变成三个判断.md) 的官方端点与密钥设置，将请求交给接口，再读取 `answers` 中相同 ID 的字段。`--request` 不会改变离线 demo 的手写结果。

`triage()` 接收 `category.choice`、`category.confidence` 和三个 `(score, confidence)`；`sponsor()` 接收两个 Choice 的选项与置信度。在线接入前还需对完整响应做契约校验，此脚本的局部数值检查不能替代客户端验证。

## 换成自己的评测结果

沿用 [evaluation.csv](evaluation.csv) 的列名：`id,text,gold,predicted,confidence`。`gold` 由人工标注，`predicted` 和 `confidence` 从真实响应提取。不要用模型自己的结果充当人工标签。

```bash
python3 articles-jev/examples/run_examples.py --csv /你的路径/results.csv
```

示例假设 `other` 必须转人工；阈值比较采用 `>=`。零自动处理样本的误分率输出 `null`。此工具只计算分类成功响应的指标；请求失败率、每类召回率、延迟、重试和账单需另外统计。

## 与仓库原版的差异

- 分诊组合了 Level 2 分类和 Level 3 评分，并增加分类／评分复核门槛。
- 赞助案例增加 `unknown`、两项置信度检查，输出草稿建议；仓库原版返回 `autoReply` 布尔值。
- 压缩策略保留 Level 7 的关键顺序与示例边界，但只返回档位，不实际压缩。
- 文件案例不扫描磁盘、不执行第二轮模型选择，只展示失败不能当成“不相关”。
- 所有新增阈值都是教学参数，不能直接解释为经过校准的生产标准。
