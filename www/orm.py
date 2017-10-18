#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# 本版本的orm缺少update remove find方法, 未完成
'This is a homework---day3'

__author__ = 'luisfly'

import logging; logging.basicConfig(level=logging.INFO)
import asyncio,aiomysql
from aiohttp import web

def log(sql, args=()):
	logging.info('SQL: %s' % sql)

# 数据库连接池创建
async def create_pool(loop, **kw):
	logging.info('create database connection pool...')
	global __pool
	# 连接池创建行数 aiomysql.create_pool
	# 导入数据库连接的参数
	__pool = await aiomysql.create_pool(
		host=kw.get('host', 'localhost'),
		port=kw.get('port', 3306),
		user=kw['user'],
		password=kw['password'],
		db=kw['database'],
		charset=kw.get('charset','utf8'),
		autocommit=kw.get('autocommit', True),
		maxsize=kw.get('maxsize', 10),
		minsize=kw.get('minsize' ,1),
		loop=loop
	)

# select 语句的配置工作
async def select(sql, args, size=None):
	log(sql, args)
	global __pool
	# 建立线程池 访问
	with (await __pool) as conn:
		cur = await conn.cursor(aiomysql.DictCursor)
		# 带参数的 sql语句，并非是 sql语句拼接
		# 防止注入式攻击
		await cur.execute(sql.replace('?', '%s'), args or ())
		if size:
			# 接受参数 即显示查询结果
			rs = await cur.fetchmany(size)
		else:
			# 查询所有
			rs = await cur.fetchall()
		await cur.close()
		logging.info('rows returned: %s' % len(rs))
		return rs

# insert,update,delete语句配置工作
async def execute(sql, args):
	log(sql)
	# 建立线程池
	with (await __pool) as conn:
		try:
			# cur 为 conn 获取连接后返回的操作对象
			# conn.cursor() 获取处理对象
			cur = await conn.cursor()
			# cur
			await cur.execute(sql.replace('?', '%s'), args)
			# 通过 rowcount返回结果
			affected = cur.rowcount
			await cur.close()
		except BaseException as e:
			raise
		return affected

# 创建 指定的字符串
def create_args_string(num):
	L = []
	for n in range(num):
		L.append('?')
	return ', '.join(L)

# User 对象与数据库表users相关联
# class User(Model):
# 	__table__ = 'users'

	# id与name 为类属性，并非是实例属性
	# 实例必须要利用__init__()进行初始化
# 	id = IntegerField(primary_key=True)
#	name = StringField()

# Model通过 metaclass 将User的映射信息读取 
# ModelMetaclass 为元类
# 是创建 Model 的基础		
class ModelMetaclass(type):

	def __new__(cls, name, bases, attrs):
		# 排除 Model类本身，只能读取其他子类的信息
		if name=='Model':
			return type.__new__(cls, name, bases,attrs)
		# 获取table名称
		tableName = attrs.get('__table__',None) or name
		logging.info('found model: %s (table: %s)' % (name, tableName))
		# 获取所有Field和主键名
		mappings = dict()
		fields = []
		primaryKey = None
		# attrs 应该是一个 dict
		# 可以通过迭代器获取所有对象
		for k, v in attrs.items():
			if isinstance(v, Field):
				logging.info('	found mapping: %s ==> %s' % (k, v))
				mappings[k] = v
				# v.priamry_key 判断当前属性是否是主键
				if v.primary_key:
					# 如果主键在之前就已经有一个被找到了
					# 系统报错
					# 因为主键只能有一个
					if primaryKey:
						raise RuntimeError('Duplicate primary key for filed: %s' % k)
					# 第一次找到主键
					# 将 primarykey 的值设置为 主键所谓位于的参数位置
					primaryKey = k
				else:
					fields.append(k)
		# 找不到主键
		# 报错
		if not primaryKey:
			raise RuntimeError('Primary key not found.')
		for k in mappings.keys():
			attrs.pop(k)
		# 注意：反引号不要打错
		escaped_fields = list(map(lambda f: '`%s`' % f, fields))
		# attrs是元类导入的方法、类属性集合，往里面添加元素
		attrs['__mappings__'] = mappings # 保存属性和列表的映射关系
		attrs['__table__'] = tableName	# 保存表名称
		attrs['__primary_key__'] = primaryKey # 主键属性名
		attrs['__fields__'] = fields # 除主键外的属性名
        # 构造默认的SELECT, INSERT, UPDATE和DELETE语句:
		attrs['__select__'] = 'select `%s`, %s from `%s`' % (primaryKey, ', '.join(escaped_fields), tableName)
		attrs['__insert__'] = 'insert into `%s` (%s, `%s`) values (%s)' % (tableName, ', '.join(escaped_fields), primaryKey, create_args_string(len(escaped_fields) + 1))
		attrs['__update__'] = 'update `%s` set %s where `%s`=?' % (tableName, ', '.join(map(lambda f: '`%s`=?' % (mappings.get(f).name or f), fields)), primaryKey)
		attrs['__delete__'] = 'delete from `%s` where `%s`=?' % (tableName, primaryKey)
        # count 语句
		attrs['__count__'] = 'select count(*) from `%s`' % (tableName, )
		return type.__new__(cls, name, bases, attrs)


