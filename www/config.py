#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# 读取配置文件

__author__ = 'luisfly'

import config_default

# 新建 Dict 类 继承与 dict
# 并进行相应的扩展
class Dict(dict):
    '''
    Simple dict but support access as x.y style.
    '''
    def __init__(self, names=(), values=(), **kw):
        super(Dict, self).__init__(**kw)
        for k, v in zip(names, values):
            self[k] = v

    # 增添了 实例.属性名  的值获取方法
    def __getattr__(self, key):
        try:
            return self[key]
        except KeyError:
            raise AttributeError(r"'Dict' object has no attribute '%s'" % key)

    # 增添了 实例.属性名 = value 的值设置方法
    def __setattr__(self, key, value):
        self[key] = value

def merge(defaults, override):
    r = {}
    # 同时获取键与值
    for k, v in defaults.items():
        if k in override:
            if isinstance(v, dict):
                r[k] = merge(v, override[k])
            else:
                r[k] = override[k]
        else:
            r[k] = v
    return r

# 转化为 Dict 对象
def toDict(d):
    D = Dict()
    for k, v in d.items():
        D[k] = toDict(v) if isinstance(v, dict) else v
    return D

configs = config_default.configs

try:
    import config_override
    configs = merge(configs, config_override.configs)
except ImportError:
    pass

configs = toDict(configs)
print(configs)