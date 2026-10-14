# 第一次调用 Jev：把一条工单变成三个判断

理解 Jev，最直接的方式是把一条消息变成几个可以被代码读取的结果。我们用这个自编例子：“付款扣了两次，订单还是失败了。我已经试了三遍，很着急，请帮我退回多扣的钱。”

这次只解决三件事：有没有退款诉求、哪个团队接手、挫败感有多强。我们暂时不处理真实退款。

## 先认识请求的三个部分

官方 HTTP 接口接收 `state`、`model` 和 `questions`。`state` 是待判断材料，`model` 选择模型，`questions` 是由自定义问题 ID 组成的字典；答案会使用相同 ID 返回。[API reference](https://docs.typesafe.ai/api)

问题 ID 是给程序取结果用的。真正需要模型理解的条件，应写在 `instructions` 和 `criteria` 中。不要把 `urgent_refund_for_vip` 当作一条隐含指令，期待模型从这个名字里读懂业务规则。

可以先在 [官方 Playground](https://console.typesafe.ai/playground) 输入材料、增加问题。如果要从终端调用，则先在 [密钥页面](https://console.typesafe.ai/keys) 创建密钥，并在本地终端通过环境变量 `TYPESAFE_API_KEY` 提供。下面命令需要该变量已经设置，运行会产生真实 API 请求及相应费用。

## 一次发送三种问题

这是基于官方协议写的完整中文教学请求，供读者自行调用；本文没有执行它，也没有附上冒充实测的响应。

```bash
curl --fail-with-body --show-error \
  https://api.typesafe.ai/v1/systemone \
  -H "Authorization: Bearer $TYPESAFE_API_KEY" \
  -H "Content-Type: application/json" \
  -d @- <<'JSON'
{
  "model": "jev-latest",
  "state": {
    "message": "付款扣了两次，订单还是失败了。我已经试了三遍，很着急，请帮我退回多扣的钱。"
  },
  "questions": {
    "refund_requested": {
      "type": "noul",
      "instructions": "`message` 的作者是否正在明确请求退回已支付或多扣的款项？",
      "criteria": {
        "true": "作者表达了当前退款请求，包括退回重复扣款。",
        "false": "只咨询退款规则、叙述历史退款，或明确表示不需要退款。"
      }
    },
    "department": {
      "type": "choice",
      "instructions": "根据 `message` 当前最主要的处理诉求，选择首个接手的团队。",
      "criteria": {
        "billing": "扣款、账单与退款处理；同时提到故障但主要要求退回款项时也归此类。",
        "technical": "主要要求修复故障、排查错误或恢复功能，没有以款项处理为主要诉求。",
        "sales": "主要咨询购买、套餐或产品报价。",
        "other": "不属于以上情况，或者没有足够信息确定主要诉求。"
      }
    },
    "frustration": {
      "type": "score",
      "instructions": "仅根据 `message` 的措辞，评估作者表达的挫败感强度。",
      "criteria": [
        "平静陈述或咨询，没有明显抱怨。",
        "表达着急、不满或反复失败带来的挫败感，仍在正常沟通。",
        "表达强烈愤怒、激烈抱怨或明显失去耐心。"
      ]
    }
  }
}
JSON
```

这里有一个刻意的设计：`billing` 写明了与技术故障重叠时的归属规则。因为“订单失败”和“要求退款”可能同时出现，如果没有首接团队的约定，即使人来标注也容易分歧。

`other` 则给未覆盖的情况留了出口。实际业务输入总会超出最初的想象，预先允许“暂时分不清”比强迫所有消息挤进三个团队更容易维护。

<!-- jev-illustration:02 -->
![退款工单的三种原语](illustrations/jev-series/02-infographic-three-primitives.png)

*图：同一工单可以同时提出是否退款、首接团队与挫败感三个问题。图中量表是教学定义。*

## 返回以后，分别看什么

Noul 读取 `answers.refund_requested.noul`。这是回答“是”的概率；它没有单独的 `confidence` 字段。

Choice 读取 `answers.department.choice`，同时可以查看各选项的 `probabilities` 与 `confidence`。Score 读取 `answers.frustration.score`，还会给出等级说明 `legend`、概率分布和置信度。字段定义见 [API 答案类型](https://docs.typesafe.ai/api#answer-types)。

Score 的数组等级从 0 开始。上面的三个等级对应 0、1、2，结果可以落在等级之间。比如，我们手写一个概率分布：0 级占 0.1，1 级占 0.7，2 级占 0.2，那么加权分数为 `0×0.1 + 1×0.7 + 2×0.2 = 1.1`。

这个算例用于解释分数，不是本次请求的模型输出。它也不是“110% 生气”，更不能当作用户真实心理状态的精确测量；模型只是在按我们写的量表评价文本表现。

## 首次实验，先观察变化

拿到一次结果之后，不必急着接业务动作。可以把消息改成三种版本，观察输出怎样变化：

| 改写 | 重点观察 |
|---|---|
| “退款已经处理好了，谢谢。” | 能否区分历史处理与当前诉求 |
| “我不需要退款，请恢复订单。” | 能否处理否定与主要诉求变化 |
| “这个怎么处理？” | 是否暴露出材料不足的问题 |

这些是待测试的用例，不是预先保证会通过的断言。保存请求、完整响应和人工判断，才有条件比较改写前后的表现。

官方说明英文是当前效果最好的训练语言，其他语言需要在自身内容上测试。因此，这份中文请求可以作为实验起点，但不能直接借用官方英文示例的数值作为它的结果。[语言支持说明](https://docs.typesafe.ai/models#language-support)

当一次调用跑通后，下一步最值得花时间的地方，就是把问题定义得更清楚。第三篇会专门处理这个环节。

---

本文请求为自编教学示例，按 2026-10-13 官方接口资料核对，未进行在线调用。置信度如何影响动作，见第四篇。

[系列目录](README.md) · [上一篇](01-Jev是什么-当AI的答案要交给代码.md) · [下一篇：材料与问题设计](03-Jev判断不准-先检查材料和问题.md)
