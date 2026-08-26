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


# =============================================================
# CONFIGURACIÓN
# =============================================================

GET_INTERVAL = 2000       # GET cada 2 segundos
RECONNECT_INTERVAL = 2000 # Reintento de conexión cada 2 segundos


# =============================================================
# CONFIG.TXT
# =============================================================

def load_config():

    cfg = {
        "PORT": "COM1",
        "BAUD": "9600"
    }

    with open("config.txt") as f:

        for line in f:

            line = line.strip()

            if "=" in line:

                k, v = line.split("=", 1)

                cfg[k.strip()] = v.strip()

    return cfg["PORT"], int(cfg["BAUD"])


# =============================================================
# LECTOR SERIE
# =============================================================

class SerialReader(QThread):

    status_received = Signal(str)
    connection_lost = Signal()

    def __init__(self, ser):

        super().__init__()

        self.ser = ser
        self.running = True

    def run(self):

        while self.running:

            try:

                line = self.ser.readline()

                if line:

                    text = line.decode(
                        errors="ignore"
                    ).strip()

                    if text:

                        self.status_received.emit(
                            text
                        )

            except (
                serial.SerialException,
                OSError
            ):

                if self.running:
                    self.connection_lost.emit()

                break

            except Exception:

                if self.running:
                    self.connection_lost.emit()

                break

    def stop(self):

        self.running = False

        if self.isRunning():

            self.wait(1500)


# =============================================================
# VENTANA PRINCIPAL
# =============================================================

