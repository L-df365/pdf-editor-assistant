#!/usr/bin/env python3
"""把已编译好的 pywpsrpc 打成 wheel，随应用一起发布。

背景：上游 pywpsrpc 只提供 x86_64 的 wheel，arm64（如银河麒麟 V10）
只能源码编译 —— 让人自己编译既慢又容易失败。这里把已经编好的那一份
重新打包成 wheel，装应用时 pip 直接装二进制，**不用编译**。

用法：
    python3 tools/build_wheel.py            # 从当前环境里已装的 pywpsrpc 打包
    python3 tools/build_wheel.py --check    # 只看能不能打包
"""

import argparse
import base64
import csv
import hashlib
import io
import os
import platform
import sys
import zipfile

SITE_DIRS = [
    os.path.expanduser('~/.local/lib/python3.8/site-packages'),
    '/usr/lib/python3/dist-packages',
]
WHEEL_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'wheels')


def find_installed():
    """找到已安装的 pywpsrpc（包目录 + dist-info）。"""
    for base in SITE_DIRS:
        pkg = os.path.join(base, 'pywpsrpc')
        if not os.path.isdir(pkg):
            continue
        for name in sorted(os.listdir(base)):
            if name.startswith('pywpsrpc-') and name.endswith('.dist-info'):
                return os.path.join(base, name), pkg
    return None, None


def platform_tag():
    """按当前平台给 wheel 打标签（pip 靠它判断能不能装）。

    用 manylinux2014（glibc ≥ 2.17）：老 pip（如 20.0.2）只认这个标签，
    新 pip 也认。编出来的 .so 只用到 GLIBC_2.17，标签是诚实的。
    """
    machine = platform.machine()
    if machine in ('aarch64', 'arm64'):
        arch = 'aarch64'
    elif machine in ('x86_64', 'amd64'):
        arch = 'x86_64'
    else:
        arch = machine
    python_tag = 'cp{}{}'.format(*sys.version_info[:2])
    return '{}-{}-manylinux2014_{}'.format(python_tag, python_tag, arch)


def record_hash(data):
    digest = hashlib.sha256(data).digest()
    encoded = base64.urlsafe_b64encode(digest).rstrip(b'=').decode()
    return 'sha256=' + encoded, len(data)


def build():
    dist_info, pkg_dir = find_installed()
    if not dist_info:
        print('本机没有装 pywpsrpc，先装好（pip install pywpsrpc）再来打包')
        return 1
    version = os.path.basename(dist_info)[:-len('.dist-info')].split('-', 1)[1]
    tag = platform_tag()
    name = 'pywpsrpc-{}-{}.whl'.format(version, tag)
    os.makedirs(WHEEL_DIR, exist_ok=True)
    target = os.path.join(WHEEL_DIR, name)

    records = []
    with zipfile.ZipFile(target, 'w', zipfile.ZIP_DEFLATED) as zf:
        # 包本体
        for root, _dirs, files in os.walk(pkg_dir):
            if '__pycache__' in root:
                continue
            for filename in files:
                if filename.endswith(('.pyc', '.pyo')):
                    continue
                full = os.path.join(root, filename)
                arc = os.path.relpath(full, os.path.dirname(pkg_dir))
                with open(full, 'rb') as f:
                    data = f.read()
                zf.writestr(arc, data)
                digest, size = record_hash(data)
                records.append((arc, digest, size))
        # dist-info：沿用已装的元数据，只换 WHEEL 的标签
        meta_dir = os.path.basename(dist_info)
        for filename in ('METADATA', 'top_level.txt', 'entry_points.txt',
                         'LICENSE'):
            full = os.path.join(dist_info, filename)
            if not os.path.exists(full):
                continue
            with open(full, 'rb') as f:
                data = f.read()
            arc = '{}/{}'.format(meta_dir, filename)
            zf.writestr(arc, data)
            digest, size = record_hash(data)
            records.append((arc, digest, size))
        wheel_meta = 'Wheel-Version: 1.0\nGenerator: pdf-editor-assistant\nRoot-Is-Purelib: false\nTag: {}\n'.format(tag)
        zf.writestr(meta_dir + '/WHEEL', wheel_meta)
        digest, size = record_hash(wheel_meta.encode())
        records.append((meta_dir + '/WHEEL', digest, size))
        # RECORD 放最后
        buf = io.StringIO()
        writer = csv.writer(buf, lineterminator='\n')
        for row in records:
            writer.writerow(row)
        writer.writerow((meta_dir + '/RECORD', '', ''))
        zf.writestr(meta_dir + '/RECORD', buf.getvalue())

    print('已生成：{}\n  大小 {:.1f} MB'.format(
        target, os.path.getsize(target) / 1024.0 / 1024.0))
    return 0


def main():
    parser = argparse.ArgumentParser(description='打包 pywpsrpc wheel')
    parser.add_argument('--check', action='store_true',
                        help='只检查环境，不打包')
    args = parser.parse_args()

    dist_info, pkg_dir = find_installed()
    if not dist_info:
        print('本机没有装 pywpsrpc')
        return 1
    print('找到：{}'.format(dist_info))
    print('平台标签：{}'.format(platform_tag()))
    if args.check:
        return 0
    return build()


if __name__ == '__main__':
    sys.exit(main())
