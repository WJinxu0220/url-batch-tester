import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import tkinter.font as tkfont
import requests
import time
import urllib3
import csv
import json
import webbrowser
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Thread, Lock
import sys
import os

# 禁用SSL警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# 全局锁，保证GUI更新线程安全
gui_lock = Lock()

class URLTesterGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("批量网站访问工具")
        self.root.geometry("1000x700")
        self.root.resizable(True, True)

        # 全局变量
        self.input_file = tk.StringVar(value="D:/urls_task.csv")
        self.output_file = tk.StringVar(value="D:/results.csv")
        self.timeout = tk.StringVar(value="5")
        self.max_workers = tk.StringVar(value="10")
        self.allow_redirects = tk.BooleanVar(value=True)
        self.open_browser = tk.BooleanVar(value=False)
        self.export_format = tk.StringVar(value="csv")
        self.results = []
        self.is_running = False
        self.executor = None  # 保存线程池实例，用于停止任务
        self.futures = []     # 保存未完成的任务，用于取消
        # 新增：请求重试次数（解决临时网络波动）
        self.retry_times = tk.IntVar(value=1)

        # 创建界面布局
        self._create_widgets()

    def _create_widgets(self):
        # ========== 1. 文件选择区域 ==========
        frame_file = ttk.LabelFrame(self.root, text="文件配置")
        frame_file.pack(fill="x", padx=10, pady=5)

        # 输入文件
        ttk.Label(frame_file, text="输入CSV文件：").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        ttk.Entry(frame_file, textvariable=self.input_file, width=60).grid(row=0, column=1, padx=5, pady=5)
        ttk.Button(frame_file, text="选择文件", command=self._select_input_file).grid(row=0, column=2, padx=5, pady=5)

        # 输出文件
        ttk.Label(frame_file, text="输出结果文件：").grid(row=1, column=0, padx=5, pady=5, sticky="w")
        ttk.Entry(frame_file, textvariable=self.output_file, width=60).grid(row=1, column=1, padx=5, pady=5)
        ttk.Button(frame_file, text="选择文件", command=self._select_output_file).grid(row=1, column=2, padx=5, pady=5)

        # ========== 2. 运行配置区域 ==========
        frame_config = ttk.LabelFrame(self.root, text="运行配置")
        frame_config.pack(fill="x", padx=10, pady=5)

        # 超时时间
        ttk.Label(frame_config, text="请求超时(秒)：").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        ttk.Entry(frame_config, textvariable=self.timeout, width=10).grid(row=0, column=1, padx=5, pady=5)

        # 并发数
        ttk.Label(frame_config, text="并发线程数：").grid(row=0, column=2, padx=5, pady=5, sticky="w")
        ttk.Entry(frame_config, textvariable=self.max_workers, width=10).grid(row=0, column=3, padx=5, pady=5)

        # 重试次数
        ttk.Label(frame_config, text="请求重试次数：").grid(row=0, column=4, padx=5, pady=5, sticky="w")
        ttk.Entry(frame_config, textvariable=self.retry_times, width=10).grid(row=0, column=5, padx=5, pady=5)

        # 跟随跳转
        ttk.Checkbutton(frame_config, text="跟随302跳转", variable=self.allow_redirects).grid(row=0, column=6, padx=5, pady=5)

        # 打开浏览器
        ttk.Checkbutton(frame_config, text="打开成功的网址", variable=self.open_browser).grid(row=0, column=7, padx=5, pady=5)

        # 导出格式
        ttk.Label(frame_config, text="导出格式：").grid(row=0, column=8, padx=5, pady=5, sticky="w")
        ttk.Combobox(frame_config, textvariable=self.export_format, values=["csv", "json"], width=8).grid(row=0, column=9, padx=5, pady=5)

        # ========== 3. 控制按钮区域 ==========
        frame_control = ttk.Frame(self.root)
        frame_control.pack(fill="x", padx=10, pady=5)

        self.btn_start = ttk.Button(frame_control, text="开始运行", command=self._start_running)
        self.btn_start.pack(side="left", padx=5)

        self.btn_stop = ttk.Button(frame_control, text="停止运行", command=self._stop_running, state="disabled")
        self.btn_stop.pack(side="left", padx=5)

        self.btn_export = ttk.Button(frame_control, text="导出结果", command=self._export_results, state="disabled")
        self.btn_export.pack(side="left", padx=5)

        # ========== 4. 进度展示区域 ==========
        frame_progress = ttk.LabelFrame(self.root, text="运行进度")
        frame_progress.pack(fill="x", padx=10, pady=5)

        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(frame_progress, variable=self.progress_var, maximum=100)
        self.progress_bar.pack(fill="x", padx=5, pady=5)

        self.label_progress = ttk.Label(frame_progress, text="就绪")
        self.label_progress.pack(pady=5)

        # ========== 5. 结果展示区域 ==========
        frame_result = ttk.LabelFrame(self.root, text="运行结果")
        frame_result.pack(fill="both", expand=True, padx=10, pady=5)

        # 结果表格
        columns = ("url", "method", "status", "status_code", "response_time", "error")
        self.tree = ttk.Treeview(frame_result, columns=columns, show="headings", height=15)
        
        # 设置列标题和宽度
        self.tree.heading("url", text="网址")
        self.tree.heading("method", text="请求方法")
        self.tree.heading("status", text="状态")
        self.tree.heading("status_code", text="状态码")
        self.tree.heading("response_time", text="响应时间(秒)")
        self.tree.heading("error", text="错误信息")

        self.tree.column("url", width=250)
        self.tree.column("method", width=80)
        self.tree.column("status", width=80)
        self.tree.column("status_code", width=80)
        self.tree.column("response_time", width=100)
        self.tree.column("error", width=300)

        # 滚动条
        scroll_y = ttk.Scrollbar(frame_result, orient="vertical", command=self.tree.yview)
        scroll_x = ttk.Scrollbar(frame_result, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=scroll_y.set, xscrollcommand=scroll_x.set)

        self.tree.pack(side="left", fill="both", expand=True)
        scroll_y.pack(side="right", fill="y")
        scroll_x.pack(side="bottom", fill="x")

        # ========== 6. 日志区域 ==========
        frame_log = ttk.LabelFrame(self.root, text="运行日志")
        frame_log.pack(fill="both", expand=True, padx=10, pady=5)

        self.text_log = tk.Text(frame_log, height=5, wrap="none")
        scroll_log_y = ttk.Scrollbar(frame_log, orient="vertical", command=self.text_log.yview)
        scroll_log_x = ttk.Scrollbar(frame_log, orient="horizontal", command=self.text_log.xview)
        self.text_log.configure(yscrollcommand=scroll_log_y.set, xscrollcommand=scroll_log_x.set)

        self.text_log.pack(side="left", fill="both", expand=True)
        scroll_log_y.pack(side="right", fill="y")
        scroll_log_x.pack(side="bottom", fill="x")

    def _select_input_file(self):
        file_path = filedialog.askopenfilename(
            title="选择输入CSV文件",
            filetypes=[("CSV文件", "*.csv"), ("所有文件", "*.*")]
        )
        if file_path:
            self.input_file.set(file_path)

    def _select_output_file(self):
        file_path = filedialog.asksaveasfilename(
            title="选择输出文件",
            filetypes=[("CSV文件", "*.csv"), ("JSON文件", "*.json"), ("所有文件", "*.*")]
        )
        if file_path:
            # 自动补充后缀（如果用户没加）
            export_format = self.export_format.get()
            if not file_path.endswith(f".{export_format}"):
                file_path = f"{file_path}.{export_format}"
            self.output_file.set(file_path)

    def _log(self, msg):
        """添加日志信息（线程安全）"""
        with gui_lock:
            self.text_log.insert(tk.END, f"[{time.strftime('%H:%M:%S')}] {msg}\n")
            self.text_log.see(tk.END)
            self.root.update_idletasks()

    def _clear_results(self):
        """清空结果表格（线程安全）"""
        with gui_lock:
            for item in self.tree.get_children():
                self.tree.delete(item)
            self.results = []
            self.root.update_idletasks()

    def _safe_tree_insert(self, values):
        """线程安全的表格插入"""
        with gui_lock:
            self.tree.insert("", tk.END, values=values)
            self.root.update_idletasks()

    def _start_running(self):
        """开始运行（子线程执行，避免阻塞GUI）"""
        if self.is_running:
            messagebox.showwarning("提示", "程序正在运行中！")
            return

        # 验证参数
        try:
            timeout = int(self.timeout.get())
            max_workers = int(self.max_workers.get())
            retry_times = int(self.retry_times.get())
            if timeout <= 0 or max_workers <= 0 or max_workers > 50 or retry_times < 0 or retry_times > 3:
                raise ValueError
        except ValueError:
            messagebox.showerror("错误", "超时时间必须为正整数，并发数需为1-50，重试次数0-3！")
            return

        # 清空之前的结果
        self._clear_results()
        self._log("="*50)
        self._log("开始执行批量网站访问任务")
        self._log(f"输入文件：{self.input_file.get()}")
        self._log(f"超时时间：{timeout}秒 | 并发数：{max_workers} | 重试次数：{retry_times}")

        # 更新按钮状态
        self.btn_start.config(state="disabled")
        self.btn_stop.config(state="normal")
        self.btn_export.config(state="disabled")
        self.is_running = True
        self.progress_var.set(0)
        self.label_progress.config(text="初始化中...")

        # 子线程执行任务
        thread = Thread(target=self._run_task, args=(timeout, max_workers, retry_times))
        thread.daemon = True
        thread.start()

    def _stop_running(self):
        """停止运行（优雅终止线程池）"""
        self.is_running = False
        # 取消未完成的任务
        if self.futures:
            for future in self.futures:
                if not future.done():
                    future.cancel()
        # 关闭线程池
        if self.executor:
            self.executor.shutdown(wait=False)
        self.btn_start.config(state="normal")
        self.btn_stop.config(state="disabled")
        self._log("用户手动停止运行，正在终止未完成任务...")

    def _run_task(self, timeout, max_workers, retry_times):
        """执行批量访问任务"""
        try:
            # 1. 读取URL列表
            self.label_progress.config(text="读取文件中...")
            tasks = self._read_urls_from_file(self.input_file.get())
            if not tasks:
                raise Exception("未读取到有效任务")

            total_tasks = len(tasks)
            self._log(f"成功读取 {total_tasks} 个有效任务")

            # 2. 并发访问
            self.label_progress.config(text="开始访问网站...")
            self.results = []
            completed = 0
            self.futures = []

            self.executor = ThreadPoolExecutor(max_workers=max_workers)
            future_to_task = {}
            for task in tasks:
                if not self.is_running:
                    break
                future = self.executor.submit(self._visit_url, task, timeout, retry_times)
                future_to_task[future] = task
                self.futures.append(future)

            for future in as_completed(future_to_task):
                if not self.is_running:
                    break

                task = future_to_task[future]
                completed += 1
                progress = (completed / total_tasks) * 100
                self.progress_var.set(progress)
                self.label_progress.config(text=f"进度：{completed}/{total_tasks} ({progress:.1f}%)")

                try:
                    result = future.result()
                    self.results.append(result)
                    # 线程安全的表格插入
                    self._safe_tree_insert((
                        result['url'],
                        result['method'],
                        result['status'],
                        result['status_code'] or "",
                        result['response_time'],
                        result['error'][:100] if result['error'] else ""
                    ))
                    # 日志
                    status = "✅" if result['status'] == "成功" else "❌"
                    self._log(f"{status} {result['url']} | {result['status']} | 状态码：{result['status_code'] or '无'}")

                except Exception as e:
                    err_msg = str(e)[:50]
                    self._log(f"⚠️ {task['url']} | 执行异常：{err_msg}")
                    self.results.append({
                        'url': task['url'],
                        'method': task['method'],
                        'status': '异常',
                        'status_code': '',
                        'response_time': 0,
                        'error': str(e)
                    })

            # 3. 结果汇总
            if self.is_running:
                success = sum(1 for r in self.results if r['status'] == '成功')
                fail = sum(1 for r in self.results if r['status'] == '失败')
                exception = sum(1 for r in self.results if r['status'] == '异常')
                total_time = round(sum(r['response_time'] for r in self.results), 2)

                self._log("="*50)
                self._log(f"任务执行完成 | 成功：{success} | 失败：{fail} | 异常：{exception}")
                self._log(f"总耗时：{total_time}秒 | 平均响应时间：{round(total_time/len(self.results), 2) if self.results else 0}秒")
                self.label_progress.config(text=f"完成！成功{success}个，失败{fail}个")
                self.btn_export.config(state="normal")
            else:
                self._log("任务被用户终止")
                self.label_progress.config(text="已终止")

        except Exception as e:
            self._log(f"执行出错：{str(e)}")
            messagebox.showerror("错误", f"执行出错：{str(e)}")
            self.label_progress.config(text="执行出错")

        # 恢复按钮状态
        self.is_running = False
        self.btn_start.config(state="normal")
        self.btn_stop.config(state="disabled")
        self.progress_var.set(100)
        self.executor = None
        self.futures = []

    def _read_urls_from_file(self, file_path):
        """读取URL列表（兼容GBK/UTF-8编码）"""
        tasks = []
        encodings = ['utf-8', 'gbk', 'gb2312', 'utf-8-sig']  # 尝试多种编码
        for encoding in encodings:
            try:
                with open(file_path, 'r', encoding=encoding) as f:
                    reader = csv.DictReader(f)
                    if 'url' not in reader.fieldnames:
                        raise Exception("CSV文件缺少'url'表头")

                    for row_num, row in enumerate(reader, 2):
                        url = (row.get('url', '') or '').strip()
                        method = (row.get('method', '') or '').strip().upper() or 'GET'
                        data = row.get('data', '') or ''
                        headers = row.get('headers', '{}') or '{}'
                        cookies = row.get('cookies', '{}') or '{}'

                        if url and not url.startswith('#'):
                            tasks.append({
                                'url': url,
                                'method': method,
                                'data': data,
                                'headers': headers,
                                'cookies': cookies
                            })
                        else:
                            self._log(f"跳过无效行（第{row_num}行）：URL为空或注释")
                self._log(f"使用 {encoding} 编码成功读取文件")
                return tasks
            except UnicodeDecodeError:
                continue
            except Exception as e:
                raise Exception(f"读取文件失败（{encoding}编码）：{str(e)}")
        raise Exception("文件编码不支持（仅支持UTF-8/GBK/GB2312）")

    def _visit_url(self, task, timeout, retry_times):
        """访问单个URL（带重试机制，修复timeout参数错误）"""
        url = task['url']
        method = task['method']
        data = task['data']
        
        # 安全解析JSON（避免格式错误崩溃）
        try:
            headers = json.loads(task['headers']) if task['headers'] else {}
        except:
            headers = {}
            self._log(f"⚠️ {url} | Headers JSON格式错误，使用空Headers")
        
        try:
            cookies = json.loads(task['cookies']) if task['cookies'] else {}
        except:
            cookies = {}
            self._log(f"⚠️ {url} | Cookies JSON格式错误，使用空Cookies")

        # 补全URL前缀
        if not url.startswith(('http://', 'https://')):
            url_https = f'https://{url}'
            # 先试HTTPS，失败重试HTTP
            result = self._send_request_with_retry(url_https, method, headers, cookies, data, timeout, retry_times)
            if result['status'] == '失败':
                url_http = f'http://{url}'
                result = self._send_request_with_retry(url_http, method, headers, cookies, data, timeout, retry_times)
            return result
        else:
            return self._send_request_with_retry(url, method, headers, cookies, data, timeout, retry_times)

    def _send_request_with_retry(self, url, method, headers, cookies, data, timeout, retry_times):
        """发送HTTP请求（带重试机制，修复timeout参数错误）"""
        # 重试逻辑
        for retry in range(retry_times + 1):
            try:
                return self._send_request(url, method, headers, cookies, data, timeout)
            except Exception as e:
                if retry < retry_times:
                    self._log(f"⚠️ {url} | 第{retry+1}次请求失败，重试中...（错误：{str(e)[:30]}）")
                    time.sleep(0.5)  # 重试前短暂等待
                else:
                    # 所有重试都失败
                    response_time = round(time.time() - start_time, 2) if 'start_time' in locals() else 0
                    return {
                        'url': url,
                        'method': method,
                        'status': '失败',
                        'status_code': '',
                        'response_time': response_time,
                        'error': str(e)
                    }

    def _send_request(self, url, method, headers, cookies, data, timeout):
        """发送HTTP请求（核心修复：移除不支持的timeout_connect参数）"""
        start_time = time.time()
        try:
            # 设置默认请求头，避免被拦截
            if not headers:
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                    'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
                    'Accept-Encoding': 'gzip, deflate',
                    'Connection': 'keep-alive',
                    'Cache-Control': 'max-age=0'
                }
            
            # 处理POST数据
            post_data = None
            if method == 'POST':
                # 尝试解析JSON数据，否则用表单格式
                try:
                    post_data = json.loads(data) if data else {}
                except:
                    post_data = data if data else {}

            # 核心修复：移除timeout_connect，只用标准timeout参数
            response = None
            if method == 'GET':
                response = requests.get(
                    url, 
                    headers=headers, 
                    cookies=cookies, 
                    timeout=timeout,  # 仅保留标准timeout参数
                    allow_redirects=self.allow_redirects.get(), 
                    verify=False  # 忽略SSL证书验证
                )
            elif method == 'POST':
                response = requests.post(
                    url, 
                    headers=headers, 
                    cookies=cookies, 
                    data=post_data, 
                    timeout=timeout,
                    allow_redirects=self.allow_redirects.get(), 
                    verify=False
                )
            elif method == 'HEAD':
                response = requests.head(
                    url, 
                    headers=headers, 
                    cookies=cookies, 
                    timeout=timeout,
                    allow_redirects=self.allow_redirects.get(), 
                    verify=False
                )
            else:
                raise ValueError(f"不支持的请求方法：{method}")

            response_time = round(time.time() - start_time, 2)
            
            # 打开浏览器（如果启用）- 放到主线程执行
            if self.open_browser.get() and self.is_running:
                self.root.after(0, lambda u=url: webbrowser.open(u))

            return {
                'url': url,
                'method': method,
                'status': '成功',
                'status_code': response.status_code,
                'response_time': response_time,
                'error': ''
            }
        except requests.exceptions.Timeout:
            response_time = round(time.time() - start_time, 2)
            return {
                'url': url,
                'method': method,
                'status': '失败',
                'status_code': '',
                'response_time': response_time,
                'error': "请求超时"
            }
        except requests.exceptions.ConnectionError:
            response_time = round(time.time() - start_time, 2)
            return {
                'url': url,
                'method': method,
                'status': '失败',
                'status_code': '',
                'response_time': response_time,
                'error': "连接失败（域名/IP不可达）"
            }
        except requests.exceptions.SSLError:
            response_time = round(time.time() - start_time, 2)
            return {
                'url': url,
                'method': method,
                'status': '失败',
                'status_code': '',
                'response_time': response_time,
                'error': "SSL证书验证失败（已忽略验证仍失败）"
            }
        except requests.exceptions.RequestException as e:
            response_time = round(time.time() - start_time, 2)
            return {
                'url': url,
                'method': method,
                'status': '失败',
                'status_code': '',
                'response_time': response_time,
                'error': f"请求异常：{str(e)[:50]}"
            }
        except Exception as e:
            response_time = round(time.time() - start_time, 2)
            return {
                'url': url,
                'method': method,
                'status': '失败',
                'status_code': '',
                'response_time': response_time,
                'error': str(e)
            }

    def _export_results(self):
        """导出结果（增强容错）"""
        if not self.results:
            messagebox.showwarning("提示", "暂无结果可导出！")
            return

        try:
            export_format = self.export_format.get()
            output_file = self.output_file.get()

            # 确保目录存在
            output_dir = os.path.dirname(output_file)
            if not os.path.exists(output_dir):
                os.makedirs(output_dir)

            if export_format == 'csv':
                with open(output_file, 'w', encoding='utf-8', newline='') as f:
                    writer = csv.DictWriter(f, fieldnames=self.results[0].keys())
                    writer.writeheader()
                    writer.writerows(self.results)
            else:
                with open(output_file, 'w', encoding='utf-8') as f:
                    json.dump(self.results, f, ensure_ascii=False, indent=2)

            self._log(f"结果已导出到：{output_file}")
            messagebox.showinfo("成功", f"结果已成功导出到：{output_file}")
        except PermissionError:
            self._log("导出失败：没有文件写入权限")
            messagebox.showerror("错误", "导出失败：没有文件写入权限，请检查输出路径是否可写！")
        except Exception as e:
            self._log(f"导出失败：{str(e)}")
            messagebox.showerror("错误", f"导出失败：{str(e)}")

if __name__ == '__main__':
    # 确保中文显示正常
    root = tk.Tk()
    # 设置字体（解决Windows中文乱码）
    try:
        default_font = tkfont.nametofont("TkDefaultFont")
        default_font.configure(family="SimHei", size=9)
        root.option_add("*Font", default_font)
    except:
        # 兼容不同系统字体
        default_font = tkfont.nametofont("TkDefaultFont")
        default_font.configure(size=9)
        root.option_add("*Font", default_font)
    
    app = URLTesterGUI(root)
    root.mainloop()