class MainWindow(QWidget):

    def __init__(self):

        super().__init__()

        self.setWindowTitle("Control PH")

        # -----------------------------------------------------
        # CONFIGURACIÓN
        # -----------------------------------------------------

        self.port, self.baud = load_config()

        self.ser = None
        self.reader = None

        self.connected = False
        self.closing = False

        # -----------------------------------------------------
        # ESTADO
        # -----------------------------------------------------

        self.status_label = QLabel(
            "DESCONECTADO"
        )

        self.status_label.setAlignment(
            Qt.AlignCenter
        )

        self.status_label.setStyleSheet("""
            font-size:32px;
            font-weight:bold;
            border:2px solid gray;
            padding:20px;
        """)

        # -----------------------------------------------------
        # BOTONES
        # -----------------------------------------------------

        self.btn1 = QPushButton("ÁCIDO")
        self.btn2 = QPushButton("BASE")
        self.btn3 = QPushButton("APAGAR")

        self.btn1.clicked.connect(
            lambda: self.send_command("ACIDO")
        )

        self.btn2.clicked.connect(
            lambda: self.send_command("BASE")
        )

        self.btn3.clicked.connect(
            lambda: self.send_command("APAGAR")
        )

        # -----------------------------------------------------
        # LAYOUT
        # -----------------------------------------------------

        layout = QVBoxLayout(self)

        layout.addWidget(
            self.status_label
        )

        layout.addWidget(
            self.btn1
        )

        layout.addWidget(
            self.btn2
        )

        layout.addWidget(
            self.btn3
        )

        # Inicialmente deshabilitados
        self.set_buttons_enabled(False)

        # -----------------------------------------------------
        # TIMER GET
        # -----------------------------------------------------

        self.get_timer = QTimer(self)

        self.get_timer.timeout.connect(
            self.send_get
        )

        # -----------------------------------------------------
        # TIMER RECONEXIÓN
        # -----------------------------------------------------

        self.reconnect_timer = QTimer(self)

        self.reconnect_timer.timeout.connect(
            self.try_reconnect
        )

        # -----------------------------------------------------
        # PRIMERA CONEXIÓN
        # -----------------------------------------------------

        self.try_connect()

        # -----------------------------------------------------
        # CIERRE
        # -----------------------------------------------------

        self.setAttribute(
            Qt.WA_DeleteOnClose
        )

    # =========================================================
    # CONECTAR
    # =========================================================

    def try_connect(self):

        if self.closing:
            return

        # Si por alguna razón ya estamos conectados,
        # no hacer nada.
        if self.connected:
            return

        try:

            print(
                f"Intentando conectar a {self.port}..."
            )

            self.ser = serial.Serial(
                self.port,
                self.baud,
                timeout=1
            )

            self.connected = True

            self.status_label.setText(
                "CONECTADO - ESPERANDO ESTADO"
            )

            self.set_buttons_enabled(
                True
            )

            # Detener timer de reconexión
            self.reconnect_timer.stop()

            # -------------------------------------------------
            # Crear lector para esta conexión
            # -------------------------------------------------

            self.reader = SerialReader(
                self.ser
            )

            self.reader.status_received.connect(
                self.update_status
            )

            self.reader.connection_lost.connect(
                self.connection_lost
            )

            self.reader.start()

            # -------------------------------------------------
            # Iniciar GET periódico
            # -------------------------------------------------

            self.get_timer.start(
                GET_INTERVAL
            )

            # GET inmediato al conectar
            self.send_get()

            print(
                f"Conectado a {self.port}"
            )

        except (
            serial.SerialException,
            OSError
        ) as e:

            print(
                f"No se pudo conectar a "
                f"{self.port}: {e}"
            )

            self.ser = None
            self.connected = False

            self.set_buttons_enabled(
                False
            )

            self.status_label.setText(
                f"DESCONECTADO - "
                f"REINTENTANDO {self.port}"
            )

            self.start_reconnect_timer()

    # =========================================================
    # INICIAR RECONEXIÓN
    # =========================================================

    def start_reconnect_timer(self):

        if self.closing:
            return

        if not self.reconnect_timer.isActive():

            self.reconnect_timer.start(
                RECONNECT_INTERVAL
            )

    # =========================================================
    # REINTENTAR CONEXIÓN
    # =========================================================

    def try_reconnect(self):

        if self.closing:
            return

        if self.connected:

            self.reconnect_timer.stop()

            return

        print(
            f"Reintentando conexión con "
            f"{self.port}..."
        )

        self.try_connect()

    # =========================================================
    # PÉRDIDA DE CONEXIÓN
    # =========================================================

    def connection_lost(self):

        if self.closing:
            return

        if not self.connected:
            return

        print(
            f"Se perdió la conexión con "
            f"{self.port}"
        )

        # -----------------------------------------------------
        # IMPORTANTE:
        #
        # Detenemos GET y cerramos completamente
        # la conexión anterior.
        # -----------------------------------------------------

        self.disconnect_serial()

        # -----------------------------------------------------
        # No queda ningún comando pendiente.
        # Los botones quedan deshabilitados.
        # -----------------------------------------------------

        self.set_buttons_enabled(
            False
        )

        self.status_label.setText(
            f"DESCONECTADO - "
            f"REINTENTANDO {self.port}"
        )

        self.start_reconnect_timer()

    # =========================================================
    # DESCONECTAR SERIAL
    # =========================================================

    def disconnect_serial(self):

        self.connected = False

        # -----------------------------------------------------
        # Detener GET
        # -----------------------------------------------------

        self.get_timer.stop()

        # -----------------------------------------------------
        # Detener lector
        # -----------------------------------------------------

        if self.reader is not None:

            try:

                self.reader.stop()

            except Exception:
                pass

            self.reader = None

        # -----------------------------------------------------
        # Cerrar puerto
        # -----------------------------------------------------

        if self.ser is not None:

            try:

                if self.ser.is_open:

                    self.ser.close()

            except Exception:
                pass

            self.ser = None

    # =========================================================
    # ENVIAR COMANDO
    # =========================================================

    def send_command(self, cmd):

        # -----------------------------------------------------
        # Nunca mandar comandos si estamos desconectados.
        # -----------------------------------------------------

        if not self.connected:
            return

        if self.ser is None:
            return

        try:

            # SerialCommand espera CR + LF
            self.ser.write(
                (cmd + "\r\n").encode()
            )

        except (
            serial.SerialException,
            OSError
        ):

            self.connection_lost()

        except Exception as e:

            print(
                f"Error enviando "
                f"{cmd}: {e}"
            )

            self.connection_lost()

    # =========================================================
    # GET
    # =========================================================

    def send_get(self):

        if not self.connected:
            return

        self.send_command(
            "GET"
        )

    # =========================================================
    # ACTUALIZAR ESTADO
    # =========================================================

    def update_status(self, text):

        if not self.connected:
            return

        self.status_label.setText(
            text
        )

    # =========================================================
    # HABILITAR / DESHABILITAR BOTONES
    # =========================================================

    def set_buttons_enabled(self, enabled):

        self.btn1.setEnabled(
            enabled
        )

        self.btn2.setEnabled(
            enabled
        )

        self.btn3.setEnabled(
            enabled
        )

    # =========================================================
    # CERRAR PROGRAMA
    # =========================================================

    def closeEvent(self, event):

        print(
            "Cerrando programa..."
        )

        self.closing = True

        # -----------------------------------------------------
        # Detener timers
        # -----------------------------------------------------

        self.get_timer.stop()

        self.reconnect_timer.stop()

        # -----------------------------------------------------
        # Deshabilitar botones
        # -----------------------------------------------------

        self.set_buttons_enabled(
            False
        )

        # -----------------------------------------------------
        # Desconectar serial
        # -----------------------------------------------------

        self.disconnect_serial()

        event.accept()


# =============================================================
# MAIN
# =============================================================

if __name__ == "__main__":

    app = QApplication(
        sys.argv
    )

    try:

        w = MainWindow()

        w.resize(
            420,
            300
        )

        w.show()

        sys.exit(
            app.exec()
        )

    except Exception as e:

        QMessageBox.critical(
            None,
            "Error",
            str(e)
        )

        sys.exit(1)