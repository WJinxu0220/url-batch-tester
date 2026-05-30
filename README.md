# 批量网站访问工具 (URL Batch Tester)

一个基于Python Tkinter开发的GUI工具，支持批量检测URL可达性、响应时间、状态码，支持并发请求、重试机制、结果导出（CSV/JSON）。

## 功能特性

- 📁 支持CSV导入URL列表（兼容UTF-8/GBK编码）

- ⚡ 多线程并发访问（可配置并发数）
- 🔄 失败自动重试（可配置重试次数）

- 🕒 自定义请求超时时间

- 📊 实时展示访问结果（URL/状态码/响应时间/错误信息）

- 💾 结果导出（CSV/JSON格式）

- 🌐 自动补全HTTP/HTTPS前缀，支持302跳转跟随

- 🌍 中文界面，适配Windows系统字体

## 环境要求

\- Python 3.7

## 安装依赖

PIP install -r requirements.txt

## 使用方法

1、克隆 / 下载项目到本地
2、安装依赖：pip install -r requirements.txt
3、运行工具：python url_batch_tester.py
4、配置参数：
输入 CSV 文件：需包含url列（必填），可选method（请求方法）、data（POST 数据）、headers、cookies列
超时时间：建议 5-10 秒
并发数：建议 10-20（过高易被目标服务器拦截）
重试次数：0-3 次（解决临时网络波动）
5、点击「开始运行」，等待执行完成后可导出结果





