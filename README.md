# FluxTask

一个私有化的、具有反爬虫对抗能力的定时任务调度平台 (GitHub Actions 复刻版)。

## 功能特性

- **可视化面板**: 现代化的 Vue3 + NaiveUI 界面，支持深色模式。
- **在线编辑**: 集成 Monaco Editor，网页端直接编写 Python 脚本。
- **反爬虫设计**: 支持 Cron 表达式 + 随机延时 (Random Delay) 执行，模拟真人操作。
- **Secrets 管理**: 环境变量加密存储，脚本中直接读取。
- **Docker 部署**: 开箱即用，支持多架构。

## 快速开始

### 1. 启动服务


### 🛠️ 必须要做的修改 (Python 脚本)

在 GitHub Actions 中，有时即便不加某些参数也能跑，但在 Docker 容器内，**必须**加上以下参数，否则 Chrome 进程会崩溃：

在你的脚本 `setup_driver` 部分，确保有这三行：

```python
chrome_options.add_argument('--headless')           # 无头模式 (Docker 没有显示器)
chrome_options.add_argument('--no-sandbox')         # 禁止沙盒 (Root用户运行必须加)
chrome_options.add_argument('--disable-dev-shm-usage') # 解决 Docker 内存共享问题
```
