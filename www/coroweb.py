#!/usr/bin/env python3
# -*- coding: utf-8 -*-

__author__ = 'luisfly'

import asyncio, os, inspect, logging, functools

from urllib import parse
from aiohttp import web
from apis import APIError

# 定义装饰器 @get
def get(path):
	'''
	Define decorator @get('/path')
	'''
	def decorator(func):
		@functools.wraps(func)
		def wrapper(*args, **kw):
			return func(*args, **kw)
		wrapper.__method__ = 'GET'
		wrapper.__route__ = path
		return wrapper
	return decorator

# 定义装饰器 @post
def post(path):
	'''
	Define decorator @post('/path')
	'''
	def decorator(func):
		@functools.wraps(func)
		def wrapper(*args, **kw):
			return func(*args, **kw)
		wrapper.__method__ = 'POST'
		wrapper.__route__ = path
		return wrapper
	return decorator

def get_required_kw_args(fn):
	args = []
	# inpsect.signature(fn) 获取函数的参数
	params = inspect.signature(fn).parameters
	for name, param in params.items():
		# 判断参数是否是关键字参数 而且 还是不是带有默认值的
		# 若没有默认值而且创建时只有名字 添加到 tuple中返回
		if param.kind == inspect.Parameter.KEYWORD_ONLY and param.default == inspect.Parameter.empty:
			args.append(name)
	return tuple(args)

# 返回创建时没有默认值 且参数是否是关键字参数，命名参数	
def get_named_kw_args(fn):
	args = []
	params = inspect.signature(fn).parameters
	for name, param in params.items():
		if param.kind == inspect.Parameter.KEYWORD_ONLY:
			args.append(name)
	return tuple(args)

# 检测参数中是否存在 关键字参数
# 即没有制定参数类型或者初始值的对象
def has_named_kw_args(fn):
	params = inspect.signature(fn).parameters
	for name, param in params.items():
		if param.kind == inspect.Parameter.KEYWORD_ONLY:
			return True

# 判断是否存在 者指针的可变参数类型
def has_var_kw_arg(fn):
	params = inspect.signature(fn).parameters
	for name, param in params.items():
		if param.kind == inspect.Parameter.VAR_KEYWORD:
			return True

# 寻找函数参数列表中是否有 request参数
def has_request_arg(fn):
	sig = inspect.signature(fn)
	params = sig.parameters
	found = False
	for name, param in params.items():
		if name == 'request':
			found = True
			continue
		# 如果参数在第一位，而又不是request将报错
		# 第一位的参数的参数类型为
		if found and (param.kind != inspect.Parameter.VAR_POSITIONAL and param.kind != inspect.Parameter.KEYWORD_ONLY and param.kind != inspect.Parameter.VAR_KEYWORD):
			raise ValueError('request parameter must be the last named parameter in function: %s%s' % (fn.__name__, str(sig)))
	return found

# 当有资源申请请求时的处理器
class RequestHandler(object):

	def __init__(self, app, fn):
		self._app = app
		self._func = fn
		self._has_request_arg = has_request_arg(fn)
		self._has_var_kw_arg = has_var_kw_arg(fn)
		self._has_named_kw_args = has_named_kw_args(fn)
		self._named_kw_args = get_named_kw_args(fn)
		self._required_kw_args = get_required_kw_args(fn)

	# 未完成
	async def __call__(self, request):
		kw = None
		if self._has_var_kw_arg or self._has_named_kw_args or self._required_kw_args:
			# 如果请求为 post 类型 即带有参数的请求
			if request.method == 'POST':
				# 请求的文本类型
				if not request.content_type:
					return web.HTTPBadRequest('Missing Content-Type.')
				ct = request.content_type.lower()
				# 若请求的文本类型为 json
				if ct.startswith('application/json'):
					params = await request.json()
					# 若新建请求类型出错
					if not isinstance(params, dict):
						return web.HTTPBadRequest('JSON body must be object.')
					kw = params
				# 如果请求表的类型为 数据表
				elif ct.startswith('application/x-www-form-urlencoded') or ct.startswith('multipart/form-data'):
					params = await request.post()
					kw = dict(**params)
				else:
					# 如果都不是则报错
					return web.HTTPBadRequest('Unsupported Content-Type: %s' % request.content_type)
			# 如果知识页面请求
			if request.method == 'GET':
				qs = request.query_string
				if qs:
					kw = dict()
					for k, v in parse.parse_qs(qs, True).items():
						kw[k] = v[0]
		if kw is None:
			kw = dict(**request.match_info)
		else:
			if not self._has_var_kw_arg and self._named_kw_args:
				#remove all unamed kw
				copy = dict()
				for name in self._named_kw_args:
					if name in kw:
						copy[name] = kw[name]
				kw = copy
			# check named arg:
			for k, v in request.match_info.items():
				if k in kw:
					logging.warning('Duplicate arg name in named arg and kw args: %s' % k)
				kw[k] = v
		if self._has_request_arg:
			kw['request'] = request
		# check required kw:
		if self._required_kw_args:
			for name in self._required_kw_args:
				if not name in kw:
					return web.HTTPBadRequest('Missing argument:%s' % name)
		logging.info('call with args: %s' % str(kw))
		try:
			r = await self._func(**kw)
			return r
		except APIError as e:
			return dict(error=e.error, data=e.data, message=e.message)

def add_static(app):
	path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static')
	app.router.add_static('/static/', path)
	logging.info('add static %s => %s' % ('/static/', path))

def add_route(app, fn):
	method = getattr(fn, '__method__', None)
	path = getattr(fn, '__route__', None)
	if path is None or method is None:
		raise ValueError('@get or @post not defined in %s.' % str(fn))
	if not asyncio.iscoroutinefunction(fn) and not inspect.isgeneratorfunction(fn):
		fn = asyncio.coroutine(fn)
	logging.info('add route %s %s => %s(%s)' % (method, path, fn.__name__, ', '.join(inspect.signature(fn).parameters.keys())))
	app.router.add_route(method, path, RequestHandler(app, fn))

def add_routes(app, module_name):
	n = module_name.rfind('.')
	if n == (-1):
		mod = __import__(module_name, globals(), locals())
	else:
		name = module_name[n+1:]
		mod = getattr(__import__(module_name[:n], globals(), locals(), [name]), name)
	for attr in dir(mod):
		if attr.startswith('_'):
			continue
		fn = getattr(mod, attr)
		if callable(fn):
			method = getattr(fn, '__method__', None)
			path = getattr(fn, '__route__', None)
			if method and path:
				add_route(app, fn)