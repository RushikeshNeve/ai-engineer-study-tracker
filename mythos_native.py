from __future__ import annotations

import math
import os
import random
import sys
import webbrowser
from dataclasses import dataclass
from datetime import datetime


try:
    from PyQt6.QtCore import QEasingCurve, QPointF, QPropertyAnimation, QRect, Qt, QTimer, pyqtProperty
    from PyQt6.QtGui import QColor, QFont, QLinearGradient, QPainter, QPainterPath, QPen, QRadialGradient
    from PyQt6.QtWidgets import QApplication, QFrame, QGraphicsDropShadowEffect, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget
except Exception as exc:  # pragma: no cover - dependency guard for optional desktop UI
    print("Project Mythos native UI requires PyQt6.")
    print("Install it with: pip install PyQt6")
    print(f"Details: {exc}")
    raise SystemExit(1)


ACCENT = QColor("#00D4FF")
PURPLE = QColor("#8B5CF6")
MATTE_BLACK = QColor("#090909")
GLASS = "rgba(16, 24, 39, 0.48)"


def mythos_url() -> str:
    host = os.getenv("MYTHOS_HOST", "localhost").strip() or "localhost"
    port = os.getenv("MYTHOS_PORT", "8501").strip() or "8501"
    return f"http://{host}:{port}"


@dataclass
class Particle:
    x: float
    y: float
    radius: float
    speed: float
    drift: float
    alpha: int


def shadow(color: QColor, blur: int = 32, offset: int = 0) -> QGraphicsDropShadowEffect:
    effect = QGraphicsDropShadowEffect()
    effect.setBlurRadius(blur)
    effect.setColor(color)
    effect.setOffset(0, offset)
    return effect


class GlassPanel(QFrame):
    def __init__(self, title: str, lines: list[str], parent=None):
        super().__init__(parent)
        self.setObjectName("glassPanel")
        self.setGraphicsEffect(shadow(QColor(0, 212, 255, 60), 28))
        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 20, 22, 20)
        layout.setSpacing(12)

        title_label = QLabel(title)
        title_label.setObjectName("panelTitle")
        layout.addWidget(title_label)

        for line in lines:
            label = QLabel(line)
            label.setObjectName("panelLine")
            label.setWordWrap(True)
            layout.addWidget(label)
        layout.addStretch()


class CommandChip(QPushButton):
    def __init__(self, text: str, parent=None):
        super().__init__(text, parent)
        self.setObjectName("commandChip")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setGraphicsEffect(shadow(QColor(0, 212, 255, 70), 20))


class MessageBubble(QFrame):
    def __init__(self, text: str, speaker: str, parent=None):
        super().__init__(parent)
        self.setObjectName("mythosBubble" if speaker == "mythos" else "userBubble")
        self.setGraphicsEffect(shadow(QColor(0, 212, 255, 55) if speaker == "mythos" else QColor(139, 92, 246, 40), 22))
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 14, 18, 14)
        caption = QLabel("MYTHOS" if speaker == "mythos" else "RUSHIKESH")
        caption.setObjectName("bubbleCaption")
        message = QLabel(text)
        message.setObjectName("bubbleText")
        message.setWordWrap(True)
        layout.addWidget(caption)
        layout.addWidget(message)


