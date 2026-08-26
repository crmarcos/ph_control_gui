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

GET_INTERVAL = 2000
RECONNECT_INTERVAL = 2000

# Al abrir el puerto serie, Arduino puede reiniciarse.
ARDUINO_BOOT_DELAY = 1200

# Tiempo máximo esperando una respuesta ESTADO durante
# la restauración.
RESTORE_RESPONSE_TIMEOUT = 2000

# Tiempo entre comandos de restauración.
RESTORE_STEP_DELAY = 300


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
        # ESTADO CONFIRMADO POR ARDUINO
        #
        # None  = todavía desconocido
        # True  = ON
        # False = OFF
        # -----------------------------------------------------

        self.acido_state = None
        self.base_state = None

        # -----------------------------------------------------
        # ESTADO DE RESTAURACIÓN
        # -----------------------------------------------------

        self.restoring = False

        self.restore_steps = []
        self.restore_index = 0

        # -----------------------------------------------------
        # LABEL DE ESTADO
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
        # TIMER ESPERA ARRANQUE ARDUINO
        # -----------------------------------------------------

        self.connect_timer = QTimer(self)

        self.connect_timer.setSingleShot(True)

        self.connect_timer.timeout.connect(
            self.start_restore
        )

        # -----------------------------------------------------
        # TIMER ENTRE PASOS DE RESTAURACIÓN
        # -----------------------------------------------------

        self.restore_timer = QTimer(self)

        self.restore_timer.setSingleShot(True)

        self.restore_timer.timeout.connect(
            self.restore_next_step
        )

        # -----------------------------------------------------
        # TIMEOUT ESPERANDO ESTADO
        # -----------------------------------------------------

        self.restore_timeout_timer = QTimer(self)

        self.restore_timeout_timer.setSingleShot(True)

        self.restore_timeout_timer.timeout.connect(
            self.restore_timeout
        )

        # -----------------------------------------------------
        # PRIMERA CONEXIÓN
        # -----------------------------------------------------

        self.try_connect()

    # =========================================================
    # CONECTAR
    # =========================================================

    def try_connect(self):

        if self.closing:
            return

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
                "CONECTADO - ESPERANDO"
            )

            # Durante la restauración los botones permanecen
            # deshabilitados.
            self.set_buttons_enabled(False)

            self.reconnect_timer.stop()

            # -------------------------------------------------
            # Crear lector serie
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

            print(
                f"Conectado a {self.port}"
            )

            # -------------------------------------------------
            # Arduino puede resetearse al abrir el COM.
            # Esperamos antes de mandar comandos.
            # -------------------------------------------------

            print(
                f"Esperando {ARDUINO_BOOT_DELAY} ms "
                "para que Arduino termine de arrancar..."
            )

            self.connect_timer.start(
                ARDUINO_BOOT_DELAY
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

            self.set_buttons_enabled(False)

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

        # Cancelar cualquier restauración en curso.
        self.cancel_restore()

        self.disconnect_serial()

        self.set_buttons_enabled(False)

        self.status_label.setText(
            f"DESCONECTADO - "
            f"REINTENTANDO {self.port}"
        )

        print()
        print(
            "Estado guardado para la próxima "
            "reconexión:"
        )

        self.print_saved_state()

        print()

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
        # Detener timers de restauración
        # -----------------------------------------------------

        self.connect_timer.stop()
        self.restore_timer.stop()
        self.restore_timeout_timer.stop()

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

        if not self.connected:
            return False

        if self.ser is None:
            return False

        try:

            print(
                f"TX: {cmd}"
            )

            # SerialCommand espera CR + LF.
            self.ser.write(
                (cmd + "\r\n").encode()
            )

            return True

        except (
            serial.SerialException,
            OSError
        ):

            self.connection_lost()

            return False

        except Exception as e:

            print(
                f"Error enviando "
                f"{cmd}: {e}"
            )

            self.connection_lost()

            return False

    # =========================================================
    # GET NORMAL
    # =========================================================

    def send_get(self):

        if not self.connected:
            return

        # Durante la restauración el GET es controlado
        # por la máquina de restauración.
        if self.restoring:
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

        print(
            f"RX: {text}"
        )

        self.status_label.setText(
            text
        )

        # -----------------------------------------------------
        # Solo procesamos mensajes ESTADO:
        # -----------------------------------------------------

        if not text.upper().startswith("ESTADO:"):
            return

        texto = text.upper()

        # -----------------------------------------------------
        # ÁCIDO
        # -----------------------------------------------------

        if "ÁCIDO ON" in texto:

            self.acido_state = True

        elif "ÁCIDO OFF" in texto:

            self.acido_state = False

        # -----------------------------------------------------
        # BASE
        # -----------------------------------------------------

        if "BASE ON" in texto:

            self.base_state = True

        elif "BASE OFF" in texto:

            self.base_state = False

        # -----------------------------------------------------
        # Mostrar estado guardado
        # -----------------------------------------------------

        print(
            "Estado confirmado y guardado:"
        )

        self.print_saved_state()

        # -----------------------------------------------------
        # Si estamos restaurando, esta respuesta confirma
        # que Arduino recibió/procesó los comandos.
        # -----------------------------------------------------

        if self.restoring:

            print(
                "Estado recibido durante la "
                "restauración."
            )

            self.restore_timeout_timer.stop()

            self.finish_restore()

    # =========================================================
    # MOSTRAR ESTADO GUARDADO
    # =========================================================

    def print_saved_state(self):

        if self.acido_state is True:

            acido = "ON"

        elif self.acido_state is False:

            acido = "OFF"

        else:

            acido = "DESCONOCIDO"

        if self.base_state is True:

            base = "ON"

        elif self.base_state is False:

            base = "OFF"

        else:

            base = "DESCONOCIDO"

        print(
            f"  ACIDO = {acido}"
        )

        print(
            f"  BASE  = {base}"
        )

    # =========================================================
    # INICIAR RESTAURACIÓN
    # =========================================================

    def start_restore(self):

        if not self.connected:
            return

        self.restoring = True

        self.restore_steps = []
        self.restore_index = 0

        # -----------------------------------------------------
        # No tenemos un estado completo guardado.
        #
        # En este caso NO mandamos APAGAR.
        # Simplemente preguntamos al Arduino.
        # -----------------------------------------------------

        if (
            self.acido_state is None
            or self.base_state is None
        ):

            print()
            print(
                "No hay estado guardado completo."
            )

            print(
                "Consultando estado actual..."
            )

            self.restore_steps = [
                "GET"
            ]

        else:

            print()
            print(
                "================================"
            )

            print(
                "RESTAURANDO ESTADO GUARDADO"
            )

            print(
                "================================"
            )

            self.print_saved_state()

            print()

            # -------------------------------------------------
            # Primero apagamos ambos canales.
            # -------------------------------------------------

            self.restore_steps.append(
                "APAGAR"
            )

            # -------------------------------------------------
            # Recuperar ACIDO si estaba ON.
            # -------------------------------------------------

            if self.acido_state:

                self.restore_steps.append(
                    "ACIDO"
                )

            # -------------------------------------------------
            # Recuperar BASE si estaba ON.
            # -------------------------------------------------

            if self.base_state:

                self.restore_steps.append(
                    "BASE"
                )

            # -------------------------------------------------
            # Verificación final.
            # -------------------------------------------------

            self.restore_steps.append(
                "GET"
            )

        self.restore_next_step()

    # =========================================================
    # SIGUIENTE PASO DE RESTAURACIÓN
    # =========================================================

    def restore_next_step(self):

        if not self.restoring:
            return

        if not self.connected:

            self.cancel_restore()

            return

        # -----------------------------------------------------
        # ¿Terminamos todos los comandos?
        # -----------------------------------------------------

        if self.restore_index >= len(
            self.restore_steps
        ):

            self.finish_restore()

            return

        # -----------------------------------------------------
        # Siguiente comando
        # -----------------------------------------------------

        cmd = self.restore_steps[
            self.restore_index
        ]

        self.restore_index += 1

        print(
            f"RESTORE -> {cmd}"
        )

        # -----------------------------------------------------
        # Enviar
        # -----------------------------------------------------

        if not self.send_command(cmd):

            self.cancel_restore()

            return

        # -----------------------------------------------------
        # GET:
        #
        # Esperamos una respuesta ESTADO.
        # No avanzamos hasta recibirla.
        # -----------------------------------------------------

        if cmd == "GET":

            self.restore_timeout_timer.start(
                RESTORE_RESPONSE_TIMEOUT
            )

            return

        # -----------------------------------------------------
        # APAGAR / ACIDO / BASE:
        #
        # Esperamos antes del siguiente comando.
        # -----------------------------------------------------

        self.restore_timer.start(
            RESTORE_STEP_DELAY
        )

    # =========================================================
    # TIMEOUT DE RESTAURACIÓN
    # =========================================================

    def restore_timeout(self):

        if not self.restoring:
            return

        if not self.connected:
            return

        print()
        print(
            "TIMEOUT esperando respuesta "
            "ESTADO."
        )

        print(
            "Reintentando GET..."
        )

        # -----------------------------------------------------
        # No acumulamos comandos.
        # Simplemente volvemos a consultar.
        # -----------------------------------------------------

        self.restore_steps = [
            "GET"
        ]

        self.restore_index = 0

        self.restore_next_step()

    # =========================================================
    # TERMINAR RESTAURACIÓN
    # =========================================================

    def finish_restore(self):

        if not self.restoring:
            return

        self.restoring = False

        self.restore_timer.stop()
        self.restore_timeout_timer.stop()

        print()
        print(
            "================================"
        )

        print(
            "RESTAURACIÓN COMPLETADA"
        )

        print(
            "================================"
        )

        print(
            "Estado confirmado:"
        )

        self.print_saved_state()

        print(
            "================================"
        )

        print()

        # -----------------------------------------------------
        # Volver al funcionamiento normal.
        # -----------------------------------------------------

        self.set_buttons_enabled(True)

        self.get_timer.start(
            GET_INTERVAL
        )

    # =========================================================
    # CANCELAR RESTAURACIÓN
    # =========================================================

    def cancel_restore(self):

        self.restoring = False

        self.connect_timer.stop()
        self.restore_timer.stop()
        self.restore_timeout_timer.stop()

        self.restore_steps = []
        self.restore_index = 0

    # =========================================================
    # BOTONES
    # =========================================================

    def set_buttons_enabled(self, enabled):

        # Nunca habilitar durante restauración.
        if self.restoring:

            enabled = False

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
    # CIERRE
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

        self.connect_timer.stop()

        self.restore_timer.stop()

        self.restore_timeout_timer.stop()

        # -----------------------------------------------------
        # Deshabilitar botones
        # -----------------------------------------------------

        self.set_buttons_enabled(
            False
        )

        # -----------------------------------------------------
        # Desconectar
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