---
tags: [tiktok, ms_token, setup]
date: 2026-04-10
status: active
---
# TikTok `ms_token` 获取方法

## o9wyuiM8NlQYsgJJ1nmj8imsoQkHbJUSAC1PZNW_mmoS0SZ26kc3FPMooo4LMoz3QpcxoOXB7ANfn4FKSwzy7q-g8GqvkkDMsYyWKl7T9qLo22zByb_EZTsYnEhTpT7soCz-qV8B137D


Pld35mLCkwXR5WRBwHSj_e-Fpg4ecWh_xHe6O67xtv0P3n13QsEvECesC_WUnDfXqBKUj9XUmDL8Axv9BquZUwQA-Jw7Xkpio2_4dO0CZKB8ibKvYJTL9rFVb2Ye84zgnAFbxd0bR6fU

G--CvmhLekmiWLj_8fj5d0WWEggy53bnEzFcu0wOxusSftEusV1ipUDHz0_5LaiBCmm5y6GNY-QQKe0KOOfRQ9JoIwJjzRmqO6va_jWj2ru-cXnaXHS_3QHOJSbmSgbvdePT_pmHRPUI

## 目的

这一步不是为了登录 TikTok API，而是为了提高 TikTok 网页端抓取的可用性和稳定性。

## 最简单的方法

1. 在浏览器里打开 `https://www.tiktok.com/`
2. 登录你的 TikTok 账号
3. 打开开发者工具
4. 进入 `Application` 或 `Storage`
5. 找到 `Cookies`
6. 选择 `https://www.tiktok.com`
7. 搜索 cookie 名：`ms_token`
8. 复制它的值

如果你习惯从 `Network` 面板看也可以：

1. 打开 TikTok 任意搜索结果页
2. 找一个请求
3. 查看请求头里的 `cookie`
4. 找到 `ms_token=...`
5. 只复制等号后面的值

## 拿到后放哪里

写入这个文件：

- [\.env.local](${ROCKBASE_HOME}/我的云端硬盘%20(<YOUR_ACCOUNT_EMAIL>)/Google%20Drive/Obsidian/My%20vault/400%20🔴%20Project/🔴%20402%20Social%20Agency/⚪%20skills/S1-inbox-kol-fuzzy-discovery-tiktok-skill/.env.local)

对应字段：

```env
TIKTOK_MS_TOKEN=这里填你的真实值
```

## 注意

- 只复制 value，不要连 `ms_token=` 一起复制进去
- 不要写入 shared global env
- 这个值可能会过期，后面失效时再换新值即可

## 2026-04-10 测试结论

基于当前 TikTok skill 的本地测试：

- 第 `2` 组 token 可用
- 第 `1` 组 token 超时
- 第 `3` 组 token 超时

当前已验证可用的 token 是：

```text
Pld35mLCkwXR5WRBwHSj_e-Fpg4ecWh_xHe6O67xtv0P3n13QsEvECesC_WUnDfXqBKUj9XUmDL8Axv9BquZUwQA-Jw7Xkpio2_4dO0CZKB8ibKvYJTL9rFVb2Ye84zgnAFbxd0bR6fU
```

补充说明：

- 这次测试里，`user search` 已经成功
- `item/content search` 仍然返回 bot-detected 的空响应
- 说明当前 `ms_token + static proxy + TikTokApi` 已经足够验证 account-side search
- 但要满足最终的 `content-first hot-content L1`，还需要下一步继续处理内容搜索路径
