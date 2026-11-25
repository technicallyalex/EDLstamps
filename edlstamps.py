#!/usr/bin/env python3
"""EDLstamps converts DaVinci Resolve timeline marker EDLs to YouTube chapters."""

from __future__ import annotations

import json
import math
import re
import sys
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import Qt, QTimer, QUrl
from PySide6.QtGui import (
    QActionGroup, QColor, QDesktopServices, QFontDatabase, QIcon, QKeySequence, QPalette,
)
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QFileDialog, QHBoxLayout, QLabel, QLineEdit,
    QMainWindow, QMessageBox, QPlainTextEdit, QPushButton, QSplitter,
    QVBoxLayout, QWidget,
)

MODERN_MARKER_RE = re.compile(
    r"\|C:(?P<color>[^|]*)"
    r"\s+\|M:(?P<name>[^|]*)"
    r"\s+\|D:(?P<comment>.*)$"
)
LEGACY_MARKER_RE = re.compile(r"\*?\s*MARKER:\s*(?P<value>.*)$", re.IGNORECASE)
TIMECODE_RE = re.compile(r"\d{2}:\d{2}:\d{2}:\d{2}")
APP_VERSION = "1.1.0"
GITHUB_REPO = "technicallyalex/resolve-edl-to-youtube"
RELEASE_API = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"


def release_version(tag: str) -> tuple[int, ...]:
    match = re.fullmatch(r"v?(\d+)\.(\d+)\.(\d+)", tag, flags=re.ASCII)
    if match is None:
        raise ValueError("Unexpected release tag")
    return tuple(int(part) for part in match.groups())


@dataclass
class Marker:
    start_frames: int
    color: str
    name: str
    comment: str

    def label(self, use_comments: bool) -> str:
        raw = self.comment if use_comments else self.name
        cleaned = " ".join(raw.split())
        return cleaned or "Chapter"


def timecode_to_frames(timecode: str, fps: float) -> int:
    hours, minutes, seconds, frames = (int(part) for part in timecode.split(":"))
    total_seconds = (hours * 3600) + (minutes * 60) + seconds
    return int(round(total_seconds * fps + frames))


def frames_to_youtube_timestamp(frame_count: int, fps: float) -> str:
    total_seconds = int(frame_count / fps)
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60
    if hours:
        return f"{hours}:{minutes:02d}:{seconds:02d}"
    return f"{minutes}:{seconds:02d}"


def parse_legacy_marker(text: str) -> tuple[str, str, str]:
    parts = [part.strip() for part in text.split("|")]
    name = parts[0] if parts else ""
    color = parts[1] if len(parts) > 1 else ""
    comment = parts[2] if len(parts) > 2 else ""
    return color, name, comment


def extract_markers(edl_text: str, fps: float) -> list[Marker]:
    markers: list[Marker] = []
    pending_start_frames: int | None = None

    for raw_line in edl_text.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        timecodes = TIMECODE_RE.findall(line)
        if len(timecodes) >= 4:
            pending_start_frames = timecode_to_frames(timecodes[2], fps)
            continue

        modern_match = MODERN_MARKER_RE.search(line)
        if modern_match and pending_start_frames is not None:
            markers.append(
                Marker(
                    start_frames=pending_start_frames,
                    color=modern_match.group("color").strip(),
                    name=modern_match.group("name").strip(),
                    comment=modern_match.group("comment").strip(),
                )
            )
            pending_start_frames = None
            continue

        legacy_match = LEGACY_MARKER_RE.match(line)
        if legacy_match and pending_start_frames is not None:
            color, name, comment = parse_legacy_marker(legacy_match.group("value"))
            markers.append(
                Marker(
                    start_frames=pending_start_frames,
                    color=color,
                    name=name,
                    comment=comment,
                )
            )
            pending_start_frames = None

    return markers


def build_chapters(
    markers: list[Marker],
    fps: float,
    use_comments: bool,
    prepend_zero_title: str,
    dedupe: bool,
) -> list[str]:
    lines: list[str] = []
    sorted_markers = sorted(markers, key=lambda item: item.start_frames)

    if prepend_zero_title.strip() and sorted_markers and sorted_markers[0].start_frames > 0:
        lines.append(f"0:00 {prepend_zero_title.strip()}")

    for marker in sorted_markers:
        lines.append(
            f"{frames_to_youtube_timestamp(marker.start_frames, fps)} {marker.label(use_comments)}"
        )

    if not dedupe:
        return lines

    deduped: list[str] = []
    for line in lines:
        if not deduped or deduped[-1] != line:
            deduped.append(line)
    return deduped