# ORM Model 基类
# 所有表的对应的对象基类
# 使用 ModelMetalclass 的元类 继承 dict 类
# 元类使用时类似下列 在参数中添加 metalclass 参数
class Model(dict, metaclass=ModelMetaclass):

	def __init__(self, **kw):
		super(Model, self).__init__(**kw)

	# 获取属性时 可使用 类名.属性
	# 当属型不存在的时候
	# 返回错误信息
	def __getattr__(self, key):
		try:
			return self[key]
		except KeyError:
			raise AttributeError(r"'Model' object has no attribute '%s'" % key)

	# 和 getattr 相类似
	def __setattr__(self, key, value):
		self[key] = value

	def getValue(self, key):
		return getattr(self, key, None)

	# 获取默认值
	def getValueOrDefault(self, key):
		value = getattr(self, key, None)
		if value is None:
			field = self.__mappings__[key]
			# 如果属性 field 的拥有默认值
			# 获取默认值，并赋予 field
			if field.default is not None:
				value = field.default() if callable(field.default) else field.default
				logging.debug('using default value for %s: %s' % (key, str(value)))
				setattr(self, key, value)
		return value

	# 实现查找
	# 通过主键进行查找
	@classmethod
	async def find(cls, pk):
		' find object by primary key.'
		# 语句拼凑
		rs = await select('%s where `%s`=?' % (cls.__select__, cls.__primary_key__), [pk], 1)
		# 如果返回结果数量为 0
		# 则返回 None
		if len(rs) == 0:
			return None
		return cls(**rs[0])

	# 根据条件返回多个查找结果
	# find()方法是根据主键查找，因而只返回一个查找结果
	# __mapping__ 存储着表的属性列表
#	@classmethod
#	async def findAll(cls, key, value):
#		rs = await select('`%s` where `%s`=?' % (cls.__select__, cls.__mapping__[key]), value)
#		if len(rs) == 0:
#			return None
#		return cls(**rs)
	# 查找多个结果
	@classmethod
	async def findAll(cls, where=None, args=None, **kw):
		'find objects by where clause.'
		sql = [cls.__select__]
		# 如果带有 where 参数
		# 自动延伸 sql 语句
		if where:
			sql.append('where')
			sql.append(where)
		# 如果不带有其他参数
		# args 设为 空 dict []
		if args is None:
			args = []
		# 获取参数 看是否有 orderBy 属性
		orderBy = kw.get('orderBy', None)
		if orderBy:
			sql.append('order by')
			sql.append(orderBy)
		# 查看是否有 limit 属性
		# 具体操作如上面 where
		limit = kw.get('limit', None)
		if limit is not None:
			sql.append('limit')
			if isinstance(limit, int):
				sql.append('?')
				args.append(limit)
			elif isinstance(limit, tuple) and len(limit) == 2:
				sql.append('?, ?')
				args.extend(limit)
			else:
				raise ValueError('Invalid limit value: %s' % str(limit))
		rs = await select(' '.join(sql), args)
		return [cls(**r) for r in rs]

	# 寻找数量
	@classmethod
	async def findNumber(cls, selectField, where=None, args=None):
		' find number by select an where'
		sql = ['select %s _num_ from `%s`' % (selectField, cls.__table__)]
		if where:
			sql.append('where')
			sql.append(where)
		#rs = await select('%s where `%s`=?' % (cls.__count__, cls.__mapping__[key]), value)
		rs = await select(''.join(sql), args, 1)
		if len(rs) == 0:
			return None
		return rs[0]['_num_']

	# 实现事务提交
	async def save(self):
		args = list(map(self.getValueOrDefault, self.__fields__))
		args.append(self.getValueOrDefault(self.__primary_key__))
		rows = await execute(self.__insert__, args)
		if rows != 1:
			logging.warn('failed to insert record: affected rows: %s' % rows)


	# 更新
	async def update(self):
		args = list(map(self.getValue, self.__fields__))
		args.append(self.getValue(self.__primary_key__))
		rows = await execute(self.__update__, args)
		if rows != 1:
			logging.warn('failed to update by primary key: affected rows: %s' % rows)

	# 根据主键来进行删除
	# 若返回的结果不为1即为出现错误
	async def remove(self):
		args = [self.getValue(self.__primary_key__)]
		rows = await exectue(self.__delete__, args)
		if rows != 1:
			logging.warn('failed to remove by primary key: affected rows: %s' % rows)

# 属性Field的子类
class Field(object):

	# 初始化 第一个参数是数据名称
	# 第二个参数是数据类型
	# 第三个参数是是否为主键
	# 第四个参数是是否有默认值
	def __init__(self, name, column_type, primary_key, default):
		self.name = name
		self.column_type = column_type
		self.primary_key = primary_key
		self.default = default

	def __str__(self):
		return '<%s, %s:%s>' % (self.__class__.__name__, self.column_type, self.name)

# 映射varchar 的 StringField,继承Field
class StringField(Field):
	
	# ddl是String的数据类型
	def __init__(self, name=None, primary_key=False, default=None, ddl='varchar(100)'):
		super().__init__(name, ddl, primary_key, default)

# 映射int 的 IntegerField,继承Field
class IntegerField(Field):

	def __init__(self, name=None, primary_key=False, default=0):
		super().__init__(name, 'bigint', primary_key, default)

# 映射 boolean 的 BooleanField
class BooleanField(Field):

	def __init__(self, name=None, primary_key=False, default=False):
		super().__init__(name, 'boolean', primary_key, default)

# 映射 Float 的 FloatField
class FloatField(Field):

	def __init__(self, name=None, primary_key=False, default=0.0):
		super().__init__(name, 'real', primary_key, default)		

# 映射 Text 的 TextField
class TextField(Field):

	def __init__(self, name=None, primary_key=False, default=None):
		super().__init__(name, 'text', primary_key, default)

# User 对象与数据库表users相关联
# class User(Model):
#	__table__ = 'users'

	# id与name 为类属性，并非是实例属性
	# 实例必须要利用__init__()进行初始化
#	id = IntegerField(primary_key=True)
#	name = StringField()

# user = User(id=123, name='Michael')