import sys
import serial
from PySide6.QtCore import Qt, QTimer, QThread, Signal
from PySide6.QtWidgets import (
    QApplication,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
    QMessageBox,
)


def load_config():
    cfg = {"PORT": "COM1", "BAUD": "9600"}

    with open("config.txt") as f:
        for line in f:
            line = line.strip()
            if "=" in line:
                k, v = line.split("=", 1)
                cfg[k.strip()] = v.strip()

    return cfg["PORT"], int(cfg["BAUD"])


class SerialReader(QThread):
    status_received = Signal(str)
    error = Signal(str)

    def __init__(self, ser):
        super().__init__()
        self.ser = ser
        self.running = True

    def run(self):
        while self.running:
            try:
                line = self.ser.readline().decode(errors="ignore").strip()
                if line:
                    self.status_received.emit(line)
            except Exception as e:
                self.error.emit(str(e))
                break

    def stop(self):
        self.running = False
        self.wait()


class MainWindow(QWidget):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Control PH")

        port, baud = load_config()

        try:
            self.ser = serial.Serial(port, baud, timeout=1)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"No se pudo abrir {port}\n\n{e}")
            sys.exit()

        self.status_label = QLabel("SIN DATOS")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setStyleSheet("""
            font-size:32px;
            font-weight:bold;
            border:2px solid gray;
            padding:20px;
        """)

        self.btn1 = QPushButton("ÁCIDO")
        self.btn2 = QPushButton("BASE")
        self.btn3 = QPushButton("APAGAR")

        self.btn1.clicked.connect(lambda: self.send_command("ACIDO"))
        self.btn2.clicked.connect(lambda: self.send_command("BASE"))
        self.btn3.clicked.connect(lambda: self.send_command("APAGAR"))

        layout = QVBoxLayout(self)
        layout.addWidget(self.status_label)
        layout.addWidget(self.btn1)
        layout.addWidget(self.btn2)
        layout.addWidget(self.btn3)

        self.reader = SerialReader(self.ser)
        self.reader.status_received.connect(self.update_status)
        self.reader.error.connect(self.serial_error)
        self.reader.start()

        self.timer = QTimer()
        self.timer.timeout.connect(lambda: self.send_command("GET"))
        self.timer.start(2000)

        self.send_command("GET")

    def send_command(self, cmd):
        try:
            self.ser.write((cmd + "\r\n").encode())
        except Exception as e:
            self.serial_error(str(e))

    def update_status(self, text):
        self.status_label.setText(text)

    def serial_error(self, msg):
        self.status_label.setText("ERROR")
        QMessageBox.warning(self, "Puerto serie", msg)

    def closeEvent(self, event):
        self.reader.stop()
        self.ser.close()
        event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = MainWindow()
    w.resize(420, 300)
    w.show()
    sys.exit(app.exec())