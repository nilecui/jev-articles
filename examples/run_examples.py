"""文章配套离线案例：仅消费手写策略输入，不调用模型，不执行外部动作。

Python 3.10+，只依赖标准库。--request 导出完整教学请求，仍不联网。
策略输入只保留用到的字段，不冒充完整 API 响应。
"""
import argparse
import csv
import json
from pathlib import Path


def unit(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 <= value <= 1:
        raise ValueError("概率或置信度必须是 0～1 的有限数")
    return value


def triage(category, confidence, severity, frustration, quality):
    routes = {"bug_report": "engineering", "billing": "billing",
              "feature_request": "product", "other": "human"}
    if category not in routes:
        raise ValueError("未声明的分类")
    if unit(confidence) < 0.8 or category == "other":
        return {"route": "human", "priority": None, "reason": "分类待复核"}
    # 各 Score 输入是 (score, confidence)，上限分别为 2、2、3。
    parts = []
    for (score, conf), maximum in zip((severity, frustration, quality), (2, 2, 3)):
        if not 0 <= score <= maximum:
            raise ValueError("分数超出量表")
        if unit(conf) < 0.7:
            return {"route": routes[category], "priority": None, "reason": "排序待复核"}
        parts.append(score / maximum)
    priority = round(sum(w * s for w, s in zip((0.6, 0.3, 0.1), parts)), 2)
    return {"route": routes[category], "priority": priority, "reason": "建议分流与排序"}


def sponsor(intent, intent_conf, category, category_conf):
    if intent not in {"sponsorship", "support", "partnership", "other"}:
        raise ValueError("未声明的意图")
    if category not in {"dev_tool", "course", "unrelated", "unknown"}:
        raise ValueError("未声明的产品类别")
    if min(unit(intent_conf), unit(category_conf)) < 0.8 or category == "unknown" or intent == "other":
        return "manual_review"
    if intent == "support":
        return "support_queue"
    if intent == "sponsorship" and category == "dev_tool":
        return "draft_media_kit_reply"
    return "manual_review"


def compact(tokens, switched, boundary, history, mid_operation, compactable=True):
    if tokens < 0 or not 0 <= history <= 2:
        raise ValueError("token 数或历史需求分数越界")
    for p in (switched, boundary, mid_operation):
        unit(p)
    if not compactable or mid_operation > 0.6:
        return "silent"
    if not (switched > 0.7 or (boundary > 0.6 and history < 1)):
        return "silent"
    if tokens < 6000:
        return "silent"
    if tokens < 10000:
        return "notice"
    if tokens < 14000:
        return "recommend"
    return "request"


def select_files(rows, floor=0.7):
    unit(floor)
    candidates, failed = [], []
    for row in rows:
        if row.get("error"):
            failed.append(row["path"])
        elif unit(row["relevant"]) >= floor:
            candidates.append(row["path"])
    # 仅为第二轮 Choice 构造候选；预留 none，不静默截断。
    if len(candidates) > 254:
        raise ValueError("候选超过 254 个，应分组；另留一个 none 选项")
    return {"candidates": candidates, "failed": failed,
            "next_step": "补查失败文件后再选" if failed else
                         "构造第二轮 Choice" if candidates else "扩大检索或人工阅读"}


def evaluate(path, thresholds=(0.5, 0.8, 0.9, 1.0)):
    with Path(path).open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    if not rows:
        raise ValueError("评测集为空")
    ids = set()
    for row in rows:
        if row["id"] in ids or not row["id"] or not row["gold"] or not row["predicted"]:
            raise ValueError("ID 重复或必填标签缺失")
        ids.add(row["id"])
        row["confidence"] = unit(float(row["confidence"]))
    report = []
    for threshold in thresholds:
        unit(threshold)
        accepted = [r for r in rows if r["confidence"] >= threshold and r["predicted"] != "other"]
        errors = sum(r["gold"] != r["predicted"] for r in accepted)
        report.append({"threshold": threshold, "total": len(rows), "accepted": len(accepted),
                       "errors": errors, "coverage": len(accepted) / len(rows),
                       "error_rate": errors / len(accepted) if accepted else None})
    return report


def build_request(kind):
    if kind == "sponsor":
        state = {"name": "示例日志平台", "description": "我们提供面向开发者的日志检索服务。",
                 "opportunity": "希望付费赞助下一期技术文章，请发合作资料。"}
        questions = {
            "intent": {"type": "choice", "instructions": "结合 `description` 与 `opportunity`，发件人的当前主要诉求是什么？",
                       "criteria": {"sponsorship": "明确希望付费投放或赞助", "support": "产品或账户求助",
                                    "partnership": "互推或内容交换，未提出付费", "other": "以上都不适用或信息不足"}},
            "category": {"type": "choice", "instructions": "根据 `name` 与 `description`，产品属于哪类？",
                         "criteria": {"dev_tool": "面向开发者的软件、API 或基础设施", "course": "课程、书籍或培训",
                                      "unrelated": "明确与开发者无关", "unknown": "描述不足，无法判断"}}
        }
    else:
        state = {"ticket": "结账页在所有浏览器报错，无法付款。Chrome 版本示例：123。步骤：打开购物车、点击付款、出现错误。"}
        questions = {
            "category": {"type": "choice", "instructions": "`ticket` 的主要诉求属于哪类？",
                         "criteria": {"bug_report": "要求修复损坏的功能", "billing": "要求核查账单、扣款或退款",
                                      "feature_request": "请求尚不存在的功能", "other": "不适用或信息不足"}},
            "severity": {"type": "score", "instructions": "`ticket` 描述的功能受阻程度如何？",
                         "criteria": ["不影响功能", "功能受损但有替代办法", "核心流程受阻且没有替代办法"]},
            "frustration": {"type": "score", "instructions": "`ticket` 的措辞表现出多强的挫败感？",
                            "criteria": ["平静", "不满但正常沟通", "强烈愤怒或表示将离开"]},
            "report_quality": {"type": "score", "instructions": "`ticket` 是否提供可供排查的具体信息？",
                               "criteria": ["没有具体信息", "只有功能名", "步骤和环境只具备一项", "同时提供步骤和环境"]}
        }
    return {"model": "jev-latest", "state": state, "questions": questions}


def demo(kind):
    if kind == "triage":
        return {"正常分类": triage("bug_report", 0.9, (1.8, 0.9), (1.0, 0.8), (3.0, 0.9)),
                "分类模糊": triage("bug_report", 0.79, (1.8, 0.9), (1.0, 0.8), (3.0, 0.9)),
                "评分模糊": triage("bug_report", 0.9, (1.8, 0.69), (1.0, 0.8), (3.0, 0.9))}
    if kind == "sponsor":
        return {"开发工具付费赞助": sponsor("sponsorship", 0.95, "dev_tool", 0.91),
                "只想互推": sponsor("partnership", 0.9, "dev_tool", 0.9),
                "课程付费赞助": sponsor("sponsorship", 0.95, "course", 0.92),
                "产品描述模糊": sponsor("sponsorship", 0.95, "unknown", 0.6)}
    if kind == "compact":
        return {"换任务_16000": compact(16000, 0.9, 0.2, 0.3, 0.1),
                "编辑未完_16000": compact(16000, 0.9, 0.2, 0.3, 0.9),
                "通知边界_6000": compact(6000, 0.9, 0.2, 0.3, 0.1),
                "换任务边界_0.7": compact(16000, 0.7, 0.2, 0.3, 0.1)}
    if kind == "files":
        return select_files([{"path": "src/domain/billing.ts", "relevant": 0.93},
                             {"path": "tests/billing.test.ts", "relevant": 0.9},
                             {"path": "docs/style.md", "relevant": 0.1},
                             {"path": "src/rounding.ts", "error": "timeout"}])
    return evaluate(Path(__file__).with_name("evaluation.csv"))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("case", nargs="?", default="all",
                        choices=("all", "triage", "sponsor", "compact", "files", "evaluation"))
    parser.add_argument("--request", choices=("triage", "sponsor"), help="只输出完整请求 JSON，不联网")
    parser.add_argument("--csv", type=Path, help="用指定 CSV 计算指标，不调用模型")
    args = parser.parse_args()
    if args.request and args.csv:
        parser.error("--request 和 --csv 不能同时使用")
    if args.request:
        result = build_request(args.request)
    elif args.csv:
        result = {"mode": "local_csv_metrics", "source": str(args.csv), "results": evaluate(args.csv)}
    else:
        kinds = ("triage", "sponsor", "compact", "files", "evaluation") if args.case == "all" else (args.case,)
        result = {"mode": "offline_handwritten_fixtures_not_model_predictions",
                  "results": {kind: demo(kind) for kind in kinds}}
    print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
