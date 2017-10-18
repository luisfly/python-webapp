#!/usr/bin/env python3
# -*- coding: utf-8 -*-

__author__ = 'lusifly'

import re, time, json, logging, hashlib, base64, asyncio

import markdown2

from aiohttp import web

from coroweb import get, post
from apis import Page, APIValueError, APIResourceNotFoundError, APIError, APIPermissionError

from config import configs
from models import User, Comment, Blog, next_id

_RE_EMAIL = re.compile(r'^[a-z0-9\.\-\_]+\@[a-z0-9\-\_]+(\.[a-z0-9\-\_]+){1,4}$')
_RE_SHA1 = re.compile(r'^[0-9a-f]{40}$')
# cookie 设置
COOKIE_NAME = 'awesession'
_COOKIE_KEY = configs.session.secret

def check_admin(request):
	if request.__user__ is None or not request.__user__.admin:
		raise APIPermissionError()

def get_page_index(page_str):
	p = 1
	try:
		p = int(page_str)
	except ValueError as e:
		pass
	if p < 1:
		p = 1
	return p

# 不要打错名字
# 计算加密 cookie
def user2cookie(user, max_age):
	# Generate cookie str by user.
	# build cookie string by: id-expires-sha1
	expires = str(int(time.time() + max_age))
	s = '%s-%s-%s-%s' % (user.id, user.passwd, expires, _COOKIE_KEY)
	L = [user.id, expires, hashlib.sha1(s.encode('utf-8')).hexdigest()]
	return '-'.join(L)

def text2html(text):
	lines = map(lambda s: '<p>%s<p>' % s.replace('&', '&amp;').replace('<', '&gt;'), filter(lambda s: s.strip() !='', text.split('\n')))
	return ''.join(lines)

# 解密 cookie 登录重要的的步骤
async def cookie2user(cookie_str):
	# parse cookie and load user if cookie is vaild
	if not cookie_str:
		return None
	try:
		L = cookie_str.split('-')
		if len(L) != 3:
			return None
		uid , expires, sha1 = L
		if int(expires) < time.time():
			return None
		user = await User.find(uid)
		if user is None:
			return None
		s = '%s-%s-%s-%s' % (uid, user.passwd, expires, _COOKIE_KEY)
		if sha1 != hashlib.sha1(s.encode('utf-8')).hexdigest():
			logging.info('invalid sha1')
			return None
		user.passwd = '*******'
		return user
	except Exception as e:
		logging.exception(e)
		return None

# 页面注册
# 将页面处理函数与页面路径相联系起来
# 固定了首页的页面
# @get('/')
# async def index(request):
#	summary = 'Lorem ipsum dolor sit amet, consectetur adipisicing elit, sed do eiusmod tempor incididunt ut labore et dolore magna aliqua.'
#	blogs = [
#		Blog(id='1', name='Test Blog', summary=summary, created_at=time.time()-3600),
#		Blog(id='2', name='Something New', summary=summary, created_at=time.time()-3600),
#		Blog(id='3', name='Learn Swift', summary=summary, created_at=time.time()-7200)
#		]
#	return {
#		'__template__': 'blogs.html',
#		'blogs': blogs
#	}

# 重新写首页的 注册方式
@get('/')
async def index(*, page='1'):
	page_index = get_page_index(page)
	num = await Blog.findNumber('count(id)')
	page = Page(num)
	if num == 0:
		blogs = []
	else:
		blogs = await Blog.findAll(orderBy='created_at desc', limit=(page.offset, page.limit))
	return {
		'__template__': 'blogs.html',
		'page': page,
		'blogs': blogs
	}

# 将数据库的数据以 json 的形式返回
# 并注册到网站上，通过访问 localhost/api/users地址
# 即可获得数据库对象的详细信息
#@get('/api/users')
#async def api_get_users(*, page='1'):
#	page_index = get_page_index(page)
#	num await User.findNumber('count(id)')
#	p = Page(numm page_index)
#	if num == 0:
#		return dict(page=p, users=())
#	users = await User.findAll(orderBy='created_at desc')
#	for u in users:
#		u.passwd = "******"
#	return dict(users=users)

