#!/usr/bin/env python3
# -*- coding: utf-8 -*-

'This is a homework--day 1'

__author__ = 'luisfly'



import logging; logging.basicConfig(level=logging.INFO)

# 导入各种模块
import asyncio, os, json, time
# 导入时间戳模块
from datetime import datetime

from aiohttp import web
from jinja2 import Environment, FileSystemLoader

import orm
from coroweb import add_routes, add_static

from handlers import cookie2user, COOKIE_NAME

# 本本件主要是负责 html 模板获取
# 以及 cookie 获取 后续操作


# 初始化 jinja2
def init_jinja2(app, **kw):
	logging.info('init jinja2...')
	options = dict(
		autoescape = kw.get('autoescape', True),
		block_start_string = kw.get('block_start_string', '{%'),
		block_end_string = kw.get('block_end_string', '%}'),
		variable_start_string = kw.get('variable_start_string', '{{'),
		variable_end_string = kw.get('variable_end_string', '}}'),
		auto_reload = kw.get('auto_reload', True)
	)
	# 从传入参数获得路径
	path = kw.get('path', None)
	# 获取 templates文件夹路径
	if path is None:
		path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates')
	logging.info('set jinja2 template path: %s' % path)
	# 利用jinja2加载模板
	env = Environment(loader=FileSystemLoader(path), **options)
	# 获取参数
	filters = kw.get('filters', None)
	if filters is not None:
		for name, f in filters.items():
			env.filters[name] = f
	# 将模板赋予 对象的 __templating__ 属性
	app['__templating__'] = env

# 日记工厂
async def logger_factory(app, handler):
	async def logger(request):
		# 获取 http 请求内容的信息
		# 主要为请求的类型以及请求的路径
		logging.info('Request: %s %s' % (request.method, request.path))
		# await asyncio.sleep(0.3)
		return (await handler(request))
	return logger

# 解析 cookie生成 request.__user__ 对象
# 这里同时内置了权限管理，当当前 cookie 中的登录用户非管理员时
# 该用户将无法进入 blog 修改界面
async def auth_factory(app, handler):
	async def auth(request):
		logging.info('check user: %s %s' % (request.method, request.path))
		request.__user__ = None
		# 获取 cookie 数据
		cookie_str = request.cookies.get(COOKIE_NAME)
		if cookie_str:
			user = await cookie2user(cookie_str)
			if user:
				logging.info('set current user: %s' % user.email)
				request.__user__ = user
		# requset.__user__.admin 就是判断当前用户是否是管理员
		if request.path.startswith('/manage/') and (request.__user__ is None or not request.__user__.admin):
			return web.HTTPFound('/signin')
		return (await handler(request))
	return auth

# 数据工厂
async def data_factory(app, handler):
	async def parse_data(request):
		# 如果请求为 post 即带有用户数据的 http 请求
		# 数据工厂将自动提取数据内容
		if request.method == 'POST':
			if request.content_type.startswith('application/json'):
				request.__data__ = await request.json()
				logging.info('request json: %s' % str(request.__data__))
			elif request.content_type.startswith('application/x-www-form-urlencoded'):
				request.__data__ = await request.post()
				logging.info('request form: %s' % str(request.__data__))
		return (await handler(request))
	return parse_data

# 回应操作工厂
async def response_factory(app, handler):
	async def response(request):
		logging.info('Response handler...')
		r = await handler(request)
		if isinstance(r, web.StreamResponse):
			return r
		# 如果是二进制字节流 将更改 http 头，以及传输数据类型
		if isinstance(r, bytes):
			resp = web.Response(body=r)
			resp.content_type = 'application/octet-stream'
			return resp
		# 如果是字符串类型 更改 http 头，以及传输数据类型
		if isinstance(r, str):
			if r.startswith('redirect:'):
				return web.HTTPFound(r[9:])
			resp = web.Response(body=r.encode('utf-8'))
			resp.content_type = 'text/html;charset=utf-8'
			return resp
		# 如果过是 json 读取模板
		if isinstance(r, dict):
			template = r.get('__template__')
			if template is None:
				# body 参数即为页面显示的主体内容
				resp = web.Response(body=json.dumps(r, ensure_ascii=False, default=lambda o: o.__dict__).encode('utf-8'))
				resp.content_type = 'application/json;charset=utf-8'
				return resp
			else:
				# 第一句与登录密切相关 r是 增加 post 中的参数数量
				r['__user__'] = request.__user__
				resp = web.Response(body=app['__templating__'].get_template(template).render(**r).encode('utf-8'))
				resp.content_type = 'text/html;charset=utf-8'
				return resp
		# 如果是整型数据
		if isinstance(r, int) and r >= 100 and r < 600:
			return web.Response(r)
		if isinstance(r, tuple) and len(r) == 2:
			t, m = r
			if isinstance(t, int) and t >= 100 and t < 600:
				return web.Response(t, str(m))
		# default:
		resp = web.Response(body=str(r).encode('utf-8'))
		resp.content_type = 'text/plain;charset=utf-8'
		return resp
	return response

def datetime_filter(t):
	delta = int(time.time() - t)
	if delta < 60:
		return u'1分钟前'
	if delta < 3600:
		return u'%s分钟前' % (delta // 60)
	if delta < 86400:
		return u'%s小时前' % (delta // 3600)
	if delta < 604800:
		return u'%s天前' % (delta // 86400)
	dt = datetime.fromtimestamp(t)
	return u'%s年%s月%s日' % (dt.year, dt.month, dt.day)

# 初始化
async def init(loop):
	# 创建线程池
	await orm.create_pool(loop=loop, host='localhost', port=3306, user='myadmin', password='1234', database='awesome')
	app = web.Application(loop=loop, middlewares=[
		logger_factory, auth_factory, response_factory
	])
	# 初始化前端模板，并把模板绑定到 app的属性中
	init_jinja2(app, filters=dict(datetime=datetime_filter))
	add_routes(app, 'handlers')
	add_static(app)
	srv = await loop.create_server(app.make_handler(), '127.0.0.1', 9000)
	logging.info('server started at http://127.0.0.1:9000...')
	return srv

loop = asyncio.get_event_loop()
loop.run_until_complete(init(loop))
loop.run_forever()


#def index(request):
	# 注意：此处的web.Response 必须要添加 content_type参数
	# 否则 chrome将无法解析，进而直接将文件下载
#	return web.Response(body=b'<h1>Awesome</h1>',content_type='text/html')

# 或者使用a
# @asyncio.coroutine
# def init():
# async def init(loop):
#	app = web.Application(loop=loop)
#	app.router.add_route('GET','/',index)
	# 创建服务器端 地址为127.0.0.1 端口为9000
#	srv = await loop.create_server(app.make_handler(), '127.0.0.1', 9000)
	# logging在文件最开头处导入
#	logging.info('server started at http://127.0.0.1:9000')
#	return srv

# 创建一个 asyncio对象
# loop = asyncio.get_event_loop()
# 将要异步执行的函数放入下面的方法中
# loop.run_until_complete(init(loop))
# loop.run_forever()
