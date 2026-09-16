# OpenCLI Scripts

本目录保留 `OpenCLI Browser Bridge` 路线的脚本入口。

当前已落位：

- `s1_opencli_easykol_writeback.py`
  - OpenCLI EasyKOL 批量 writeback 主入口
- `internal/session_runtime.py`
  - `open / wait / eval` 封装
- `internal/extractors/youtube_easykol.py`
  - YouTube EasyKOL 提取
- `internal/extractors/tiktok_easykol.py`
  - TikTok EasyKOL 提取
- `internal/extractors/instagram_easykol.py`
  - Instagram EasyKOL 提取
- `internal/extractors/common.py`
  - 平台路由、session 默认值、结果 contract

推荐用法：

```bash
python3 '.../scripts/opencli/s1_opencli_easykol_writeback.py' \
  --csv-path '/abs/path/to/file.csv' \
  --platform youtube \
  --rows '14-18' \
  --slug 'yt_preview_rows14_18' \
  --workbench-dir '/abs/path/to/workbench/2026-05-29'
```

正式写回时加：

```bash
--write
```

与现有目录分工：

- `scripts/browser/`
  - 通用浏览器抽取
- `scripts/codex_chrome/`
  - Codex Chrome extension 路线
- `scripts/opencli/`
  - OpenCLI Browser Bridge 路线
