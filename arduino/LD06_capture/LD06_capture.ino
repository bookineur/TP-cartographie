// Capture de scans LD06 pour le PC (python -m ld06.capture --mode arduino)
// Basé sur examples/Basic/Basic.ino de la librairie LD06 (Mike118).
//
// Différences avec l'exemple :
//  - sortie CSV (printScanCSV) au lieu de Teleplot : angle + distance + intensité ;
//  - pas de filtrage : on garde les données brutes, on filtrera côté PC ;
//  - après chaque scan imprimé on jette le scan suivant : pendant l'impression
//    (~12 ko par tour) on ne lit plus le lidar, son buffer UART déborde et le
//    scan en cours aurait des trous. Ainsi chaque scan envoyé est complet.

#include "ld06.h"

LD06 ld06(Serial1);  // LD06 TX -> RX1 de la carte, GND commun, 5 V

bool skipNext = true;

void setup() {
  Serial.begin(921600);  // USB natif (Teensy) : valeur ignorée ; sinon le plus rapide possible
  ld06.init();           // Serial1 @ 230400
  ld06.enableCRC();
  ld06.enableFullScan();
  ld06.disableFiltering();
}

void loop() {
  if (ld06.readScan()) {
    if (skipNext) {
      skipNext = false;
      return;
    }
    ld06.printScanCSV(Serial);  // "N,Angle(°),Distance(mm),Intensity,x(mm),y(mm)" puis ligne vide
    skipNext = true;
    while (Serial1.available()) Serial1.read();  // vide les octets à moitié reçus
  }
}
