# -*- coding: utf-8 -*-
"""
system_cmd.py - 系统命令与文件操作工具模块

职责:
- 提供文件复制、移动、删除操作
- 提供同步/异步命令行执行
- 获取系统环境路径（AppData）

调用链:
- game_case.py -> system_cmd.py -> shutil / os / subprocess
"""
import shutil
import os
import subprocess


def copy(source_path: str, dst_path: str) -> None:
    """
    复制文件到目标路径。

    Args:
        source_path (str): 源文件路径
        dst_path (str): 目标文件路径
    """
    shutil.copyfile(source_path, dst_path)


def move(source_path: str, dst_path: str) -> None:
    """
    移动文件到目标路径。

    Args:
        source_path (str): 源文件路径
        dst_path (str): 目标文件路径
    """
    shutil.move(source_path, dst_path)


def cmd_block(cmd_str: str) -> None:
    """
    同步执行命令行指令，阻塞等待完成。

    Args:
        cmd_str (str): 要执行的命令行字符串
    """
    os.popen(cmd_str).read()


def cmd_asyn(cmd_str: str) -> None:
    """
    异步执行命令行指令，不等待返回。

    Args:
        cmd_str (str): 要执行的命令行字符串
    """
    subprocess.Popen(cmd_str, shell=True)


def remove_file(file_path: str) -> None:
    """
    删除指定文件，若文件不存在则打印提示。

    Args:
        file_path (str): 要删除的文件路径
    """
    file_path = os.path.abspath(file_path)
    if os.path.isfile(file_path):
        os.remove(file_path)
    else:
        print(f"——删除的文件不存在{file_path}")


def remove_folder(folder_path: str) -> None:
    """
    删除指定文件夹及其所有内容，若路径非目录则打印提示。

    Args:
        folder_path (str): 要删除的文件夹路径（需为绝对路径）
    """
    if os.path.isdir(folder_path):
        shutil.rmtree(folder_path)
    else:
        print("——删除文件夹请输入正确的文件夹目录（绝对路径）")


def get_abs_appdata_path() -> str:
    """
    获取当前用户的 AppData/Roaming 绝对路径。

    Returns:
        str: %APPDATA% 环境变量对应的绝对路径
    """
    return os.getenv("APPDATA")


if __name__ == '__main__':
    print(get_abs_appdata_path())
