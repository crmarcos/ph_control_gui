# PH Control - Control de PH de BIOFLO2000

Permite controlar la placa de control remoto del PH CONTROLLER del BIOFLO2000.
Controla el estado de 2 contactos secos conectados en paralelo con las llaves de Modo de
las bombas de Ácido y Base, entre la posición OFF y AUTO, permitiendo apagarlas y seleccionar cuál
de las 2 permanece encendida. 

La comunicación es por puerto serie, con una velocidad de 9600, 8N1.
El firmware asociado a este control remoto se ubica dentro de este repositorio para mayor practicidad.

## Tabla de Contenidos

- [Instalación](#instalación)
  - [Prerequisitos](#prerequisitos)
  - [Copia de repositorio y dependencias](#copia-de-repositorio-y-dependencias)
- [Uso](#uso)
  - [1. Seteo de puerto y velocidad](#1-seteo-de-puerto-y-velocidad)
  - [2. Interface](#2-interface)
  - [3. Ejecución del script](#3-ejecución-del-script)
- [Licencia](#licencia)


## Instalación
### Prerequisitos
Tener instalados los siguientes programas:
- Python
- Git

### Copia de repositorio y dependencias
1. Clona el repositorio:
   ```bash
   git clone https://github.com/crmarcos/ph_control_gui.git
   ```
2. Instala las dependencias:
   ```bash
   pip install -r requirements.txt
   ```

## Uso

Los archivos que debe modificar el usuario son los siguientes:
- config.txt: define el puerto serie (Velocidad y puerto) donde está conectado el control.

### 1. Seteo de puerto y velocidad
Dentro del archivo **config.txt**, modificar el valor de la variable **PORT** al puerto que corresponda. **COMX** en windows, **/dev/ttyX** en linux, donde **X** lo otorga el sistema. La velocidad está fija, pero por si alguna razón cambia el firmware, modificar **BAUD** al valor que corresponda.

```bash
PORT=COM4
BAUD=9600
```

### 2. Interface
La interface es intuitiva. 
La ventana de texto superior muestra el estado de los switches y el estado de conexión.
Luego hay 3 botones, uno para encender la bomba de Ácido, otro para encender la bomba de Base y otro para apagar ambas bombas.
Por firmware, solo una bomba puede trabajar a la vez.


### 3. Ejecución del script
Ir al mismo nivel donde se encuentra el archivo **main.py** y ejecutar:

```bash
py .\main.py
```

Una vez que se logra la comunicación con la bomba, se recibe el estado de los switches.
Si la placa sufrió alguna desconexión, el programa reintenta conectarse y vuelve a la configuración previa.


## Licencia

Este proyecto está bajo la Licencia GPLv3.
