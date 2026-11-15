# 真实模型离线评测

cases.json 包含 30 条人工定义的演示咨询，涵盖中文、英语、西语、同会话追问、售后、数量、未知目的国与诱导编造价格/配送/退款政策。期望工具、参数、关键事实、状态与需禁止的承诺随各条用例记录。事实只来自三个种子商品和 ES 配送规则。

在 backend 目录执行：

```powershell
uv run --frozen --extra dev python -m app.scripts.eval_agent --list
uv run --frozen --extra dev python -m app.scripts.eval_agent
uv run --frozen --extra dev python -m app.scripts.eval_agent --case shipping-mx --case injected-price
```

实际运行前在 backend/.env 配置可用模型地址、名称和密钥。--list 不创建应用资源；评测使用临时数据库，不读取或修改真实演示会话。评测不会进入 CI，实际运行会调用所配置的模型。

默认结果在 evals/results/latest.json，该目录被忽略。报告包含逐条检查、最终回复、商家摘要、来源、工具轨迹和通过率；不记录模型密钥。也可用 --output 指定报告路径。

自动评分是可复核的基线：要求实际成功的工具调用及参数、核对数字/措辞的正则和会话状态；不代表已经证明回复语义完全正确。中文译文的准确性、否定句和不同语言的等价措辞需要人工检查，必要时调整该用例的表达式。报告中附有原始回复，便于逐项核对。

建议手工重点检查：

1. ES 的三个时效与单一美元价没有变化；其他国家都需商家确认。
2. Mars 被澄清；如果调用物流工具，结果必须为失败并含错误说明。
3. 退款/退货只是登记工单，没有承诺已退款或自动批准。
4. 西语咨询的中文摘要含完整译文，分析的 needs_human 标注没有额外创建工单。
5. 数量被记住但不发明阶梯折扣，同一会话重复售后只产生一个未关闭工单。
