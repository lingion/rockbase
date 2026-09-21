# S5 OCR Sync

从达人截图提取账号、受众和联系方式字段并回填到表格。需要图片和 OCR/Vision 依赖；写入前先输出可复核预览，生产主表需先备份。

服务器推荐显式使用 `--ocr-engine llm`，直接调用部署侧 OpenAI-compatible 多模态 endpoint；配置 `OPENAI_API_KEY`、`--llm-base-url` 和 `--llm-model`。原有 `auto|vision|tesseract` 路径保留。

V2 依赖：`base,ocr,llm`；LLM 路径不依赖 macOS Swift，但模型必须支持图片输入。
