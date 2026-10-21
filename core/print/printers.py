"""打印机能力探测与作业提交（CUPS / IPP）。

用 IPP 属性而不是厂商 PPD 选项：换一台打印机不用改代码。
实测本机 Konica C368 支持：
sides-supported = 单面 / 双面长边 / 双面短边
print-color-mode-supported = color / monochrome
media-supported = 52 种
number-up-supported = 1 2 4 6 9 16
page-ranges-supported = True
"""

import os

#: python3-cups 是系统包（python3-cups），不是 pip 依赖；
#: 没装的时候打印功能要给出明确提示，而不是直接崩。
try:
    import cups
except ImportError:      # pragma: no cover - 取决于系统环境
    cups = None

#: CUPS 的打印机状态（IPP job-state / printer-state）
PRINTER_STATES = {
    3: '就绪',
    4: '正在处理',
    5: '已停止',
    6: '正在取消',
    7: '已暂停',
}

#: 常见的状态原因 → 中文（IPP 的原始串太难懂）
STATE_REASONS = {
    'toner-low-report': '碳粉不足',
    'toner-empty-report': '碳粉用尽',
    'marker-supply-low-report': '硒鼓不足',
    'paper-empty-report': '缺纸',
    'paper-low-report': '纸量偏低',
    'offline-report': '打印机离线',
    'service-requested': '需要维护',
    'none': '',
}

JOB_STATES = {
    3: '处理中',
    4: '已保留',
    5: '已取消',
    6: '已中止',
    7: '已完成',
    8: '已删除',
    9: '处理中',
}


class PrintError(RuntimeError):
    """打印相关的问题（给界面直接显示的）。"""


class PrinterInfo:
    """一台打印机的能力。"""

    def __init__(self, name, attrs):
        self.name = name
        self.state = attrs.get('printer-state', 0)
        self.accepting = bool(attrs.get('printer-is-accepting-jobs', True))
        self.reasons = [str(r) for r in attrs.get('printer-state-reasons', [])
                        if r]
        self.info = str(attrs.get('printer-info', '') or '')
        self.sides = list(attrs.get('sides-supported', []))
        self.color_modes = list(attrs.get('print-color-mode-supported', []))
        self.media = [m[0] if isinstance(m, (list, tuple)) else m
                      for m in attrs.get('media-supported', [])]
        self.media_default = attrs.get('media-default', '')
        self.nup = list(attrs.get('number-up-supported', [1]))
        self.scaling = list(attrs.get('print-scaling-supported', []))
        self.supports_page_ranges = bool(
            attrs.get('page-ranges-supported', False))
        self.queued = attrs.get('queued-job-count', 0)

    @property
    def state_text(self):
        return PRINTER_STATES.get(self.state, '状态未知')

    def reason_text(self):
        """状态原因的中文说明。"""
        parts = []
        for reason in self.reasons:
            if reason in ('none', 'processing'):
                continue
            parts.append(STATE_REASONS.get(reason, reason))
        return '、'.join(parts)

    @property
    def online(self):
        return self.accepting and self.state in (3, 4)

    def supports_duplex(self, mode):
        """mode: one / long / short。"""
        if not mode:
            return True
        wanted = {'one': 'one-sided', 'long': 'two-sided-long-edge',
                  'short': 'two-sided-short-edge'}[mode]
        return wanted in self.sides

    def supports_color(self, mode):
        if not mode:
            return True
        wanted = 'color' if mode == 'color' else 'monochrome'
        return wanted in self.color_modes

    def supports_media(self, media):
        return (not media) or (media in self.media)

    def supports_nup(self, nup):
        return (not nup) or (nup in self.nup)

    def label(self):
        # printer-info 常常是「型号 added by 主机名」，只取型号
        name = self.info or self.name
        for sep in (' added by', ' @ '):
            if sep in name:
                name = name.split(sep)[0]
        return '{}（{}）'.format(name, self.state_text)


# --------------------------------------------------------------------------
# 连接
# --------------------------------------------------------------------------

_connection = None


def _conn():
    """取 CUPS 连接（没装 python3-cups 时给明确提示）。"""
    global _connection
    if cups is None:
        raise PrintError(
            '系统缺少 python3-cups，打印功能不可用。'
            '安装后重试：sudo apt-get install python3-cups')
    if _connection is None:
        _connection = cups.Connection()
    return _connection


def set_connection(conn):
    """替换连接（自测时注入假的连接用）。"""
    global _connection
    _connection = conn


def available():
    return cups is not None


def list_printers():
    """列出所有打印机。"""
    conn = _conn()
    result = []
    for name in conn.getPrinters():
        try:
            attrs = conn.getPrinterAttributes(name)
        except Exception:
            attrs = {}
        result.append(PrinterInfo(name, attrs))
    return result


def default_printer():
    """默认打印机：系统设置的优先，否则第一台。"""
    conn = _conn()
    try:
        name = conn.getDefault()
    except Exception:
        name = None
    printers = list_printers()
    if name:
        for printer in printers:
            if printer.name == name:
                return printer
    return printers[0] if printers else None


def get_printer(name):
    for printer in list_printers():
        if printer.name == name:
            return printer
    return None


# --------------------------------------------------------------------------
# 作业
# --------------------------------------------------------------------------

def submit(printer_name, pdf_path, title, options):
    """提交一个打印作业，返回作业号。

    options 是 IPP 作业属性（见 options.PrintOptions.to_cups）。
    """
    conn = _conn()
    try:
        return conn.printFile(printer_name, pdf_path, title, dict(options))
    except cups.IPPError as exc:
        raise PrintError('提交打印作业失败：{}'.format(exc))
    except OSError as exc:
        raise PrintError('无法读取待打印文件：{}'.format(exc))


def job_state(job_id):
    """查作业状态，返回 (状态文字, 详情)。"""
    conn = _conn()
    try:
        attrs = conn.getJobAttributes(job_id)
    except Exception:
        return ('已过期', '')
    state = attrs.get('job-state', 0)
    reasons = attrs.get('job-state-reasons', [])
    if isinstance(reasons, str):
        reasons = [reasons]
    text = JOB_STATES.get(state, '未知')
    detail = '、'.join(str(r) for r in reasons if r)
    return (text, detail)


def cancel(job_id):
    """取消作业（已经开印的撤不掉）。"""
    conn = _conn()
    try:
        conn.cancelJob(job_id)
        return True
    except Exception:
        return False


def job_exists(job_id):
    conn = _conn()
    try:
        attrs = conn.getJobAttributes(job_id)
    except Exception:
        return False
    return bool(attrs)


def temp_pdf_path(prefix='pdf-print-'):
    """打印用的临时 PDF 放哪儿。"""
    import tempfile
    return os.path.join(tempfile.gettempdir(), prefix + str(os.getpid()) + '.pdf')
