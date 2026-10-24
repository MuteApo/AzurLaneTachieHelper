"""One bounded worker per owner; all results return through queued Qt signals."""

import logging
import threading
import traceback
from collections.abc import Callable
from typing import cast, override

from PySide6.QtCore import QCoreApplication, QObject, QRunnable, QThreadPool, Signal, Slot

from domain.messages import Message, Progress

logger = logging.getLogger(__name__)


type Task[T] = Callable[[Progress], T]


class Cancelled(Exception):
    """Raised only at a task's documented progress checkpoints."""


class _Signals(QObject):
    progress = Signal(object, int, int)
    completed = Signal(object)
    failed = Signal(object, str)
    cancelled = Signal()


class _Work(QRunnable):
    def __init__(self, function: Task[object], signals: _Signals, cancel: threading.Event):
        super().__init__()
        self.function, self.signals, self.cancel = function, signals, cancel

    def report(self, message: str | Message, current: int = 0, total: int = 0) -> None:
        if self.cancel.is_set():
            raise Cancelled()
        self.signals.progress.emit(message, current, total)

    @override
    @Slot()
    def run(self) -> None:
        try:
            self.report(QCoreApplication.translate("Tasks", "Preparing"))
            result = self.function(self.report)
        except Cancelled:
            self.signals.cancelled.emit()
        except Exception as error:
            logger.exception("任务失败")
            self.signals.failed.emit(error, traceback.format_exc())
        else:
            self.signals.completed.emit(result)


class TaskRunner(QObject):
    progress = Signal(object, int, int)
    failed = Signal(object, str)
    busy_changed = Signal(bool)
    cancelled = Signal()

    def __init__(self, parent: QObject):
        super().__init__(parent)
        self.pool = QThreadPool(self)
        self.pool.setMaxThreadCount(1)
        self.busy = False
        self._cancel = threading.Event()
        self._signals: _Signals | None = None
        self._done: Callable[[object], None] | None = None

    def start[T](self, function: Task[T], done: Callable[[T], None]) -> bool:
        if self.busy:
            return False
        self.busy = True
        self._cancel.clear()
        # Qt transports arbitrary objects; restore the task's result type only here.
        self._done = lambda result: done(cast(T, result))
        self._signals = _Signals(self)
        self._signals.progress.connect(self.progress)
        self._signals.completed.connect(self._complete)
        self._signals.failed.connect(self._fail)
        self._signals.cancelled.connect(self._cancelled)
        self.busy_changed.emit(True)
        self.pool.start(_Work(function, self._signals, self._cancel))
        return True

    def cancel(self):
        self._cancel.set()

    def _finish(self):
        self._done = None
        self.busy = False
        self.busy_changed.emit(False)
        if self._signals:
            self._signals.deleteLater()
            self._signals = None

    @Slot(object)
    def _complete(self, result: object) -> None:
        done = self._done
        self._finish()
        if done:
            done(result)

    @Slot(object, str)
    def _fail(self, message: Exception, details: str) -> None:
        self._finish()
        self.failed.emit(message, details)

    @Slot()
    def _cancelled(self):
        self._finish()
        self.cancelled.emit()
