"""WPS 静默转 PDF 的内部 worker。

该脚本由 PyWpsRpcBackend 以独立进程方式调用，保证 WPS/Qt 的生命周期
与 Tk 主程序隔离，并且全程不显示 WPS 窗口：

    python3 wps_worker.py <input> <output.pdf>

退出码：0 成功，1 转换失败，2 参数错误。
"""

import os
import sys
import traceback

WRITER_EXTS = {'.docx', '.doc', '.odt', '.rtf', '.txt'}
CALC_EXTS = {'.xlsx', '.xls', '.ods'}
IMPRESS_EXTS = {'.pptx', '.ppt', '.odp'}

_qapp = None


def _silence_writer(app, wpsapi):
    for attr, value in (
            ('Visible', False),
            ('DisplayAlerts', int(wpsapi.WdAlertLevel.wdAlertsNone)),
    ):
        try:
            setattr(app, attr, value)
        except Exception:
            pass


def _silence_calc(app):
    for attr, value in (('Visible', False), ('DisplayAlerts', False)):
        try:
            setattr(app, attr, value)
        except Exception:
            pass


def _silence_impress(app, wppapi):
    for attr, value in (
            ('Visible', int(wppapi.MsoTriState.msoFalse)),
            ('DisplayAlerts', int(wppapi.PpAlertLevel.ppAlertsNone)),
    ):
        try:
            setattr(app, attr, value)
        except Exception:
            pass


def _check(hr, action):
    if hr != 0:
        raise RuntimeError('{} 失败，HRESULT={}'.format(action, hex(hr & 0xFFFFFFFF)))


def _save_process_pid(rpc, pidfile):
    if not pidfile:
        return
    try:
        hr, pid = rpc.getProcessPid()
        if hr == 0 and pid:
            with open(pidfile, 'w') as f:
                f.write(str(pid))
    except Exception:
        pass


def _convert_writer(src, dst, pidfile):
    from pywpsrpc.rpcwpsapi import createWpsRpcInstance, wpsapi

    hr, rpc = createWpsRpcInstance()
    _check(hr, 'createWpsRpcInstance')
    hr, app = rpc.getWpsApplication()
    _check(hr, 'getWpsApplication')
    _save_process_pid(rpc, pidfile)

    doc = None
    try:
        _silence_writer(app, wpsapi)
        hr, doc = app.Documents.Open(
            src,
            ConfirmConversions=False,
            ReadOnly=True,
            AddToRecentFiles=False,
            Visible=False,
        )
        _check(hr, 'Documents.Open')
        hr = doc.SaveAs(
            dst,
            FileFormat=int(wpsapi.WdExportFormat.wdExportFormatPDF),
        )
        _check(hr, 'Document.SaveAs(PDF)')
    finally:
        if doc is not None:
            try:
                doc.Close(
                    SaveChanges=int(wpsapi.WdSaveOptions.wdDoNotSaveChanges))
            except Exception:
                pass
        try:
            app.Quit()
        except Exception:
            pass


def _convert_calc(src, dst, pidfile):
    from pywpsrpc.rpcetapi import createEtRpcInstance, etapi

    hr, rpc = createEtRpcInstance()
    _check(hr, 'createEtRpcInstance')
    hr, app = rpc.getEtApplication()
    _check(hr, 'getEtApplication')
    _save_process_pid(rpc, pidfile)

    book = None
    try:
        _silence_calc(app)
        hr, book = app.Workbooks.Open(
            src,
            ReadOnly=True,
            AddToMru=False,
        )
        _check(hr, 'Workbooks.Open')
        hr = book.ExportAsFixedFormat(
            etapi.XlFixedFormatType.xlTypePDF, dst)
        _check(hr, 'Workbook.ExportAsFixedFormat(PDF)')
    finally:
        if book is not None:
            try:
                book.Close()
            except Exception:
                pass
        try:
            app.Quit()
        except Exception:
            pass


def _convert_impress(src, dst, pidfile):
    from pywpsrpc.rpcwppapi import createWppRpcInstance, wppapi

    hr, rpc = createWppRpcInstance()
    _check(hr, 'createWppRpcInstance')
    hr, app = rpc.getWppApplication()
    _check(hr, 'getWppApplication')
    _save_process_pid(rpc, pidfile)

    pres = None
    try:
        _silence_impress(app, wppapi)
        hr, pres = app.Presentations.Open(
            src,
            ReadOnly=int(wppapi.MsoTriState.msoTrue),
            WithWindow=int(wppapi.MsoTriState.msoFalse),
        )
        _check(hr, 'Presentations.Open')
        hr = pres.ExportAsFixedFormat(
            dst, wppapi.PpFixedFormatType.ppFixedFormatTypePDF)
        _check(hr, 'Presentation.ExportAsFixedFormat(PDF)')
    finally:
        if pres is not None:
            try:
                pres.Close()
            except Exception:
                pass
        try:
            app.Quit()
        except Exception:
            pass


def main(argv=None):
    global _qapp

    argv = list(sys.argv if argv is None else argv)
    if len(argv) not in (3, 4):
        sys.stderr.write(
            'usage: wps_worker.py <input> <output.pdf> [pidfile]\n')
        return 2

    src = os.path.abspath(argv[1])
    dst = os.path.abspath(argv[2])
    pidfile = os.path.abspath(argv[3]) if len(argv) == 4 else None
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    if os.path.exists(dst):
        os.remove(dst)

    ext = os.path.splitext(src)[1].lower()
    try:
        if ext not in WRITER_EXTS | CALC_EXTS | IMPRESS_EXTS:
            raise RuntimeError('WPS 后端不支持的文件类型: {}'.format(ext))

        from pywpsrpc.common import QtApp
        _qapp = QtApp([argv[0]])

        if ext in WRITER_EXTS:
            _convert_writer(src, dst, pidfile)
        elif ext in CALC_EXTS:
            _convert_calc(src, dst, pidfile)
        else:
            _convert_impress(src, dst, pidfile)

        if not os.path.exists(dst) or os.path.getsize(dst) == 0:
            raise RuntimeError('WPS 未生成 PDF 文件: {}'.format(dst))
    except Exception as exc:
        traceback.print_exc()
        sys.stderr.write('WPS 转换失败: {}\n'.format(exc))
        return 1

    return 0


if __name__ == '__main__':
    sys.exit(main())
