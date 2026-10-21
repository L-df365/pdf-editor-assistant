#!/usr/bin/env python3
"""Tk 版界面自测：用 event_generate 造真实事件，逐项断言并截图。

    xvfb-run -a python3 tools/uitest.py

Tk 的好处是能真的模拟点击/拖拽，验证的是真实链路，
不像 GTK 那边只能验到逻辑层。
"""

import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import tkinter as tk  # noqa: E402

from gui.main_window import MainWindow  # noqa: E402

SHOTS = '/tmp/opencode/ui-tk'
FIXTURES = '/tmp/pyw'
PDF = os.path.join(FIXTURES, 'many.pdf')
SMALL_PDF = os.path.join(FIXTURES, 'six.pdf')
PNG = os.path.join(FIXTURES, 'photo.png')
DOCX = os.path.join(FIXTURES, 'test.docx')
os.makedirs(SHOTS, exist_ok=True)

RESULTS = []


def ensure_fixtures():
    """测试用的文件自己造：/tmp 会被清理，不能指望它一直都在。"""
    os.makedirs(FIXTURES, exist_ok=True)
    if not os.path.isfile(PDF):
        import pymupdf
        doc = pymupdf.open()
        for i in range(24):
            page = doc.new_page(width=595, height=842)
            page.insert_text((72, 120), 'Page {}'.format(i + 1), fontsize=36)
        doc.save(PDF)
        doc.close()
    if not os.path.isfile(SMALL_PDF):
        import pymupdf
        doc = pymupdf.open()
        for i in range(6):
            page = doc.new_page(width=595, height=842)
            page.insert_text((72, 120), 'Page {}'.format(i + 1), fontsize=36)
        doc.save(SMALL_PDF)
        doc.close()
    if not os.path.isfile(PNG):
        from PIL import Image
        Image.new('RGB', (400, 300), (120, 180, 200)).save(PNG)
    if not os.path.isfile(DOCX):
        with open(DOCX, 'wb') as f:
            f.write(b'PK\x03\x04 placeholder for tests')
    return PDF


def check(name, ok, detail=''):
    RESULTS.append((name, bool(ok), detail))
    print('{} {}{}'.format('PASS' if ok else 'FAIL', name,
                           ('  <- ' + detail) if detail and not ok else ''),
          flush=True)


def shot(name):
    subprocess.run(['import', '-window', 'root',
                    os.path.join(SHOTS, name + '.png')])


def pump(app, seconds=0.35):
    """跑一会儿事件循环，等界面把状态更新完。"""
    end = time.time() + seconds
    while time.time() < end:
        app.root.update()
        time.sleep(0.01)


def click(app, widget, x=None, y=None, button=1):
    if x is None:
        x = widget.winfo_width() // 2
    if y is None:
        y = widget.winfo_height() // 2
    widget.event_generate('<ButtonPress-%d>' % button, x=x, y=y)
    widget.event_generate('<ButtonRelease-%d>' % button, x=x, y=y)
    pump(app)