class ResolveEdlApp(QMainWindow):
    def __init__(self, initial_path: str = "") -> None:
        super().__init__()
        self.setWindowTitle("EDLstamps")
        self._network = QNetworkAccessManager(self)
        self.resize(1050, 720)
        self._loaded_path: Path | None = None
        self._path_timer = QTimer(self, singleShot=True, interval=200)
        self._path_timer.timeout.connect(self._load_typed_path)
        self._generate_timer = QTimer(self, singleShot=True, interval=150)
        self._generate_timer.timeout.connect(self.generate_chapters)
        self._build_ui()
        self._build_menu()
        if initial_path:
            self.load_file(initial_path, report_errors=True)

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(18, 14, 18, 14)
        layout.setSpacing(10)

        file_row = QHBoxLayout()
        layout.addLayout(file_row)
        self.path_entry = QLineEdit()
        self.path_entry.setPlaceholderText("Path to a marker EDL")
        path_label = QLabel("EDL &file")
        path_label.setBuddy(self.path_entry)
        file_row.addWidget(path_label)
        file_row.addWidget(self.path_entry, 1)
        browse = QPushButton("&Browse...")
        browse.clicked.connect(self.open_file)
        file_row.addWidget(browse)
        load = QPushButton("Load File")
        load.clicked.connect(self._load_path_explicitly)
        file_row.addWidget(load)
        self.path_entry.textEdited.connect(lambda _: self._path_timer.start())
        self.path_entry.returnPressed.connect(self._load_path_explicitly)

        settings = QHBoxLayout()
        layout.addLayout(settings)
        self.fps = QLineEdit("24")
        self.fps.setMaximumWidth(76)
        fps_label = QLabel("&FPS")
        fps_label.setBuddy(self.fps)
        settings.addWidget(fps_label)
        settings.addWidget(self.fps)
        self.use_comments = QCheckBox("Use marker comments")
        settings.addWidget(self.use_comments)
        self.dedupe = QCheckBox("Dedupe consecutive lines")
        self.dedupe.setChecked(True)
        settings.addWidget(self.dedupe)
        settings.addStretch()

        panes = QSplitter(Qt.Orientation.Vertical)
        panes.setChildrenCollapsible(False)
        layout.addWidget(panes, 1)
        self.input_text = self._add_editor(panes, "EDL &Input")
        self.output_text = self._add_editor(panes, "&YouTube Chapters")
        panes.setSizes([330, 270])

        actions = QHBoxLayout()
        layout.addLayout(actions)
        self.prepend_zero = QCheckBox("Prepend 0:00 chapter")
        self.prepend_zero.setChecked(True)
        actions.addWidget(self.prepend_zero)
        self.intro_title = QLineEdit("Intro")
        self.intro_title.setAccessibleName("Intro chapter title")
        self.intro_title.setMaximumWidth(140)
        actions.addWidget(self.intro_title)
        generate = QPushButton("&Generate Chapters")
        generate.clicked.connect(self.generate_chapters)
        actions.addWidget(generate)
        actions.addStretch()
        self.copy_button = QPushButton("&Copy to Clipboard")
        self.copy_button.clicked.connect(self.copy_output)
        actions.addWidget(self.copy_button)
        self.save_button = QPushButton("Save as Text File...")
        self.save_button.clicked.connect(self.save_output)
        actions.addWidget(self.save_button)

        self.status = QLabel()
        self.status.setTextFormat(Qt.TextFormat.PlainText)
        self.status.setWordWrap(True)
        self.status.hide()
        layout.addWidget(self.status)

        self.prepend_zero.toggled.connect(self.intro_title.setEnabled)
        for field in (self.fps, self.intro_title):
            field.textChanged.connect(lambda _: self._generate_timer.start())
        for checkbox in (self.use_comments, self.dedupe, self.prepend_zero):
            checkbox.toggled.connect(lambda _: self._generate_timer.start())
        self.input_text.textChanged.connect(self._generate_timer.start)
        self.output_text.textChanged.connect(self._sync_export_buttons)
        self._sync_export_buttons()

    @staticmethod
    def _add_editor(panes: QSplitter, title: str) -> QPlainTextEdit:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        label = QLabel(title)
        editor = QPlainTextEdit()
        editor.setFont(QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont))
        editor.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        editor.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        editor.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        label.setBuddy(editor)
        layout.addWidget(label)
        layout.addWidget(editor)
        panes.addWidget(panel)
        return editor

    def _build_menu(self) -> None:
        file_menu = self.menuBar().addMenu("&File")
        open_action = file_menu.addAction("&Open EDL...", self.open_file)
        open_action.setShortcut(QKeySequence.StandardKey.Open)
        view = self.menuBar().addMenu("&View")
        modes = QActionGroup(self)
        modes.setExclusive(True)
        for title, scheme in (
            ("Dark", Qt.ColorScheme.Dark),
            ("Light", Qt.ColorScheme.Light),
            ("System", Qt.ColorScheme.Unknown),
        ):
            action = view.addAction(title)
            action.setCheckable(True)
            modes.addAction(action)
            action.triggered.connect(
                lambda checked, mode=scheme: self._set_theme(mode) if checked else None
            )
            if scheme == Qt.ColorScheme.Light:
                action.setChecked(True)
                self._set_theme(scheme)

        help_menu = self.menuBar().addMenu("&Help")
        self.update_action = help_menu.addAction("Check for &Updates...", self.check_for_updates)
        help_menu.addAction("About EDLstamps", self.show_about)

    def show_about(self) -> None:
        QMessageBox.about(
            self, "About EDLstamps", f"EDLstamps {APP_VERSION}\nDaVinci Resolve markers to YouTube chapters."
        )

    def check_for_updates(self) -> None:
        self.update_action.setEnabled(False)
        self._set_status("Checking GitHub for updates...")
        request = QNetworkRequest(QUrl(RELEASE_API))
        request.setRawHeader(b"Accept", b"application/vnd.github+json")
        request.setRawHeader(b"User-Agent", f"EDLstamps/{APP_VERSION}".encode("ascii"))
        request.setAttribute(
            QNetworkRequest.Attribute.RedirectPolicyAttribute,
            QNetworkRequest.RedirectPolicy.SameOriginRedirectPolicy,
        )
        request.setTransferTimeout(10_000)
        reply = self._network.get(request)
        reply.finished.connect(lambda: self._update_check_finished(reply))

    def _update_check_finished(self, reply: QNetworkReply) -> None:
        self.update_action.setEnabled(True)
        self._set_status("")
        try:
            if reply.error() != QNetworkReply.NetworkError.NoError:
                raise ValueError(reply.errorString())
            release = json.loads(bytes(reply.readAll()))
            if not isinstance(release, dict) or not isinstance(release.get("tag_name"), str):
                raise ValueError("GitHub did not return a release version.")
            version = release_version(release["tag_name"])
        except ValueError as error:
            QMessageBox.warning(self, "Update check failed", f"Could not check GitHub for updates.\n\n{error}")
            return
        finally:
            reply.deleteLater()

        if version <= release_version(APP_VERSION):
            QMessageBox.information(self, "No update found", f"EDLstamps {APP_VERSION} is up to date.")
            return

        tag = release["tag_name"]
        choice = QMessageBox.question(
            self,
            "Update available",
            f"EDLstamps {tag} is available. Open the GitHub release page?",
        )
        if choice == QMessageBox.StandardButton.Yes:
            release_url = QUrl(f"https://github.com/{GITHUB_REPO}/releases/tag/{tag}")
            if not QDesktopServices.openUrl(release_url):
                QMessageBox.warning(self, "Could not open browser", release_url.toString())

    @staticmethod
    def _set_theme(scheme: Qt.ColorScheme) -> None:
        app = QApplication.instance()
        app.styleHints().setColorScheme(scheme)
        if scheme == Qt.ColorScheme.Unknown:
            app.setPalette(QPalette())
            return
        dark = scheme == Qt.ColorScheme.Dark
        palette = QPalette()
        for role, light_color, dark_color in (
            (QPalette.ColorRole.Window, "#eef2f6", "#1d2229"),
            (QPalette.ColorRole.Base, "#ffffff", "#20252d"),
            (QPalette.ColorRole.Button, "#f7f9fb", "#2a313a"),
            (QPalette.ColorRole.WindowText, "#1b2430", "#e6ebf2"),
            (QPalette.ColorRole.Text, "#1b2430", "#e6ebf2"),
            (QPalette.ColorRole.ButtonText, "#1b2430", "#e6ebf2"),
            (QPalette.ColorRole.Highlight, "#3158a5", "#344e74"),
            (QPalette.ColorRole.HighlightedText, "#ffffff", "#ffffff"),
        ):
            palette.setColor(role, QColor(dark_color if dark else light_color))
        for role in (QPalette.ColorRole.WindowText, QPalette.ColorRole.Text, QPalette.ColorRole.ButtonText):
            palette.setColor(QPalette.ColorGroup.Disabled, role, QColor("#8490a0" if dark else "#687486"))
        app.setPalette(palette)

    def open_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Resolve Marker EDL", self.path_entry.text(),
            "EDL files (*.edl);;Text files (*.txt);;All files (*)",
        )
        if path:
            self.load_file(path, report_errors=True)

    def _load_path_explicitly(self) -> None:
        if self.path_entry.text().strip():
            self.load_file(self.path_entry.text(), report_errors=True)
        else:
            self.open_file()

    def _load_typed_path(self) -> None:
        self.load_file(self.path_entry.text())

    def load_file(self, path_text: str, *, report_errors: bool = False) -> None:
        self._path_timer.stop()
        path_text = path_text.strip().strip('"')
        if not path_text:
            return
        path = Path(path_text)
        if not report_errors and path == self._loaded_path:
            return
        try:
            content = path.read_text(encoding="utf-8-sig")
        except (OSError, UnicodeError, ValueError) as error:
            if report_errors:
                self._set_status(f"Could not read {path.name}: {error}")
            return
        self._loaded_path = path
        self.path_entry.setText(str(path))
        self.input_text.setPlainText(content)
        self.generate_chapters()

    def generate_chapters(self) -> None:
        self._generate_timer.stop()
        edl = self.input_text.toPlainText().strip()
        lines: list[str] = []
        status = ""
        if edl:
            try:
                fps = float(self.fps.text())
                if not math.isfinite(fps) or fps <= 0:
                    raise ValueError
                markers = extract_markers(edl, fps)
            except (ValueError, OverflowError):
                status = "Enter a valid positive frame rate."
            else:
                if markers:
                    intro = self.intro_title.text() if self.prepend_zero.isChecked() else ""
                    lines = build_chapters(
                        markers, fps, self.use_comments.isChecked(), intro, self.dedupe.isChecked()
                    )
                    status = f"Generated {len(lines)} chapter lines from {len(markers)} markers."
                else:
                    status = "No Resolve markers were found in the current EDL input."
        self.output_text.setPlainText("\n".join(lines))
        self._set_status(status)

    def _set_status(self, text: str) -> None:
        self.status.setText(text)
        self.status.setVisible(bool(text))

    def _sync_export_buttons(self) -> None:
        has_output = not self.output_text.document().isEmpty()
        self.copy_button.setEnabled(has_output)
        self.save_button.setEnabled(has_output)

    def copy_output(self) -> None:
        QApplication.clipboard().setText(self.output_text.toPlainText().strip())
        self._set_status("Copied chapter lines to clipboard.")

    def save_output(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "Save YouTube Chapters", "chapters.txt", "Text files (*.txt);;All files (*)"
        )
        if not path:
            return
        try:
            Path(path).write_text(self.output_text.toPlainText().strip() + "\n", encoding="utf-8")
        except OSError as error:
            QMessageBox.critical(self, "Save Failed", str(error))
        else:
            self._set_status(f"Saved chapter lines to {path}")


def main() -> None:
    app = QApplication([sys.argv[0]])
    app.setApplicationName("EDLstamps")
    app.setApplicationVersion(APP_VERSION)
    app.setWindowIcon(QIcon(str(Path(__file__).resolve().parent / "assets" / "app-logo.png")))
    app.setStyle("Fusion")
    window = ResolveEdlApp(sys.argv[1] if len(sys.argv) > 1 else "")
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