# 页面注册
@get('/blog/{id}')
async def get_blog(id):
	blog = await Blog.find(id)
	print('id=%s' % id)
	comments = await Comment.findAll('blog_id=?', [id], orderBy='created_at desc')
	for c in comments:
		c.html_content =text2html(c.content)
	blog.html_content = markdown2.markdown(blog.content)
	return {
		'__template__': 'blog.html',
		'blog': blog,
		'comments': comments
	}

# 页面注册
@get('/register')
def register():
	return {
		'__template__': 'register.html'
	}

@get('/signin')
def signin():
	return {
		'__template__': 'signin.html'
	}

@post('/api/authenticate')
async def authenticate(*, email, passwd):
	if not email:
		raise APIValueError('email', 'Invalid email.')
	if not passwd:
		raise APIValueError('passwd', 'Invalid password')
	users = await User.findAll('email=?', [email])
	if len(users) == 0:
		raise APIValueError('email', 'Email not exist.')
	user = users[0]
	# check passwd:
	sha1 = hashlib.sha1()
	sha1.update(user.id.encode('utf-8'))
	sha1.update(b':')
	sha1.update(passwd.encode('utf-8'))
	if user.passwd != sha1.hexdigest():
		raise APIValueError('passwd', 'Invalid password.')
	# authenticate ok, set cookie:
	r = web.Response()
	r.set_cookie(COOKIE_NAME, user2cookie(user, 86400), max_age=86400, httponly=True)
	user.passwd = '********'
	r.content_type = 'application/json'
	r.body = json.dumps(user, ensure_ascii=False).encode('utf-8')
	return r

# 登出页面
@get('/signout')
async def signout(request):
	referer = request.headers.get('Referer')
	r = web.HTTPFound(referer or '/')
	r.set_cookie(COOKIE_NAME, '-deleted-', max_age=0, httponly=True)
	logging.info('user signed out.')
	return r

# 当输入 127.0.0.1/manage时
# 重定位
@get('/manage/')
def manage():
	return 'redirect:/manage/comments'

# 获取博客讨论区
@get('/manage/comments')
def manage_comments(*, page='1'):
	return {
		'__template__': 'manage_comments.html',
		'page_index': get_page_index(page)
	}

@get('/manage/blogs')
def manage_blogs(*, page='1'):
	return {
		'__template__': 'manage_blogs.html',
		'page_index': get_page_index(page)
	}

@get('/manage/blogs/create')
def manage_create_blog():
	return {
		'__template__': 'manage_blog_edit.html',
		'id': '',
		'action': '/api/blogs'
	}

# blog 编辑页面
@get('/manage/blogs/edit')
def manage_edit_blog(*, id):
	return {
		'__template__': 'manage_blog_edit.html',
		'id': id,
		'action': '/api/blogs/%s' % id
	}

# 用户管理页面
@get('/manage/users')
def manage_users(*, page='1'):
	return {
		'__template__': 'manage_users.html',
		'page_index': get_page_index(page)
	}

# 配置论坛部分的 api 页面 
@get('/api/comments')
async def api_comments(*, page='1'):
	page_index = get_page_index(page)
	# 通过 Comment.findNumber 去寻找对应的论坛评论
	num = await Comment.findNumber('count(id)')
	p = Page(num, page_index)
	if num == 0:
		return dict(page=p, comments=())
	comments = await Comment.findAll(orderBy='created_at desc', limit=(p.offset, p.limit))
	return dict(page=p, comments=comments)

# 根据 id 获取论坛 api
@post('/api/blogs/{id}/comments')
async def api_create_comment(id, request, *, content):
	user = request.__user__
	if user is None:
		raise APIPermissionError('Please signin first.')
	if not content or not content.strip():
		raise APIValueError('content')
	blog = await Blog.find(id)
	if blog is None:
		raise APIResourceNotFoundError('Blog')
	comment = Comment(blog_id=blog.id, user_id=user.id, user_name=user.name, user_image=user.image, content=content.strip())
	await comment.save()
	return comment

