import os


def check_dir(*dir):
    if len(dir) > 1:
        check_dir(*dir[:-1])
    path = os.path.join(*dir)
    if not os.path.exists(path):
        os.mkdir(path)
