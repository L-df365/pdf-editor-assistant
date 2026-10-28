"""打印后端：CUPS / IPP。

能力探测、作业提交、状态查询、取消都收在这一层，
上层（打印当前文档 / 批量队列）不直接碰 CUPS。

用 IPP 属性而不是厂商 PPD 选项：换一台打印机不用改代码。
实测本机 Konica C368 支持：
sides-supported = 单面 / 双面长边 / 双面短边
print-color-mode-supported = color / monochrome
media-supported = 52 种
number-up-supported = 1 2 4 6 9 16
page-ranges-supported = True
"""

import os
import shutil

from .errors import PrintError

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


class PrinterInfo:
    """一台打印机的能力。"""

    def __init__(self, name, attrs):
        self.name = name
        self.attrs = attrs
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

    # ------------------------------------------------------------------
    # 厂商专属选项
    # ------------------------------------------------------------------

    def _ppd_path(self):
        """这台打印机的 PPD 文件路径（拿不到就是 None）。"""
        try:
            path = _conn().getPPD(self.name)
        except Exception:
            return None
        return path if path and os.path.exists(path) else None

    def _ppd_text(self):
        """PPD 的内容（读不到就返回空串 —— 很多系统上 PPD 只有 root 能读）。"""
        path = self._ppd_path()
        if not path:
            return ''
        try:
            with open(path, encoding='utf-8', errors='ignore') as f:
                return f.read()
        except OSError:
            return ''

    def _ppd_option_names(self):
        """PPD 里用到的颜色选项名。"""
        text = self._ppd_text()
        if not text:
            return ()
        return tuple(name for name in ('ColorModel', 'SelectColor')
                     if ('*%s ' % name) in text)

    def _ppd_choices(self, option):
        """PPD 某个选项的候选值。"""
        text = self._ppd_text()
        if not text:
            return []
        choices = []
        prefix = '*%s ' % option
        for line in text.splitlines():
            if not line.startswith(prefix):
                continue
            value = line[len(prefix):].split(':')[0].split('/')[0].strip()
            if value and value not in choices:
                choices.append(value)
        return choices

    def extra_options(self, options):
        """补上标准 IPP 属性覆盖不到的地方。

        两件事：
        1. 黑白打印要显式指定 PDF→PS 的渲染器：默认的 Poppler 不会转灰度，
           出来还是彩的。
        2. 有些打印机的 PPD 里没有标准的 ColorModel，只有厂商自己的颜色选项
           （例如 Konica 的 SelectColor），这时 print-color-mode 会被驱动丢掉。
        """
        extras = {}
        if options.get('print-color-mode') == 'monochrome':
            renderer = pdf_renderer()
            if renderer:
                extras['pdftops-renderer'] = renderer
        names = self._ppd_option_names()
        if 'ColorModel' in names:
            return extras
        color = options.get('print-color-mode')
        if not color or 'SelectColor' not in names:
            return extras
        value = self._vendor_color_value(color)
        if value:
            extras['SelectColor'] = value
        return extras

    def _vendor_color_value(self, color):
        """从 PPD 的候选里挑一个对应的颜色值。"""
        choices = self._ppd_choices('SelectColor')
        if not choices:
            return None
        if color == 'monochrome':
            for want in ('grayscale', 'gray', 'black', 'mono'):
                for choice in choices:
                    if want in choice.lower():
                        return choice
            return None
        for choice in choices:
            low = choice.lower()
            if 'color' in low and 'gray' not in low and 'black' not in low:
                return choice
        return None


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

def pdf_renderer():
    """PDF → PostScript 用哪个渲染器。

    cups-filters 默认用 Poppler(pdftops) 转，**它不会把 PDF 转成灰度** ——
    打印黑白时颜色信息会丢，出来还是彩的（日志里会写
    "Poppler is not able to convert to grayscale/monochrome PostScript"）。
    Ghostscript / MuPDF 都能转，所以黑白打印要显式指定渲染器。
    """
    for name, binary in (('gs', 'gs'), ('mupdf', 'mutool'),
                         ('pdftocairo', 'pdftocairo')):
        if shutil.which(binary):
            return name
    return None


def submit(printer_name, pdf_path, title, options, printer=None):
    """提交一个打印作业，返回作业号。

    options 是 IPP 作业属性（见 options.PrintOptions.to_cups）。
    printer 给了的话，会按这台打印机的 PPD 补上厂商专属选项。
    """
    conn = _conn()
    options = dict(options)
    if printer is not None:
        options.update(printer.extra_options(options))
    try:
        return conn.printFile(printer_name, pdf_path, title, options)
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


def sides_text(sides):
    """CUPS 的 sides 值 → 中文。"""
    return {'one-sided': '单面', 'two-sided-long-edge': '双面长边',
            'two-sided-short-edge': '双面短边'}.get(sides, sides)


def temp_pdf_path(prefix='pdf-print-'):
    """打印用的临时 PDF 放哪儿。"""
    import tempfile
    return os.path.join(tempfile.gettempdir(), prefix + str(os.getpid()) + '.pdf')
