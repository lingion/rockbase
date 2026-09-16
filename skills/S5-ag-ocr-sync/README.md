# S5 OCR Sync

从达人截图提取账号、受众和联系方式字段并回填到表格。需要图片和 OCR/Vision 依赖；写入前先输出可复核预览，生产主表需先备份。

V2 依赖：`base,ocr`；使用外部 Vision 模型时另加其 SDK。本入口未纳入 V2 干净环境 smoke。
