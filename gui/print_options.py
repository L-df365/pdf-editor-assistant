"""打印参数表单。

「打印当前 PDF」和以后的「批量打印」共用这一块界面：
批量打印里每个队列项的逐项覆盖，用的就是同一个表单。
"""

import tkinter as tk
from tkinter import ttk

from core.print_core import PrintOptions
from core.print_core import ranges
from gui.theme import DANGER, INK, INK_2, INK_3, LINE, PAPER, font
from gui.widgets import Segmented

#: 常见纸张的中文/英文名（CUPS 的 media 名不好读）
MEDIA_LABELS = {
    'iso_a4_210x297mm': 'A4',
    'iso_a3_297x420mm': 'A3',
    'iso_a5_148x210mm': 'A5',
    'iso_a6_105x148mm': 'A6',
    'jis_b4_257x364mm': 'B4',
    'jis_b5_182x257mm': 'B5',
    'na_letter_8.5x11in': 'Letter',
    'na_legal_8.5x14in': 'Legal',
    'na_tabloid_11x17in': 'Tabloid',
    'na_executive_7.25x10.5in': 'Executive',
}


def media_label(name):
    """把 CUPS 的 media 名变成人能读的标签。"""
    if not name:
        return ''
    if name in MEDIA_LABELS:
        return MEDIA_LABELS[name]
    parts = name.split('_')
    if len(parts) >= 2 and parts[0] in ('iso', 'na', 'jis'):
        return parts[1].upper()
    return name


