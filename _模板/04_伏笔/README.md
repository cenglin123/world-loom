# 伏笔

> 伏笔登记表——open/closed 状态机。**不登记 = 不存在 = 收不回来。**

## 文件

- `伏笔登记表.md`：全部伏笔登记（ID / 内容 / 预期回收方式 / 状态 / 期限）

## 怎么用

1. 写正文时埋下新伏笔 → 立刻登记，状态=open，设定回收期限
2. 回收伏笔 → 状态改为 closed，记录实际回收方式
3. 每卷复盘检查 open 伏笔是否超期

## 工具

- `python scripts/check_foreshadowing.py` — 伏笔完整性 + 超期检查
- `python scripts/check_all.py` — 全仓检查含伏笔项
