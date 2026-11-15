# 全球痛点与真实赚钱机会 24h 自动监控工作台 v10.2

页面只展示实际公开来源抓取结果。金额、`$bid`、`$paid`、平台指标与作者自述分别标记；没有成交数字就显示“原帖未披露具体成交单数”。主页面的百分比是“可行性/证据完整度”，不是成功率承诺。

## 云端运行

`.github/workflows/monitor_20min.yml` 配置为每20分钟尝试运行，也支持手动触发。GitHub计划任务可能排队、延迟或跳过，因此页面会显示最近一次实际完成时间和运行触发方式。

可选Secrets：

- `GEMINI_API_KEY`：Gemini结构化输出。
- `GROQ_API_KEY`：Groq严格JSON Schema输出。
- `DEEPSEEK_API_KEY` 或 `OPENAI_API_KEY`：OpenAI兼容JSON输出。
- `CHATURBATE_WM`：只有官方联盟代码存在时才请求其公开联盟房间API。

未配置大模型Key时，每条新帖子仍由规则引擎生成完整字段，并明确标记 `structured_by: rules-v10.2`。API限流或输出校验失败也会逐条回退，不会留下空白卡片。

## 来源边界

Reddit 16个社区用4个联合公开RSS请求读取；HN使用Algolia公开接口；V2EX使用公开API；BHW和DLsite只发送普通公开请求。遇到403/429会记入 `source_health.json`，不会轮换代理、伪装浏览器指纹或破解验证。成人商业内容只分析授权、结算、营销与创作者服务；不生成欺骗审核、爬虫分流或未授权素材方案。

## 本地验证

```powershell
python opportunity_monitor_24h.py --self-test
python opportunity_monitor_24h.py --cloud-once
python opportunity_monitor_24h.py --serve --port 8765
```

本地服务不会自动打开浏览器。