class PrintOptionsForm(tk.Frame):
    """打印参数表单（颜色、单双面、份数、纸张、缩放、N-up、页码范围）。"""

    def __init__(self, parent, bg=PAPER, show_pages=True, on_change=None,
                 page_total=0):
        super().__init__(parent, bg=bg)
        self._on_change = on_change
        self._page_total = page_total
        self._printer = None
        self._media_names = []
        self._build(show_pages)

    # ------------------------------------------------------------------

    def _row(self, label):
        """新建一行，返回这一行里放控件的容器。

        控件必须用这一行当父容器创建：Tk 的控件不能改父，
        建好了再 pack 到别处，位置会整个乱掉。
        """
        line = tk.Frame(self, bg=self.cget('bg'))
        line.pack(fill='x', pady=(0, 8))
        tk.Label(line, text=label, bg=self.cget('bg'), fg=INK_2,
                 font=font('body'), width=6, anchor='w').pack(side='left')
        return line

    def _note(self, line, text):
        """行尾的提示文字（放在控件右边）。"""
        tk.Label(line, text=text, bg=self.cget('bg'), fg=INK_3,
                 font=font('meta')).pack(side='left', padx=(8, 0))

    def _build(self, show_pages):
        color_row = self._row('颜色')
        self.color_choice = Segmented(
            color_row, [('', '默认'), ('color', '彩色'), ('mono', '黑白')],
            value='', command=lambda v: self._changed())
        self.color_choice.pack(side='left')

        duplex_row = self._row('单双面')
        self.duplex_choice = Segmented(
            duplex_row, [('', '默认'), ('one', '单面'), ('long', '双面长边'),
                         ('short', '双面短边')],
            value='', command=lambda v: self._changed())
        self.duplex_choice.pack(side='left')

        copies_row = self._row('份数')
        self.copies = tk.Spinbox(copies_row, from_=1, to=99, width=4,
                                 font=font('num'), justify='center',
                                 bg=PAPER, fg=INK, relief='flat',
                                 highlightbackground=LINE,
                                 highlightthickness=1,
                                 buttonbackground=PAPER)
        self.copies.pack(side='left')
        self.copies.bind('<KeyRelease>', lambda e: self._changed())

        media_row = self._row('纸张')
        self.media_box = ttk.Combobox(media_row, state='readonly', width=18,
                                      font=font('body'))
        self.media_box.pack(side='left')
        self.media_box.bind('<<ComboboxSelected>>', lambda e: self._changed())

        scaling_row = self._row('缩放')
        self.scaling_choice = Segmented(
            scaling_row, [('', '默认'), ('auto-fit', '适合'), ('none', '原始'),
                          ('fill', '填满')], value='',
            command=lambda v: self._changed())
        self.scaling_choice.pack(side='left')

        nup_row = self._row('N-up')
        self.nup_choice = Segmented(
            nup_row, [(1, '1'), (2, '2'), (4, '4'), (6, '6')],
            value=1, command=lambda v: self._changed())
        self.nup_choice.pack(side='left')

        if show_pages:
            pages_row = self._row('页码')
            self.page_entry = ttk.Entry(pages_row, font=font('body'),
                                        width=16)
            self.page_entry.pack(side='left')
            self.page_entry.bind('<KeyRelease>', lambda e: self._changed())
            self._note(pages_row, '如 1-5,8,10-')
        else:
            self.page_entry = None

        self.problem_label = tk.Label(self, text='', bg=self.cget('bg'),
                                      fg=DANGER, font=font('meta'),
                                      anchor='w', justify='left')
        self.problem_label.pack(fill='x', pady=(2, 0))

    # ------------------------------------------------------------------

    def set_printer(self, printer):
        """按打印机的能力更新可选项。"""
        self._printer = printer
        names = []
        if printer:
            for media in printer.media:
                names.append((media, media_label(media)))
        self.media_box['values'] = [label for _, label in names]
        self._media_names = [key for key, _ in names]
        if names:
            index = 0
            default = getattr(printer, 'media_default', '')
            if default and default in self._media_names:
                index = self._media_names.index(default)
            self.media_box.current(index)
        # 打印机不支持的选项直接置灰，并且不预选
        self.duplex_choice.set_value('')
        self.color_choice.set_value('')
        if printer:
            self.duplex_choice.disable_item('long',
                                            not printer.supports_duplex('long'))
            self.duplex_choice.disable_item('short',
                                            not printer.supports_duplex('short'))
            self.duplex_choice.disable_item('one',
                                            not printer.supports_duplex('one'))
            self.color_choice.disable_item(
                'color', not printer.supports_color('color'))
            self.color_choice.disable_item(
                'mono', not printer.supports_color('mono'))
        self._changed()

    def set_page_total(self, total):
        self._page_total = total

    # ------------------------------------------------------------------

    def options(self):
        """当前表单的值。"""
        media = ''
        index = self.media_box.current()
        if index >= 0 and index < len(self._media_names):
            media = self._media_names[index]
        try:
            copies = max(1, min(99, int(self.copies.get())))
        except (ValueError, tk.TclError):
            copies = 1
        pages = ''
        if self.page_entry is not None:
            pages = self.page_entry.get().strip()
        return PrintOptions(
            pages=pages,
            copies=copies,
            media=media,
            scaling=self.scaling_choice.get(),
            color=self.color_choice.get(),
            duplex=self.duplex_choice.get(),
            nup=self.nup_choice.get() or 1,
        )

    def set_options(self, opts):
        self.color_choice.set_value(opts.color, notify=False)
        self.duplex_choice.set_value(opts.duplex, notify=False)
        self.scaling_choice.set_value(opts.scaling, notify=False)
        self.nup_choice.set_value(opts.nup, notify=False)
        self.copies.delete(0, 'end')
        self.copies.insert(0, str(opts.copies))
        if self.page_entry is not None:
            self.page_entry.delete(0, 'end')
            self.page_entry.insert(0, opts.pages)
        if opts.media and opts.media in getattr(self, '_media_names', []):
            self.media_box.current(self._media_names.index(opts.media))
        self._changed()

    def set_page_range(self, text):
        if self.page_entry is None:
            return
        self.page_entry.delete(0, 'end')
        self.page_entry.insert(0, text)
        self._changed()

    # ------------------------------------------------------------------

    def problems(self):
        """检查当前参数在打印机上能不能打。

        返回问题描述列表；**不静默降级**——不支持就明说，让用户改。
        """
        issues = []
        opts = self.options()
        printer = self._printer
        if printer is None:
            return ['没有找到可用的打印机']
        if not printer.online:
            issues.append('打印机当前不接收任务（{}）'.format(printer.state_text))
        if not printer.supports_duplex(opts.duplex):
            issues.append('该打印机不支持{}，可选：{}'.format(
                _duplex_label(opts.duplex),
                '、'.join(_sides_text(s) for s in printer.sides) or '无'))
        if not printer.supports_color(opts.color):
            issues.append('该打印机不支持{}'.format(_color_label(opts.color)))
        if not printer.supports_media(opts.media):
            issues.append('该打印机不支持所选纸张')
        if not printer.supports_nup(opts.nup):
            issues.append('该打印机不支持每张 {} 页'.format(opts.nup))
        # 页码范围
        text = opts.pages.strip()
        if text:
            try:
                segments = ranges.parse(text, self._page_total or None)
            except ranges.RangeError as exc:
                issues.append('页码范围有误：{}'.format(exc))
            else:
                if self._page_total and not segments:
                    issues.append('页码范围超出文档范围（共 {} 页）'.format(
                        self._page_total))
        return issues

    def _changed(self):
        issues = self.problems()
        if issues:
            self.problem_label.configure(text='\n'.join(issues))
        else:
            self.problem_label.configure(text='')
        if self._on_change:
            self._on_change(issues)


def _duplex_label(mode):
    return {'one': '单面', 'long': '双面长边', 'short': '双面短边'}.get(mode,
                                                                       '单双面')


def _color_label(mode):
    return {'color': '彩色', 'mono': '黑白'}.get(mode, '颜色')


def _sides_text(sides):
    return {'one-sided': '单面', 'two-sided-long-edge': '双面长边',
            'two-sided-short-edge': '双面短边'}.get(sides, sides)
