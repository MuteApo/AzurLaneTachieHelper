import argparse
import logging
import sys
from pathlib import Path

from PySide6.QtCore import QCoreApplication, QLocale, QStandardPaths


def _argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=QCoreApplication.translate("Main", "Tachie · Azur Lane artwork workbench")
    )
    parser.add_argument(
        "project",
        nargs="?",
        type=Path,
        help=QCoreApplication.translate("Main", "metadata or a saved .tachie.json project"),
    )
    parser.add_argument(
        "--manifest", type=Path, help=QCoreApplication.translate("Main", "use this dependencies index")
    )
    parser.add_argument(
        "--inspect",
        action="store_true",
        help=QCoreApplication.translate("Main", "list assets in the terminal without opening a window"),
    )
    parser.add_argument(
        "--psd", type=Path, help=QCoreApplication.translate("Main", "export a PSD without opening a window")
    )
    parser.add_argument(
        "--export",
        dest="output",
        type=Path,
        help=QCoreApplication.translate("Main", "export project edits to this folder"),
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help=QCoreApplication.translate("Main", "record detailed diagnostic logs"),
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        help=QCoreApplication.translate("Main", "use this settings and log directory (portable mode)"),
    )
    return parser


def main() -> int:
    # Determine the Qt application type and settings location before translating help.
    bootstrap = argparse.ArgumentParser(add_help=False)
    bootstrap.add_argument("-h", "--help", action="store_true")
    bootstrap.add_argument("--data-dir", type=Path)
    bootstrap.add_argument("--inspect", action="store_true")
    bootstrap.add_argument("--psd", type=Path)
    bootstrap.add_argument("--export", dest="output", type=Path)
    bootstrap.add_argument("--verbose", action="store_true")
    early, _ = bootstrap.parse_known_args()
    gui = not (early.help or early.inspect or early.psd or early.output)
    if gui:
        from PySide6.QtGui import QFont
        from PySide6.QtWidgets import QApplication

        app = QApplication(sys.argv[:1])
        app.setStyle("Fusion")
        app.setFont(QFont("Microsoft YaHei UI" if sys.platform == "win32" else "Sans Serif", 10))
    else:
        app = QCoreApplication(sys.argv[:1])
    app.setOrganizationName("Tachie")
    # Keep the existing settings and logs location after promoting the application.
    app.setApplicationName("TachieNext")

    from adapters.storage import Settings
    from logging_setup import configure_logging
    from ui.i18n import configure_language, render_message

    data_dir = early.data_dir or Path(
        QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppLocalDataLocation)
    )
    # --help only reads preferences; it does not create logs or configuration files.
    log_path = configure_logging(data_dir / "logs", early.verbose) if not early.help else None
    configure_language("system")
    try:
        settings = Settings(data_dir / "settings.json")
        language = configure_language(settings.data.language)
        if not early.help:
            logger = logging.getLogger(__name__)
            logger.info(
                "UI language: %s (preference=%s; system UI languages=%s)",
                language,
                settings.data.language,
                QLocale.system().uiLanguages(),
            )
            logger.info("Settings: %s; entry point: %s", settings.path, Path(__file__).resolve())
    except Exception as error:
        logging.getLogger(__name__).exception("加载设置失败")
        if gui:
            from PySide6.QtWidgets import QMessageBox

            QMessageBox.critical(
                None, QCoreApplication.translate("Main", "Unable to start Tachie"), render_message(error)
            )
        return 1

    parser = _argument_parser()
    args = parser.parse_args()
    if (args.inspect or args.psd or args.output) and args.project is None:
        parser.error(QCoreApplication.translate("Main", "terminal operations require a project file"))
    if not gui:
        return _headless(args, settings)

    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QMessageBox

    from ui.studio.window import MainWindow

    try:
        window = MainWindow(settings, log_path=log_path)
        if args.manifest:
            settings.set("manifest_path", str(args.manifest.resolve()))
    except Exception as error:
        logging.getLogger(__name__).exception("启动失败")
        QMessageBox.critical(
            None,
            QCoreApplication.translate("Main", "Unable to start Tachie"),
            QCoreApplication.translate("Main", "{0}\n\nLog: {1}").format(render_message(error), log_path),
        )
        return 1
    window.show()
    if args.project:
        QTimer.singleShot(0, lambda: window.open_path(args.project))
    return app.exec()


def _headless(args, settings) -> int:
    from rich.console import Console
    from rich.progress import Progress, SpinnerColumn, TextColumn
    from rich.table import Table

    from application.session import Session
    from domain.imaging import display_layer
    from domain.messages import Message
    from domain.model import Kind
    from ui.i18n import render_message

    console = Console()
    try:
        with Progress(
            SpinnerColumn(), TextColumn("{task.description}", markup=False), console=console, transient=True
        ) as progress:
            task = progress.add_task(QCoreApplication.translate("Main", "Reading project"), total=None)

            def update(message: str | Message, current: int = 0, total: int = 0):
                progress.update(
                    task, description=render_message(message), completed=current, total=total or None
                )

            session = Session.open(
                args.project,
                manifest=args.manifest,
                progress=update,
                defaults=settings.data.model_copy(deep=True),
            )
            if args.psd:
                if args.psd.exists():
                    raise FileExistsError(
                        QCoreApplication.translate(
                            "Main", "Output already exists. Choose a new PSD filename: {0}"
                        ).format(args.psd)
                    )
                session.export_psd(args.psd, update)
                console.print(
                    QCoreApplication.translate("Main", "PSD exported: {0}").format(args.psd), markup=False
                )
            if args.output:
                paths = session.export_unity(args.output, update)
                for path in paths:
                    console.print(str(path), markup=False)
        if args.inspect:
            table = Table(
                title=f"{session.project.name} · {session.project.size[0]} × {session.project.size[1]}"
            )
            for name in (
                QCoreApplication.translate("Main", "Asset"),
                QCoreApplication.translate("Main", "Type"),
                QCoreApplication.translate("Main", "Size"),
                QCoreApplication.translate("Main", "Status"),
            ):
                table.add_column(name)
            for asset in session.project.assets:
                image = asset.image() if asset.kind == Kind.ICON else display_layer(session.project, asset)[0]
                table.add_row(
                    asset.key,
                    asset.kind.value,
                    f"{image.width} × {image.height}",
                    QCoreApplication.translate("Main", "Modified")
                    if asset.modified
                    else QCoreApplication.translate("Main", "Original"),
                )
            console.print(table)
        return 0
    except Exception as error:
        logging.getLogger(__name__).exception("操作失败")
        console.print(render_message(error), markup=False)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
