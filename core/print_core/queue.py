"""批量打印队列。

顺序执行、可以暂停/继续/取消，失败的任务隔离在原地不影响后面的。
状态变化通过回调抛给界面（界面在主线程里收，更新列表）。

队列本身不碰界面，也不需要 PyMuPDF——
只有"打印内存里打开的文档"那种作业才需要（由调用方提供文档对象）。
"""

import threading

from . import backend
from .errors import PrintError
from .jobs import PrintState


class PrintQueue:
    """一批打印任务。"""

    def __init__(self, printer='', on_event=None):
        self.printer = printer
        self.on_event = on_event
        self.jobs = []
        self._thread = None
        self._pause = threading.Event()
        self._pause.set()          # 有信号 = 继续跑
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self._running = False

    # -- 队列内容 ----------------------------------------------------

    def add(self, job):
        with self._lock:
            self.jobs.append(job)
        self._emit(job, PrintState.PENDING, '等待中')
        return job

    def add_many(self, jobs):
        for job in jobs:
            self.add(job)

    def remove(self, job):
        with self._lock:
            if job in self.jobs:
                self.jobs.remove(job)

    def clear(self):
        with self._lock:
            self.jobs = []

    def failed_jobs(self):
        return [job for job in self.jobs if job.state == PrintState.FAILED]

    def retry_failed(self):
        """把失败的任务重置成待处理（不自动开跑，由界面决定）。"""
        retried = []
        for job in self.failed_jobs():
            job.state = PrintState.PENDING
            job.error = ''
            job.job_ids = []
            retried.append(job)
            self._emit(job, PrintState.PENDING, '等待重试')
        return retried

    @property
    def running(self):
        return self._running

    def progress(self):
        """已完成 / 总数。"""
        total = len(self.jobs)
        done = sum(1 for job in self.jobs
                   if job.state in (PrintState.DONE, PrintState.FAILED,
                                    PrintState.CANCELLED))
        return done, total

    # -- 控制 --------------------------------------------------------

    def start(self):
        """开始（或继续）跑队列。"""
        if self._thread and self._thread.is_alive():
            self._pause.set()
            return
        self._stop.clear()
        self._pause.set()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def pause(self):
        """暂停：不再提交新的作业（已经提交的照打）。"""
        self._pause.clear()

    def resume(self):
        self._pause.set()

    def cancel(self):
        """取消整批：没提交的丢弃，提交了的撤掉。"""
        self._stop.set()
        self._pause.set()
        for job in self.jobs:
            if job.state in (PrintState.PENDING, PrintState.PREPARING,
                             PrintState.SUBMITTING):
                job.state = PrintState.CANCELLED
                self._emit(job, PrintState.CANCELLED, '已取消')
            elif job.state == PrintState.PRINTING:
                for job_id in job.job_ids:
                    backend.cancel(job_id)

    def wait(self, timeout=None):
        """等队列跑完（给命令行/独立工具用）。"""
        if self._thread:
            self._thread.join(timeout)

    # -- 执行 --------------------------------------------------------

    def _run(self):
        self._running = True
        try:
            for job in list(self.jobs):
                if self._stop.is_set():
                    break
                # 暂停点：等继续
                while not self._pause.wait(0.2):
                    if self._stop.is_set():
                        break
                if self._stop.is_set():
                    break
                if job.state in (PrintState.DONE, PrintState.CANCELLED):
                    continue
                self._run_job(job)
        finally:
            self._running = False

    def _run_job(self, job):
        from . import submit_job
        try:
            job.state = PrintState.PREPARING
            self._emit(job, PrintState.PREPARING, '准备文件')
            submit_job(job, printer=self.printer or job.printer,
                       on_event=self._on_job_event)
            job.state = PrintState.DONE
            job.error = ''
            self._emit(job, PrintState.DONE, '已提交')
        except PrintError as exc:
            job.state = PrintState.FAILED
            job.error = str(exc)
            self._emit(job, PrintState.FAILED, job.error)
        except Exception as exc:
            job.state = PrintState.FAILED
            job.error = str(exc)
            self._emit(job, PrintState.FAILED, job.error)

    def _on_job_event(self, job, state, message):
        job.state = state
        self._emit(job, state, message)

    def _emit(self, job, state, message):
        if self.on_event:
            try:
                self.on_event(job, state, message)
            except Exception:
                pass
