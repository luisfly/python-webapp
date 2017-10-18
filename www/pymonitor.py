#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# 监视网页的主文件夹的变化
# 并且可以自动重启服务器
# 避免人工重启服务器
# 用户仅需刷新页面即可看到页面的变化
# 大大地降低了编程人员的编程难度
__author__ = 'luisfly'

import os, sys, time, subprocess

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# 日志编写
def log(s):
	print('[Monitor] %s' % s)

# 当文件发生变化的处理函数
class MyFileSystemEventHander(FileSystemEventHandler):

	def __init__(self, fn):
		super(MyFileSystemEventHander, self).__init__()
		self.restart = fn

	# 检测是否有新的 .py 文件出现
	# 自动重新启动服务器
	def on_any_event(self, event):
		if event.src_path.endswith('.py'):
			log('Python source file changed: %s' % event.src_path)
			self.restart()

command = ['echo', 'ok']
process = None

# 杀死进程
def kill_process():
	global process
	if process:
		# 输出日志
		log('kill process [%s]...' % process.pid)
		process.kill()
		process.wait()
		log('Process ended with code %s.' % process.returncode)
		process = None

# 启动进程
def start_process():
	global process, command
	# 输出日志
	log('Start process %s...' % ' '.join(command))
	process = subprocess.Popen(command, stdin=sys.stdin, stdout=sys.stdout, stderr=sys.stderr)

# 重启进程
# 先杀死进程后 再启动
def restart_process():
	kill_process()
	start_process()

# 监视
def start_watch(path, callback):
	observer = Observer()
	# 调用 MyFileSystemEventHander
	# 绑定属性 restart = restart_process
	observer.schedule(MyFileSystemEventHander(restart_process), path, recursive=True)
	# 监视开始
	observer.start()
	log('Watching directory %s...' % path)
	# 启动进程
	start_process()
	try:
		while True:
			time.sleep(0.5)
	# 如果触发键盘打断事件
	# 退出监视
	except KeyboardInterrupt:
		observer.stop()
	observer.join()

# 判断是否是直接调用该函数的
if __name__ == '__main__':
	argv = sys.argv[1:]
	if not argv:
		print('Usage: ./pymonitor your-script.py')
		exit(0)
	if argv[0] != 'python3':
		argv.insert(0, 'python3')
	command = argv
	path = os.path.abspath('.')
	start_watch(path, None)