import os
from UnityPy import Environment


def check_dir(*dir):
    if len(dir) > 1:
        check_dir(*dir[:-1])
    path = os.path.join(*dir)
    if not os.path.exists(path):
        os.mkdir(path)


def filter_env(env: Environment, type: type, read: bool = True):
    return [_.read() if read else _ for _ in env.objects if _.type.name == type.__name__]
