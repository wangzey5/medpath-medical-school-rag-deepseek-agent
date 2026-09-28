# MedPath 美国医学院申请助手

一个本地运行的 RAG 原型：上传个人申请资料，优先从知识库检索；资料不足时可调用 DeepSeek 生成补充回答。

## 运行

```bash
python3 -m pip install -r requirements.txt
python3 server.py
```

浏览器访问 `http://127.0.0.1:8000`。

如果所在网络通过单位代理注入自定义 HTTPS 证书，可以在启动前指定 CA 文件：

```bash
DEEPSEEK_CA_BUNDLE=/path/to/company-ca.pem python3 server.py
```

## 功能

- 上传 PDF、TXT、Markdown、CSV、JSON 文档
- 本地切分、索引和关键词相似度检索
- 知识库、智能、DeepSeek 三种回答模式
- 展示知识库命中文档和原文片段
- DeepSeek API Key 仅保存在浏览器 `localStorage`，服务端不持久化
- 可添加自定义 System Prompt；知识库上下文和 User Prompt 模板保持固定
- DeepSeek Function Calling 工具：官方来源检索、申请时间线、院校比较、申请档案评估、先修课匹配、GPA/费用计算器
- 支持对话上下文和移动端布局

## 数据与限制

- 文档及索引保存在本机 `data/` 目录。
- DeepSeek 模型不是实时搜索引擎。政策、截止日期、学费及院校要求必须回到 AAMC、AACOMAS 或院校官网核验。
- 当前检索器是轻量本地实现，适合课程 Demo。生产环境建议替换为 Embedding + 向量数据库，并增加用户认证、加密存储、文件病毒扫描和访问审计。
