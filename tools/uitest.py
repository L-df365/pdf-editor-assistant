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
PDF = '/tmp/pyw/many.pdf'
os.makedirs(SHOTS, exist_ok=True)

RESULTS = []


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


def run(app):
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
        drag(app, source,
             source.winfo_width() // 2, source.winfo_height() // 2,
             target.winfo_width() // 2,
             target.winfo_height() // 2 + 30)
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
        for path in ('/tmp/pyw/test.docx', '/tmp/pyw/photo.png'):
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
        sheet = InsertSheet(app.root, paths=['/tmp/pyw/many.pdf'],
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
            return '/tmp/pyw/many.pdf'

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
                  '/tmp/pyw/many.pdf' in sheet.selected,
                  str(sheet.selected))
            grab = app.root.tk.call('grab', 'current')
            check('浏览后 grab 回到浮层', 'filesheet' in str(grab), str(grab))
        sheet.destroy()
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
    app = MainWindow()
    app.root.geometry('1280x800')
    app.root.update()
    if os.path.isfile(PDF):
        app.open_file(PDF)
    app.root.update()
    app.root.after(300, lambda: (run(app), False)[-1])
    app.root.mainloop()


if __name__ == '__main__':
    main()