class AICore(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._phase = 0.0
        self.state = "Online"
        self.setMinimumSize(360, 360)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.tick)
        self.timer.start(16)

    def tick(self) -> None:
        self._phase = (self._phase + 0.018) % (math.pi * 2)
        self.update()

    def set_state(self, state: str) -> None:
        self.state = state
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect()
        center = QPointF(rect.width() / 2, rect.height() / 2)
        base = min(rect.width(), rect.height()) * 0.31
        pulse = 1 + math.sin(self._phase) * 0.045

        for index in range(4):
            radius = base * pulse + index * 28
            alpha = max(18, 92 - index * 20)
            pen_color = QColor(ACCENT)
            pen_color.setAlpha(alpha)
            pen = QPen(pen_color, 2)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(center, radius, radius)

        ring_angle = self._phase * (1.6 if self.state == "Thinking" else 0.7)
        for index, color in enumerate([ACCENT, PURPLE]):
            pen = QPen(color, 4 - index)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            painter.setPen(pen)
            start = int((ring_angle + index * math.pi) * 16 * 180 / math.pi)
            painter.drawArc(
                QRect(int(center.x() - base - 22 - index * 18), int(center.y() - base - 22 - index * 18), int((base + 22 + index * 18) * 2), int((base + 22 + index * 18) * 2)),
                start,
                110 * 16,
            )

        gradient = QRadialGradient(center, base * 1.2)
        gradient.setColorAt(0.0, QColor(255, 255, 255, 220))
        gradient.setColorAt(0.22, QColor(0, 212, 255, 190))
        gradient.setColorAt(0.58, QColor(139, 92, 246, 120))
        gradient.setColorAt(1.0, QColor(0, 0, 0, 0))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(gradient)
        painter.drawEllipse(center, base * 0.96, base * 0.96)

        if self.state == "Speaking":
            painter.setPen(QPen(QColor(0, 212, 255, 180), 3))
            for index in range(18):
                x = center.x() - 120 + index * 14
                height = 12 + abs(math.sin(self._phase * 3 + index * 0.7)) * 40
                painter.drawLine(QPointF(x, center.y() + 120 - height / 2), QPointF(x, center.y() + 120 + height / 2))


class Background(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.particles = [
            Particle(random.uniform(0, 1600), random.uniform(0, 1000), random.uniform(0.8, 2.2), random.uniform(0.15, 0.55), random.uniform(-0.18, 0.18), random.randint(35, 120))
            for _ in range(90)
        ]
        self.phase = 0.0
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.tick)
        self.timer.start(33)

    def tick(self) -> None:
        self.phase += 0.008
        for particle in self.particles:
            particle.y -= particle.speed
            particle.x += particle.drift
            if particle.y < -8:
                particle.y = self.height() + 8
                particle.x = random.uniform(0, max(1, self.width()))
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), MATTE_BLACK)

        grid_color = QColor(0, 212, 255, 18)
        painter.setPen(QPen(grid_color, 1))
        grid = 48
        for x in range(0, self.width(), grid):
            painter.drawLine(x, 0, x, self.height())
        for y in range(0, self.height(), grid):
            painter.drawLine(0, y, self.width(), y)

        glow = QRadialGradient(QPointF(self.width() * 0.5, self.height() * 0.46), self.width() * 0.52)
        glow.setColorAt(0.0, QColor(0, 212, 255, 32))
        glow.setColorAt(0.45, QColor(139, 92, 246, 20))
        glow.setColorAt(1.0, QColor(9, 9, 9, 0))
        painter.setBrush(glow)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRect(self.rect())

        for particle in self.particles:
            color = QColor(0, 212, 255, particle.alpha)
            painter.setBrush(color)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(QPointF(particle.x, particle.y), particle.radius, particle.radius)


class MythosWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Project Mythos")
        self.resize(1440, 900)
        self.setMinimumSize(1180, 760)
        self.status = "Online"
        self.background = Background(self)
        self.build_ui()
        self.apply_styles()
        self.clock = QTimer(self)
        self.clock.timeout.connect(self.update_time)
        self.clock.start(1000)
        self.update_time()

    def resizeEvent(self, event) -> None:
        self.background.setGeometry(self.rect())
        super().resizeEvent(event)

    def build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(34, 24, 34, 28)
        root.setSpacing(18)

        header = QHBoxLayout()
        logo = QLabel("PROJECT MYTHOS")
        logo.setObjectName("logo")
        self.date_time = QLabel("")
        self.date_time.setObjectName("dateTime")
        self.status_label = QLabel("* Online")
        self.status_label.setObjectName("statusOnline")
        header.addWidget(logo)
        header.addStretch()
        header.addWidget(self.date_time)
        header.addSpacing(22)
        header.addWidget(self.status_label)
        root.addLayout(header)

        main = QHBoxLayout()
        main.setSpacing(28)
        self.left_panel = GlassPanel("Today's Focus", ["AI Cohort deep work", "Redis Streams revision", "Two graph problems", "Project polish: voice shell"])
        self.left_panel.setFixedWidth(280)
        main.addWidget(self.left_panel)

        center = QVBoxLayout()
        center.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.core = AICore()
        center.addWidget(self.core, alignment=Qt.AlignmentFlag.AlignCenter)
        greeting = QLabel("Good Morning, Rushikesh.")
        greeting.setObjectName("greeting")
        sub = QLabel("How may I assist you today?")
        sub.setObjectName("subGreeting")
        center.addWidget(greeting, alignment=Qt.AlignmentFlag.AlignCenter)
        center.addWidget(sub, alignment=Qt.AlignmentFlag.AlignCenter)

        chips = QHBoxLayout()
        chips.setSpacing(10)
        for text in ["What should I study today?", "Analyze my workout", "Analyze my diet", "Weekly review", "My progress", "Open projects"]:
            chip = CommandChip(text)
            chip.clicked.connect(lambda checked=False, label=text: self.add_user_message(label))
            chips.addWidget(chip)
        center.addLayout(chips)

        conversation = QVBoxLayout()
        conversation.setSpacing(14)
        row1 = QHBoxLayout()
        row1.addWidget(MessageBubble("Mythos is online. Systems are calm, focused, and ready.", "mythos"))
        row1.addStretch()
        row2 = QHBoxLayout()
        row2.addStretch()
        row2.addWidget(MessageBubble("What should I focus on next?", "user"))
        conversation.addLayout(row1)
        conversation.addLayout(row2)
        center.addLayout(conversation)

        mic = QPushButton("VOICE")
        mic.setObjectName("micButton")
        mic.setCursor(Qt.CursorShape.PointingHandCursor)
        mic.setFixedSize(96, 96)
        mic.setGraphicsEffect(shadow(QColor(0, 212, 255, 150), 45))
        mic.clicked.connect(self.open_voice_mode)
        center.addWidget(mic, alignment=Qt.AlignmentFlag.AlignCenter)
        voice_note = QLabel("Live microphone and audio playback run in the Mythos AI Command Center.")
        voice_note.setObjectName("voiceNote")
        voice_note.setWordWrap(True)
        center.addWidget(voice_note, alignment=Qt.AlignmentFlag.AlignCenter)
        main.addLayout(center, stretch=1)

        self.right_panel = GlassPanel("Health Overview", ["Weight: 96.8 kg", "Protein target: 130-150 g", "Steps: 10k target", "Workout: Push / Pull / Legs"])
        self.right_panel.setFixedWidth(280)
        main.addWidget(self.right_panel)
        root.addLayout(main, stretch=1)

    def add_user_message(self, text: str) -> None:
        self.set_status("Thinking")
        QTimer.singleShot(900, lambda: self.set_status("Speaking"))
        QTimer.singleShot(2200, lambda: self.set_status("Online"))

    def cycle_status(self) -> None:
        states = ["Listening", "Thinking", "Speaking", "Online"]
        current_index = states.index(self.status) if self.status in states else 3
        self.set_status(states[(current_index + 1) % len(states)])

    def open_voice_mode(self) -> None:
        self.set_status("Listening")
        webbrowser.open(mythos_url())
        QTimer.singleShot(1600, lambda: self.set_status("Online"))

    def set_status(self, status: str) -> None:
        self.status = status
        self.core.set_state(status)
        self.status_label.setText(f"* {status}")
        self.status_label.setObjectName(f"status{status}")
        self.status_label.style().unpolish(self.status_label)
        self.status_label.style().polish(self.status_label)

    def update_time(self) -> None:
        now = datetime.now()
        self.date_time.setText(now.strftime("%I:%M %p   |   %A, %d %B"))

    def apply_styles(self) -> None:
        self.setStyleSheet(
            f"""
            QWidget {{
                color: #E5F7FF;
                font-family: Segoe UI, Inter, Arial;
                background: transparent;
            }}
            #logo {{
                font-size: 23px;
                font-weight: 800;
                letter-spacing: 3px;
                color: #F8FCFF;
            }}
            #dateTime {{
                color: rgba(229, 247, 255, 0.72);
                font-size: 14px;
            }}
            #statusOnline, #statusListening, #statusThinking, #statusSpeaking {{
                padding: 9px 14px;
                border-radius: 15px;
                border: 1px solid rgba(0, 212, 255, 0.34);
                background: rgba(0, 212, 255, 0.08);
                color: #00D4FF;
                font-weight: 700;
            }}
            #statusListening {{ color: #34D399; border-color: rgba(52, 211, 153, 0.5); }}
            #statusThinking {{ color: #8B5CF6; border-color: rgba(139, 92, 246, 0.55); }}
            #statusSpeaking {{ color: #F8FCFF; border-color: rgba(0, 212, 255, 0.72); }}
            #glassPanel {{
                background: {GLASS};
                border: 1px solid rgba(0, 212, 255, 0.18);
                border-radius: 24px;
            }}
            #panelTitle {{
                color: #FFFFFF;
                font-size: 18px;
                font-weight: 800;
            }}
            #panelLine {{
                color: rgba(229, 247, 255, 0.74);
                font-size: 14px;
                line-height: 1.35;
            }}
            #greeting {{
                font-size: 38px;
                font-weight: 800;
                color: #FFFFFF;
                margin-top: 4px;
            }}
            #subGreeting {{
                font-size: 18px;
                color: rgba(229, 247, 255, 0.70);
                margin-bottom: 14px;
            }}
            #voiceNote {{
                color: rgba(229, 247, 255, 0.56);
                font-size: 12px;
                max-width: 420px;
                margin-top: 4px;
            }}
            #commandChip {{
                padding: 10px 16px;
                border-radius: 18px;
                border: 1px solid rgba(0, 212, 255, 0.25);
                background: rgba(12, 20, 31, 0.62);
                color: rgba(229, 247, 255, 0.88);
                font-weight: 650;
            }}
            #commandChip:hover {{
                background: rgba(0, 212, 255, 0.14);
                border-color: rgba(0, 212, 255, 0.72);
            }}
            #micButton {{
                border-radius: 48px;
                border: 1px solid rgba(0, 212, 255, 0.65);
                background: qradialgradient(cx:0.5, cy:0.45, radius:0.8, stop:0 rgba(0,212,255,0.45), stop:0.65 rgba(12,20,31,0.9), stop:1 rgba(139,92,246,0.25));
                color: #FFFFFF;
                font-weight: 900;
                letter-spacing: 2px;
            }}
            #micButton:hover {{
                border-color: #FFFFFF;
                background: rgba(0, 212, 255, 0.22);
            }}
            #mythosBubble, #userBubble {{
                border-radius: 20px;
                max-width: 440px;
            }}
            #mythosBubble {{
                background: rgba(9, 18, 30, 0.64);
                border: 1px solid rgba(0, 212, 255, 0.38);
            }}
            #userBubble {{
                background: rgba(20, 16, 35, 0.62);
                border: 1px solid rgba(139, 92, 246, 0.34);
            }}
            #bubbleCaption {{
                font-size: 11px;
                letter-spacing: 2px;
                color: rgba(0, 212, 255, 0.85);
                font-weight: 800;
            }}
            #bubbleText {{
                font-size: 14px;
                color: rgba(248, 252, 255, 0.90);
            }}
            """
        )


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("Project Mythos")
    window = MythosWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
