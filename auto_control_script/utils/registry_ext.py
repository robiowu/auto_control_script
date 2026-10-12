# -*- coding: utf-8 -*-
"""
registry_ext.py - Windows 注册表操作模块

职责:
- 提供注册表键值的读写、枚举、存在性检查
- 支持导入 .reg 文件

调用链:
- 外部脚本 -> registry_ext.py -> winreg
"""
import os
import winreg as _winreg


def OpenFullPathReg(regPath: str, sam: int = _winreg.KEY_READ):
    """
    根据完整注册表路径打开注册表键，返回键句柄。

    Args:
        regPath (str): 完整路径注册表键名，例如 HKEY_LOCAL_MACHINE\\SOFTWARE\\Tencent\\QQPCMgr
        sam (int): 访问权限，例如 _winreg.KEY_ALL_ACCESS

    Returns:
        注册表键句柄，失败返回 None
    """
    rootKeys = ["HKEY_CLASSES_ROOT", "HKEY_CURRENT_USER", "HKEY_LOCAL_MACHINE", "HKEY_USERS", "HKEY_CURRENT_CONFIG"]
    pos = -1
    for rootKey in rootKeys:
        pos = regPath.find(rootKey)
        if pos != -1:
            break

    if pos != -1:
        if rootKey == "HKEY_CLASSES_ROOT":
            regRoot = _winreg.HKEY_CLASSES_ROOT
        elif rootKey == "HKEY_CURRENT_USER":
            regRoot = _winreg.HKEY_CURRENT_USER
        elif rootKey == "HKEY_LOCAL_MACHINE":
            regRoot = _winreg.HKEY_LOCAL_MACHINE
        elif rootKey == "HKEY_USERS":
            regRoot = _winreg.HKEY_USERS
        elif rootKey == "HKEY_CURRENT_CONFIG":
            regRoot = _winreg.HKEY_CURRENT_CONFIG
        else:
            print("Wrong reg path: ", regPath)
            return None
    else:
        print("Wrong reg path: ", regPath)
        return None

    subKey = regPath[pos + len(rootKey) + 1:]
    try:
        key = _winreg.OpenKey(regRoot, subKey, 0, sam)
    except:
        print("Fail to open: ", regPath)
        return None
    return key


def GetValues(regPath: str) -> list:
    """
    获取一个注册表键下的所有键值。

    Args:
        regPath (str): 完整路径注册表键名

    Returns:
        list: 由注册表键值组成的列表，每一项为 (name, value, type)
    """
    values = []
    key = OpenFullPathReg(regPath)
    if key is None:
        return values
    try:
        i = 0
        while True:
            name, value, type_val = _winreg.EnumValue(key, i)
            values.append((name, value, type_val))
            i = i + 1
    except WindowsError:
        return values


def GetSubKeys(regPath: str) -> list:
    """
    获取一个注册表键下的所有子键名。

    Args:
        regPath (str): 完整路径注册表键名

    Returns:
        list: 由子键名组成的字符串列表
    """
    subKeys = []
    key = OpenFullPathReg(regPath)
    if key is None:
        return subKeys
    try:
        i = 0
        while True:
            name = _winreg.EnumKey(key, i)
            subKeys.append(name)
            i = i + 1
    except WindowsError:
        return subKeys


def IsKeyExist(regPath: str) -> bool:
    """
    判断注册表键是否存在。

    Args:
        regPath (str): 完整路径注册表键名

    Returns:
        bool: 存在返回 True，否则返回 False
    """
    key = OpenFullPathReg(regPath)
    if key is None:
        return False
    else:
        _winreg.CloseKey(key)
        return True


def IsValueExist(regPath: str, valueName: str) -> bool:
    """
    判断注册表键下某个值是否存在。

    Args:
        regPath (str): 完整路径注册表键名
        valueName (str): 注册表值名称

    Returns:
        bool: 存在返回 True，否则返回 False
    """
    values = GetValues(regPath)
    for value in values:
        if value[0] == valueName:
            return True
    return False


def GetRegValue(regPath: str, valueName: str):
    """
    读取注册表中指定值的数值。

    Args:
        regPath (str): 完整路径注册表键名，例如 HKEY_LOCAL_MACHINE\\SOFTWARE\\Tencent\\QQPCMgr
        valueName (str): 注册表值名称，例如 "Version"

    Returns:
        值对应的数据，失败或异常时返回 None
    """
    value = None
    hkey = OpenFullPathReg(regPath)
    if hkey is None:
        return None
    try:
        value = _winreg.QueryValueEx(hkey, valueName)[0]
        return value
    except Exception as e:
        print(e, regPath, valueName)
        return None


def ImportRegistry(regfilePath: str) -> bool:
    """
    静默导入一个 .reg 注册表文件。

    Args:
        regfilePath (str): 要导入的注册表文件的完整路径

    Returns:
        bool: 成功返回 True，否则返回 False
    """
    if os.path.isfile(regfilePath):
        cmd = f"regedit /s {regfilePath} >nul"
        if os.system(cmd) == 0:
            print("import registry file succeed")
            return True
        else:
            print("Fail to import registry file")
            return False
    else:
        print(f"{regfilePath} is not a file")
        return False


def SetValue(regPath: str, value_name: str, value: int) -> None:
    """
    设置注册表键下某个 DWORD 类型的值。

    Args:
        regPath (str): 完整路径注册表键名
        value_name (str): 要设置的注册表值名称
        value (int): 要设置的值
    """
    hkey = OpenFullPathReg(regPath, sam=_winreg.KEY_ALL_ACCESS)
    if hkey is None:
        return None
    try:
        _winreg.SetValueEx(hkey, value_name, 0, _winreg.REG_DWORD, value)
    except Exception as e:
        print(e, regPath, value_name)
        return None


if __name__ == '__main__':
    pass