# 页面请求的方式不一样，获得的页面也有所不同
# 与下面的做比较
# 同样是注册在 '/api/users' 路径下的两个处理函数
@get('/api/users')
async def api_get_users(*, page='1'):
	page_index = get_page_index(page)
	num = await User.findNumber('count(id)')
	p = Page(num, page_index)
	if num == 0:
		return dict(page=p, users=())
	users = await User.findAll(orderBy='created_at desc', limit=(p.offset, p.limit))
	for u in users:
		u.passwd = '*******'
	return dict(page=p, users=users)

# 用户注册页面的设置
# 尝试不添加 async 关键字
@post('/api/users')
async def api_register_user(*, email, name, passwd):
	if not name or not name.strip():
		raise APIValueError('name')
	if not email or not _RE_EMAIL.match(email):
		raise APIValueError('email')
	if not passwd or not _RE_SHA1.match(passwd):
		raise APIValueError('passwd')
	users = await User.findAll('email=?',[email])
	if len(users) > 0:
		raise APIError('register:failed', 'email', 'Email is already in use.')
	uid = next_id()
	sha1_passwd = '%s:%s' % (uid, passwd)
	# 保存生成的 id 的是 uid
	user = User(id=uid, name=name.strip(), email=email, passwd=hashlib.sha1(sha1_passwd.encode('utf-8')).hexdigest(), image='http://www.gravatar.com/avatar/%s?d=mm&s=120' % hashlib.md5(email.encode('utf-8')).hexdigest())
	await user.save()
	# make session cookie:
	r = web.Response()
	# 查一下 set_cookie 相关知识
	r.set_cookie(COOKIE_NAME, user2cookie(user, 86400), max_age=86400, httponly=True)
	user.passwd = '*******'
	r.content_type = 'application/json'
	r.body = json.dumps(user, ensure_ascii=False).encode('utf-8')
	return r

# 实现 blog manage 的 api 
# 快速查询
@get('/api/blogs')
async def api_blogs(*, page='1'):
	page_index = get_page_index(page)
	num = await Blog.findNumber('count(id)')
	p = Page(num, page_index)
	if num == 0:
		return dict(page=p, blogs=())
	blogs = await Blog.findAll(orderBy='created_at desc', limit=(p.offset, p.limit))
	return dict(page=p, blogs=blogs)

# 模板 manage_blog.html
# 通过 api获得 Model
@get('/api/blogs/{id}')
async def api_get_blog(*, id):
	blog = await Blog.find(id)
	return blog

# 小修改看能否有效
@post('/api/blogs')
# 添加了 async 关键字
async def api_create_blog(request, *, name, summary, content):
	check_admin(request)
	if not name or not name.strip():
		raise APIValueError('name', 'name cannot be empty.')
	if not summary or not summary.strip():
		raise APIValueError('summary', 'summary cannot be empty.')
	if not content or not content.strip():
		raise APIValueError('content', 'content cannot be empty.')
	blog = Blog(user_id=request.__user__.id, user_name=request.__user__.name, user_image=request.__user__.image, name=name.strip(), summary=summary.strip(), content=content.strip())
	# 将 yield from 改为 await
	await blog.save()
	return blog

# 页面 blog api 获取
@post('/api/blogs/{id}')
async def api_update_blog(id, request, *, name, summary, content):
	check_admin(request)
	blog = await Blog.find(id)
	if not name or not name.strip():
		raise APIValueError('name', 'name cannot be empty.')
	if not summary or not summary.strip():
		raise APIValueError('summary', 'summary cannot be empty.')
	if not content or not content.strip():
		raise APIValueError('content')
	blog.name = name.strip()
	blog.summary = summary.strip()
	blog.content = content.strip()
	await blog.update()
	return blog

# 页面删除 api
@post('/api/blogs/{id}/delete')
async def api_delete_blog(request, *, id):
	check_admin(request)
	blog = await Blog.find(id)
	await blog.remove()
	return dict(id=id)