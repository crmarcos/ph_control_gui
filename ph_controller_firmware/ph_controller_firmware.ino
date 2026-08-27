/**
Firmware para interactuar con el control de PH del BIOFLO.
Controla el estado de 2 contactos secos conectados en paralelo con 
las llaves de Modo de las bombas peristálticas: Entre la posición 
OFF y AUTO.

Esto permite habilitar o deshabilitar de forma remota las bombas.

*/

#include <SerialCommand.h>
SerialCommand sCmd;

#define PIN_LED     13
#define BLINK_DELAY 500
unsigned long lastMillis = 0;

#define PIN_ACIDO   6
#define PIN_BASE    7

void acido_cb()
{
    digitalWrite(PIN_ACIDO, LOW);
    digitalWrite(PIN_BASE, HIGH);
}

void base_cb()
{
    digitalWrite(PIN_BASE, LOW);
    digitalWrite(PIN_ACIDO, HIGH);
}

void apagar_cb()
{
    digitalWrite(PIN_BASE, HIGH);
    digitalWrite(PIN_ACIDO, HIGH);
}

void get_cb()
{
    Serial.print("ESTADO: ");

    if(digitalRead(PIN_ACIDO)) {
      Serial.print("ÁCIDO OFF, ");
    }else{
      Serial.print("ÁCIDO ON, ");
    }

    if(digitalRead(PIN_BASE)) {
      Serial.println("BASE OFF");
    }else{
      Serial.println("BASE ON");
    }

}

void setup()
{
    pinMode(PIN_LED, OUTPUT);
    digitalWrite(PIN_LED, LOW);

    pinMode(PIN_ACIDO, OUTPUT);
    digitalWrite(PIN_ACIDO, HIGH);
    pinMode(PIN_BASE, OUTPUT);
    digitalWrite(PIN_BASE, HIGH);

    Serial.begin(9600);

    sCmd.begin(Serial);

    sCmd.addExecuteCommand((char*)"ACIDO", acido_cb);
    sCmd.addExecuteCommand((char*)"BASE", base_cb);
    sCmd.addExecuteCommand((char*)"APAGAR", apagar_cb);
    sCmd.addExecuteCommand((char*)"GET", get_cb);
}

void loop()
{
    sCmd.loop();

  if(millis() - lastMillis > BLINK_DELAY){
    lastMillis = millis();
    digitalWrite(PIN_LED, !digitalRead(PIN_LED));
  }

}