def drag(app, widget, x1, y1, x2, y2, steps=8):
    widget.event_generate('<ButtonPress-1>', x=x1, y=y1)
    app.root.update()
    for i in range(1, steps + 1):
        widget.event_generate(
            '<B1-Motion>', x=x1 + (x2 - x1) * i // steps,
            y=y1 + (y2 - y1) * i // steps)
        app.root.update()
        time.sleep(0.02)
    widget.event_generate('<ButtonRelease-1>', x=x2, y=y2)
    pump(app)


def drag_to(app, widget, target, offset=0, steps=8):
    """把 widget 上的指针拖到 target 的位置（屏幕上真实的坐标）。

    事件是发给 widget 的，坐标相对它自己的左上角；
    落点计算用的是屏幕坐标，所以要按两者屏幕位置的差换算。
    """
    tx = target.winfo_rootx() + target.winfo_width() // 2
    ty = target.winfo_rooty() + offset
    x1 = widget.winfo_width() // 2
    y1 = widget.winfo_height() // 2
    x2 = tx - widget.winfo_rootx()
    y2 = ty - widget.winfo_rooty()
    drag(app, widget, x1, y1, x2, y2, steps)


def run(app):
    ensure_fixtures()
    steps = []

    def step(fn):
        steps.append(fn)
        return fn

    @step
    def s1_open():
        check('打开了文档', app.doc.page_count == 24,
              'pages={}'.format(app.doc.page_count))
        check('页面轨有缩略图', len(app.thumb_panel.cards) == 24,
              str(len(app.thumb_panel.cards)))

    @step
    def s2_click_thumbnail():
        # 点第 5 页的缩略图
        label = app.thumb_panel.cards[4]['image']
        click(app, label)
        check('点缩略图切到第 5 页', app.current_page == 4,
              'current_page={}'.format(app.current_page))
        check('预览跟着切页', app.preview.counter.cget('text').startswith('05'),
              app.preview.counter.cget('text'))
        shot('01-点击缩略图')

    @step
    def s3_drag_reorder():
        def first_page_text():
            return app.doc.doc.load_page(0).get_text().strip()

        app._origin_text = first_page_text()
        before = first_page_text()
        source = app.thumb_panel.cards[0]['image']
        target = app.thumb_panel.cards[3]['image']
        # 拖到第 4 页的上半部分（落点线画在第 4 页上沿之前）
        drag_to(app, source, target, offset=6)
        after = first_page_text()
        check('拖拽改变了页面顺序', before != after,
              '第一页还是 {}'.format(after[:20]))
        shot('02-拖拽后')

    @step
    def s4_undo_redo():
        def first_page_text():
            return app.doc.doc.load_page(0).get_text().strip()

        origin = app._origin_text
        check('撤销可用', app.doc.history.can_undo, 'can_undo=False')
        app.undo()
        pump(app)
        check('撤销恢复到拖动前的顺序', first_page_text() == origin,
              '第一页是 {}'.format(first_page_text()[:20]))
        check('重做可用', app.doc.history.can_redo, 'can_redo=False')
        app.redo()
        pump(app)
        check('重做回到拖动后的顺序', first_page_text() != origin,
              '第一页是 {}'.format(first_page_text()[:20]))
        app.undo()
        pump(app)

    @step
    def s5_context_menu():
        label = app.thumb_panel.cards[2]['image']
        label.event_generate('<ButtonPress-3>', x=10, y=10)
        label.event_generate('<ButtonRelease-3>', x=10, y=10)
        pump(app)
        menu = getattr(app.thumb_panel, '_context_menu', None)
        win = getattr(menu, '_win', None)
        check('右键弹出菜单', win is not None and win.winfo_ismapped(),
              str(menu))
        if win is not None:
            shot('03-右键菜单')
            # 悬停：文字必须还在（不能被高亮底色盖住）
            canvas = menu._canvas
            canvas.event_generate('<Motion>', x=40, y=12)
            pump(app, 0.2)
            shot('04-菜单悬停')
            check('悬停时文字仍在',
                  len(canvas.find_withtag('text')) > 0, '文字被盖住了')
            # 点外面关闭
            app.root.event_generate('<ButtonPress-1>', x=900, y=600)
            app.root.event_generate('<ButtonRelease-1>', x=900, y=600)
            pump(app)
            closed = menu._win is None
            if not closed:
                try:
                    closed = not win.winfo_ismapped()
                except tk.TclError:
                    closed = True
            check('点外面菜单消失', closed, '菜单还在')

    @step
    def s5b_info_panel():
        """信息面板：正文用 grid、脚注再 pack 会直接崩（面板打不开）。"""
        from gui.feedback import InfoPanel
        panel = InfoPanel(app.root, '关于',
                          [('作用', '把 Word、Excel 转成页面插进 PDF')],
                          footnote='改动随时可以撤销。')
        panel._place(app.root)
        pump(app, 0.3)
        check('关于面板能打开', panel.winfo_ismapped(), '面板没显示')
        panel.destroy()
        pump(app, 0.2)

    @step
    def s5c_undo_buttons():
        """撤销/重做按钮的可用状态要跟着历史走（Canvas 不认 state）。"""
        app._refresh_undo_buttons()
        pump(app, 0.2)
        check('撤销按钮状态跟历史一致',
              app.preview.undo_button._state ==
              ('normal' if app.doc.history.can_undo else 'disabled'),
              app.preview.undo_button._state)
        check('重做按钮状态跟历史一致',
              app.preview.redo_button._state ==
              ('normal' if app.doc.history.can_redo else 'disabled'),
              app.preview.redo_button._state)

    @step
    def s5d_drop_target():
        """拖拽落点：拖到第 4 页上沿，应该落在第 3 位（不是第 1 位）。"""
        rail = app.thumb_panel
        moved = []
        original = rail.on_reorder
        rail.on_reorder = lambda a, b: moved.append((a, b))
        try:
            source = rail.cards[1]['image']
            target = rail.cards[3]['image']
            drag_to(app, source, target, offset=4)
        finally:
            rail.on_reorder = original
        check('拖拽落点算对了', moved and moved[0][1] == 2,
              'moved={}'.format(moved))

    @step
    def s6_scrollbar():
        rail = app.thumb_panel
        sb = getattr(rail, 'scrollbar', None)
        ok = sb is not None and sb.winfo_ismapped()
        check('页面轨有可见的滚动条', ok, str(sb))
        shot('05-滚动条')

    @step
    def s7_file_sheet():
        from gui.file_sheet import FileSheet
        sheet = FileSheet(app.root, mode='insert',
                          current_path=app.doc.filepath,
                          confirm_text='插入')
        sheet._place(app.root)
        pump(app, 0.3)
        shot('06-文件面板')
        for path in (DOCX, PNG):
            if os.path.exists(path):
                sheet.selected.add(path)
        sheet._update_selection_label()
        pump(app, 0.2)
        check('已选计数有显示',
              '已选' in sheet.selection_label.get_text(),
              sheet.selection_label.get_text())
        check('主按钮有文案', sheet.confirm_button._text == '插入',
              sheet.confirm_button._text)
        check('主按钮已可用', sheet.confirm_button._state == 'normal',
              sheet.confirm_button._state)
        shot('07-已选文件')
        sheet.destroy()
        pump(app, 0.2)

    @step
    def s8_sheet_footer():
        """文件面板的底部按钮行必须完整落在窗口里（小屏会被切掉半截）。"""
        from gui.file_sheet import FileSheet
        sheet = FileSheet(app.root, mode='insert',
                          current_path=app.doc.filepath,
                          confirm_text='插入')
        sheet._place(app.root)
        pump(app, 0.3)
        foot = sheet.button_frame
        bottom = foot.winfo_rooty() + foot.winfo_height()
        win_bottom = sheet.winfo_rooty() + sheet.winfo_height()
        check('文件面板底部按钮没被切掉', bottom <= win_bottom,
              '按钮底={} 窗口底={}'.format(bottom, win_bottom))
        shot('08-文件面板底部')
        sheet.destroy()
        pump(app, 0.2)

    @step
    def s9_insert_position_sheet():
        """插入位置面板：以前这里少导入一个颜色常量会直接崩。"""
        from gui.insert_sheet import InsertSheet
        sheet = InsertSheet(app.root, paths=[PDF],
                            current_page=app.current_page,
                            page_count=app.doc.page_count)
        sheet._place(app.root)
        pump(app, 0.3)
        check('插入位置面板能打开', sheet.winfo_ismapped(), '打不开')
        foot = sheet.button_frame
        bottom = foot.winfo_rooty() + foot.winfo_height()
        win_bottom = sheet.winfo_rooty() + sheet.winfo_height()
        check('插入位置面板按钮完整', bottom <= win_bottom,
              '按钮底={} 窗口底={}'.format(bottom, win_bottom))
        shot('09-插入位置')
        sheet.destroy()
        pump(app, 0.2)

    @step
    def s10_browse_button():
        """「浏览全部文件…」：开系统对话框前要放开 grab、收起浮层，
        否则对话框开不出来，整个界面像卡死。"""
        from gui.file_sheet import FileSheet

        def fake_browse(directory):
            return PDF

        sheet = FileSheet(app.root, mode='insert',
                          current_path=app.doc.filepath,
                          confirm_text='插入', on_browse=fake_browse)
        sheet._place(app.root)
        pump(app, 0.3)
        button = None
        for row in sheet.button_frame.winfo_children():
            for child in row.winfo_children():
                if getattr(child, '_text', '') == '浏览全部文件…':
                    button = child
        check('找得到浏览全部文件按钮', button is not None, '没找到')
        if button is not None:
            click(app, button)
            pump(app, 0.3)
            check('浏览后浮层还在', sheet.winfo_ismapped(), '浮层不见了')
            check('浏览后选中了文件',
                  PDF in sheet.selected,
                  str(sheet.selected))
            grab = app.root.tk.call('grab', 'current')
            check('浏览后 grab 回到浮层', 'filesheet' in str(grab), str(grab))
        sheet.destroy()
        pump(app, 0.2)

    @step
    def s7b_file_sheet_multiselect():
        """文件面板的多选：点一个加一个，Ctrl 能加，再点一次能取消。"""
        from gui.file_sheet import FileSheet
        sheet = FileSheet(app.root, mode='insert',
                          current_path=app.doc.filepath,
                          confirm_text='加入队列')
        sheet._place(app.root)
        pump(app, 0.3)

        def rows():
            return [i for i in sheet.tree.get_children()
                    if not sheet._row(i)['dir']]

        def click_row(path, state=0):
            box = sheet.tree.bbox(path)
            sheet.tree.event_generate('<Button-1>', x=40, y=box[1] + 5,
                                       state=state)
            pump(app, 0.1)

        items = rows()
        check('列表里有可选文件', len(items) >= 2,
              '只有 {} 个'.format(len(items)))
        if len(items) >= 2:
            click_row(items[0])
            check('点一下选中一个', len(sheet.selected) == 1,
                  str(len(sheet.selected)))
            click_row(items[1])
            check('再点一个变成两个', len(sheet.selected) == 2,
                  str(len(sheet.selected)))
            check('树里的高亮也是两个',
                  len(sheet.tree.selection()) == 2,
                  str(len(sheet.tree.selection())))
            if len(items) >= 3:
                click_row(items[2], state=0x0004)     # Ctrl
                check('Ctrl+点能加选', len(sheet.selected) == 3,
                      str(len(sheet.selected)))
            click_row(items[0])
            check('再点一次能取消', len(sheet.selected) == 2,
                  str(len(sheet.selected)))
            check('已选计数跟着变',
                  '2' in sheet.selection_label.get_text(),
                  sheet.selection_label.get_text())
        sheet.destroy()
        pump(app, 0.2)

    @step
    def s7c_long_name():
        """文件名特别长时，详情栏不能把文件列表挤没。"""
        from gui.file_sheet import INFO_WIDTH, FileSheet
        long_name = ('这是一个非常非常长的文件名用来测试详情栏会不会把文件列表'
                     '挤掉-' + '长' * 40 + '.pdf')
        path = os.path.join(FIXTURES, long_name)
        if not os.path.isfile(path):
            with open(path, 'wb') as f:
                f.write(b'%PDF-1.4\n')
        sheet = FileSheet(app.root, mode='insert', current_path=path,
                          confirm_text='加入队列')
        sheet._place(app.root)
        pump(app, 0.3)
        rows = [i for i in sheet.tree.get_children()
                if not sheet._row(i)['dir']]
        check('长文件名的面板没被撑爆', sheet.winfo_width() < 1000,
              '面板宽 {}'.format(sheet.winfo_width()))
        check('详情栏宽度有上限',
              sheet.info_label.winfo_reqwidth() <= INFO_WIDTH + 20,
              '详情宽 {}'.format(sheet.info_label.winfo_reqwidth()))
        check('文件列表还剩得下', sheet.tree.winfo_width() > 200,
              '列表宽 {}'.format(sheet.tree.winfo_width()))
        if rows:
            box = sheet.tree.bbox(rows[0])
            sheet.tree.event_generate('<Button-1>', x=40, y=box[1] + 5)
            pump(app, 0.2)
            check('选了长名字之后列表还在',
                  sheet.tree.winfo_width() > 200,
                  '列表宽 {}'.format(sheet.tree.winfo_width()))
        sheet.destroy()
        pump(app, 0.2)

    @step
    def s7d_folder_picker():
        """选文件夹用的也是自己画的面板：只列目录、有上级目录、能进能退。"""
        from gui.file_sheet import FileSheet
        sheet = FileSheet(app.root, mode='folder', current_path=FIXTURES,
                          confirm_text='选择此文件夹')
        sheet._place(app.root)
        pump(app, 0.3)
        check('文件夹面板能打开', sheet.winfo_ismapped(), '没打开')
        names = [sheet._row(i)['name'] for i in sheet.tree.get_children()]
        check('列表里只有目录',
              all(name.endswith('/') or name.startswith('..')
                  for name in names), str(names[:4]))
        check('有上级目录', any(name.startswith('..') for name in names),
              str(names[:3]))
        check('没有浏览全部文件按钮', not any(
            getattr(child, '_text', '') == '浏览全部文件…'
            for row in sheet.button_frame.winfo_children()
            for child in row.winfo_children()), '还在')
        check('确定按钮可用', sheet.confirm_button._state == 'normal',
              sheet.confirm_button._state)

        # 双击进目录
        dirs = [i for i in sheet.tree.get_children()
                if sheet._row(i)['dir'] and i != sheet._up_row]
        if dirs:
            box = sheet.tree.bbox(dirs[0])
            for _ in range(2):
                sheet.tree.event_generate('<ButtonPress-1>', x=40,
                                          y=box[1] + 5)
                sheet.tree.event_generate('<ButtonRelease-1>', x=40,
                                          y=box[1] + 5)
            pump(app, 0.3)
            check('双击能进目录', sheet.directory != FIXTURES,
                  sheet.directory)
            # 点上级目录回去
            if sheet._up_row:
                box = sheet.tree.bbox(sheet._up_row)
                sheet.tree.event_generate('<Button-1>', x=40, y=box[1] + 5)
                pump(app, 0.3)
                check('能回到上级目录', sheet.directory == FIXTURES,
                      sheet.directory)
        sheet.destroy()
        pump(app, 0.2)

    @step
    def s7e_fixed_width():
        """文件面板的宽度要固定：选不同文件时宽度不能跳。"""
        from gui.file_sheet import PANEL_WIDTH, FileSheet
        sheet = FileSheet(app.root, mode='insert', current_path=FIXTURES,
                          confirm_text='加入队列')
        sheet._place(app.root)
        pump(app, 0.3)
        check('面板宽度是固定的', sheet.winfo_width() == PANEL_WIDTH,
              '{} != {}'.format(sheet.winfo_width(), PANEL_WIDTH))
        files = [i for i in sheet.tree.get_children()
                 if not sheet._row(i)['dir'] and sheet.tree.bbox(i)]
        widths = {sheet.winfo_width()}
        for path in files[:3]:
            box = sheet.tree.bbox(path)
            if not box:
                continue
            sheet.tree.event_generate('<Button-1>', x=40, y=box[1] + 5)
            pump(app, 0.15)
            widths.add(sheet.winfo_width())
        check('选不同文件宽度不变', len(widths) == 1, str(widths))
        sheet.destroy()
        pump(app, 0.2)

    @step
    def s11b_rail_never_squeezed():
        """页面轨不能被分栏挤没（用户反馈过"侧边预览框不见了"）。

        - 启动后左栏要有宽度
        - 分栏位置被压到很窄时，要拉回下限
        - 分栏自己重排（窗口尺寸变化）也不能把左栏弄没
        """
        rail = app._left_frame
        floor = app.RAIL_MIN_WIDTH
        check('启动后左栏有宽度', rail.winfo_width() >= floor,
              '左栏宽 {}'.format(rail.winfo_width()))
        app._paned.sashpos(0, 20)
        pump(app, 0.3)
        check('左栏被压窄后拉回下限', rail.winfo_width() >= floor,
              '左栏宽 {}'.format(rail.winfo_width()))
        app._paned.sashpos(0, 280)
        pump(app, 0.3)
        check('宽度还能调回 280', rail.winfo_width() >= floor,
              '左栏宽 {}'.format(rail.winfo_width()))

    @step
    def s11c_rail_columns():
        """页面轨的列：默认一列，列宽要摊满（右边不留空白）。"""
        rail = app.thumb_panel
        # 先回到默认宽度（前面的步骤动过轨道）
        app._paned.sashpos(0, app._rail_width)
        pump(app, 0.4)
        check('默认排一列', rail._cols == 1, '排了 {} 列'.format(rail._cols))
        canvas_w = rail.canvas.winfo_width()
        content_w = rail.inner.winfo_reqwidth()
        check('单列时内容撑满轨道', abs(content_w - canvas_w) <= 12,
              '内容 {} 画布 {}'.format(content_w, canvas_w))

        # 拉宽 → 两列，且两列摊满
        app._paned.sashpos(0, 365)
        pump(app, 0.4)
        check('拉宽后排两列', rail._cols == 2,
              '排了 {} 列'.format(rail._cols))
        content_w = rail.inner.winfo_reqwidth()
        canvas_w = rail.canvas.winfo_width()
        check('两列摊满轨道', abs(content_w - canvas_w) <= 12,
              '内容 {} 画布 {}'.format(content_w, canvas_w))
        app._paned.sashpos(0, 210)
        pump(app, 0.4)

    @step
    def s11_layout_stable():
        """打开文件不该让界面横向跳一下。

        - 空状态和文档状态必须占同一块地方（预览区宽度不变）
        - 用户自己拖过的分栏宽度，重新打开文件也不能被拽回去
        """
        app._show_empty(True)
        pump(app, 0.3)
        empty_w = app.empty_state.frame.winfo_width()
        app._show_empty(False)
        pump(app, 0.3)
        loaded_w = app.preview.frame.winfo_width()
        check('打开文件时预览区宽度不变', abs(empty_w - loaded_w) <= 2,
              '空={} 载入={}'.format(empty_w, loaded_w))

        app._paned.sashpos(0, 360)
        pump(app, 0.3)
        dragged = app._paned.sashpos(0)
        app.open_file(PDF)
        pump(app, 0.5)
        check('重新打开文件不改变分栏宽度',
              abs(app._paned.sashpos(0) - dragged) <= 2,
              '{} -> {}'.format(dragged, app._paned.sashpos(0)))

    @step
    def s11_print_panel():
        """打印面板：能力探测、参数映射、能力校验拦截。

        用假的 CUPS 连接：不碰真打印机，也不会出纸。
        """
        from core.print_core import backend as printers
        from gui.print_sheet import PrintSheet

        class FakeConnection:
            def __init__(self):
                self.jobs = []

            def getPrinters(self):
                return ['FakePrinter']

            def getDefault(self):
                return 'FakePrinter'

            def getPrinterAttributes(self, name):
                return {
                    'printer-state': 3,
                    'printer-is-accepting-jobs': True,
                    'printer-state-reasons': [],
                    'sides-supported': ['one-sided',
                                        'two-sided-long-edge'],
                    'print-color-mode-supported': ['monochrome', 'color'],
                    'media-supported': ['iso_a4_210x297mm',
                                        'iso_a3_297x420mm'],
                    'media-default': 'iso_a4_210x297mm',
                    'number-up-supported': [1, 2],
                    'page-ranges-supported': True,
                }

            def printFile(self, printer, filename, title, options):
                self.jobs.append({'printer': printer, 'file': filename,
                                  'title': title, 'options': options})
                return 42

            def getJobAttributes(self, job_id):
                return {'job-state': 7}

            def cancelJob(self, job_id):
                return True

        fake = FakeConnection()
        printers.set_connection(fake)
        try:
            sheet = PrintSheet(app.root, app.doc, title='打印')
            sheet._place(app.root)
            pump(app, 0.3)
            check('打印面板能打开', sheet.winfo_ismapped(), '面板没显示')
            check('找到打印机了', sheet._printer is not None, '没找到打印机')
            check('默认能打印', sheet.print_button._state == 'normal',
                  '按钮被禁用了：{}'.format(sheet.form.problems()))

            # 参数要正确映射成 CUPS 的作业属性
            form = sheet.form
            form.color_choice.set_value('mono')
            form.duplex_choice.set_value('long')
            form.copies.delete(0, 'end')
            form.copies.insert(0, '2')
            form.set_page_range('1-2')
            pump(app, 0.3)
            opts = form.options()
            cups = opts.to_cups('1-2')
            check('颜色映射成 print-color-mode',
                  cups.get('print-color-mode') == 'monochrome', str(cups))
            check('单双面映射成 sides',
                  cups.get('sides') == 'two-sided-long-edge', str(cups))
            check('份数映射成 copies', cups.get('copies') == '2', str(cups))
            check('页码范围传下去了',
                  cups.get('page-ranges') == '1-2', str(cups))

            # 打印机不支持的选项要拦下来，不能静默降级
            form.duplex_choice.set_value('short')
            pump(app, 0.3)
            check('不支持的双面被拦下', bool(form.problems()),
                  '问题列表是空的')
            check('拦下后打印按钮禁用',
                  sheet.print_button._state == 'disabled',
                  sheet.print_button._state)
            form.duplex_choice.set_value('long')
            pump(app, 0.3)

            sheet._print()
            pump(app, 0.3)
            check('提交了一个打印作业', len(fake.jobs) == 1,
                  'jobs={}'.format(fake.jobs))
            if fake.jobs:
                job = fake.jobs[0]
                check('作业带上了参数',
                      job['options'].get('sides') == 'two-sided-long-edge',
                      str(job['options']))
                check('打印的是临时副本',
                      job['file'] != app.doc.filepath, job['file'])
                check('临时文件已清理',
                      not os.path.exists(job['file']), job['file'])
            sheet.destroy()
        finally:
            printers.set_connection(None)
        pump(app, 0.2)

    @step
    def s12_print_ranges():
        """页码范围解析：组合、开区间、后缀。"""
        from core.print_core import ranges
        check('解析组合范围',
              ranges.parse('1-5,8', 20) == [(1, 5, None), (8, 8, None)],
              str(ranges.parse('1-5,8', 20)))
        check('开区间补齐到末页',
              ranges.parse('18-', 20) == [(18, 20, None)],
              str(ranges.parse('18-', 20)))
        check('超出的页码被夹住',
              ranges.parse('1-99', 20) == [(1, 20, None)],
              str(ranges.parse('1-99', 20)))
        check('后缀模式能解析',
              ranges.parse('1-12d,13s', 20) ==
              [(1, 12, 'd'), (13, 13, 's')],
              str(ranges.parse('1-12d,13s', 20)))
        check('混了模式要拆作业', ranges.has_mixed_modes(
            ranges.parse('1-12d,13s', 20)), '没识别出来')
        check('页数统计正确',
              ranges.count_pages(ranges.parse('1-5,8', 20)) == 6,
              str(ranges.count_pages(ranges.parse('1-5,8', 20))))
        try:
            ranges.parse('abc', 20)
            ok = False
        except ranges.RangeError:
            ok = True
        check('写错的范围会报错', ok, '没报错')

    @step
    def s13_batch_window():
        """批量打印窗口：主程序里能开、能加文件、默认参数会下发、能跑队列。

        用假的 CUPS 连接，不会碰真打印机。
        """
        from core.print_core import backend as printers
        from gui.batch_print_window import BatchPrintWindow

        class FakeConnection:
            def __init__(self):
                self.jobs = []

            def getPrinters(self):
                return ['FakePrinter']

            def getDefault(self):
                return 'FakePrinter'

            def getPrinterAttributes(self, name):
                return {
                    'printer-state': 3,
                    'printer-is-accepting-jobs': True,
                    'printer-state-reasons': [],
                    'sides-supported': ['one-sided', 'two-sided-long-edge'],
                    'print-color-mode-supported': ['monochrome', 'color'],
                    'media-supported': ['iso_a4_210x297mm'],
                    'media-default': 'iso_a4_210x297mm',
                    'number-up-supported': [1, 2],
                    'page-ranges-supported': True,
                }

            def printFile(self, printer, filename, title, options):
                self.jobs.append({'file': filename, 'options': options})
                return 100 + len(self.jobs)

            def getJobAttributes(self, job_id):
                return {'job-state': 7}

            def cancelJob(self, job_id):
                return True

        fake = FakeConnection()
        printers.set_connection(fake)
        try:
            window = BatchPrintWindow(app.root)
            pump(app, 0.3)
            check('批量打印窗口能打开', window.win.winfo_ismapped(), '没打开')
            check('批量窗口找到打印机', window._printer is not None, '没找到')

            window.add_paths([SMALL_PDF, PDF])
            pump(app, 0.2)
            check('队列加进了文件', len(window.queue.jobs) == 2,
                  str(len(window.queue.jobs)))
            check('队列表格有行',
                  len(window.tree.get_children()) == 2,
                  str(len(window.tree.get_children())))

            # 默认参数要下发到队列项
            window.form.color_choice.set_value('mono')
            window.form.duplex_choice.set_value('long')
            pump(app, 0.2)
            first = window.queue.jobs[0]
            check('默认参数下发到队列项',
                  first.options.color == 'mono' and
                  first.options.duplex == 'long',
                  '{} {}'.format(first.options.color, first.options.duplex))

            # 跑队列
            window._start()
            for _ in range(40):
                pump(app, 0.1)
                if len(fake.jobs) >= 2:
                    break
            check('队列提交了两个作业', len(fake.jobs) == 2,
                  str(len(fake.jobs)))
            if fake.jobs:
                check('作业带上了参数',
                      fake.jobs[0]['options'].get('sides') ==
                      'two-sided-long-edge',
                      str(fake.jobs[0]['options']))
                check('队列项状态变成已完成',
                      window.queue.jobs[0].state == 'done',
                      window.queue.jobs[0].state)
            window.win.destroy()
        finally:
            printers.set_connection(None)
        pump(app, 0.2)

    @step
    def s13b_batch_sort():
        """队列排序：按文件名排 + 每行的上下箭头能手动调顺序。"""
        from gui.batch_print_window import BatchPrintWindow

        window = BatchPrintWindow(app.root)
        pump(app, 0.3)
        window.add_paths([PNG, DOCX, PDF])
        pump(app, 0.2)
        names = [job.name for job in window.queue.jobs]
        check('按添加顺序排', names == [os.path.basename(p) for p in
                                       (PNG, DOCX, PDF)], str(names))

        tree = window.tree

        def column_x(number):
            total = 0
            for i in range(number - 1):
                total += tree.column('#{}'.format(i + 1), 'width')
            return total + 10

        # 点第 2 行的 ↓：它应该和第 3 行换位
        rows = tree.get_children()
        box = tree.bbox(rows[1])
        tree.event_generate('<Button-1>', x=column_x(len(tree['columns'])),
                            y=box[1] + 5)
        pump(app, 0.2)
        moved = [job.name for job in window.queue.jobs]
        check('点↓能往下挪', moved[1] == names[2] and moved[2] == names[1],
              str(moved))

        # 点第 3 行的 ↑：换回去
        rows = tree.get_children()
        box = tree.bbox(rows[2])
        tree.event_generate('<Button-1>', x=column_x(len(tree['columns']) - 1),
                            y=box[1] + 5)
        pump(app, 0.2)
        back = [job.name for job in window.queue.jobs]
        check('点↑能往上挪', back == names, str(back))

        # 按文件名排序
        window.sort_box.current(1)
        window._on_sort()
        pump(app, 0.2)
        sorted_names = [job.name for job in window.queue.jobs]
        check('能按文件名排序', sorted_names == sorted(names), str(sorted_names))
        window.win.destroy()
        pump(app, 0.2)

    def stepper():
        if not steps:
            print('\n===== 结果 =====')
            failed = [r for r in RESULTS if not r[1]]
            print('通过 {}/{}'.format(len(RESULTS) - len(failed), len(RESULTS)))
            for name, _, detail in failed:
                print('  FAIL', name, detail)
            app.root.quit()
            return False
        fn = steps.pop(0)
        try:
            fn()
        except Exception as exc:
            import traceback
            traceback.print_exc()
            check('步骤异常: {}'.format(getattr(fn, '__name__', fn)), False,
                  str(exc))
        app.root.after(120, stepper)
        return False

    app.root.after(600, stepper)


def main():
    ensure_fixtures()          # 先备料：/tmp 里的文件可能被清理掉
    app = MainWindow()
    app.root.geometry('1280x800')
    app.root.update()
    app.open_file(PDF)
    app.root.update()
    app.root.after(300, lambda: (run(app), False)[-1])
    app.root.mainloop()


if __name__ == '__main__':
    main()
