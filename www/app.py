#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging; logging.basicConfig(level=logging.INFO)

# 导入各种模块
import asyncio, os, json, time
# 导入时间戳模块
from datetime import datetime

from aiohttp import web

def index(request):
	return web.Response(body=b'<h1>Awesome</h1>')

# 或者使用a
# @asyncio.coroutine
# def init():
async init(loop):
	app = web.Application(loop=loop)
	app.router.add_route('GET','/',index)
	# 创建服务器端 地址为127.0.0.1 端口为9000
	srv = await loop.create_server(app.make_handler(), '127.0.0.1', 9000)
	# logging在文件最开头处导入
	logging.info('server started at http://127.0.0.1:9000')
	return srv

# 创建一个 asyncio对象
loop = asyncio.get_event_loop()
# 将要异步执行的函数放入下面的方法中
loop.run_until_complete(init(loop))
loop.run_forever()