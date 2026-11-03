// ============================================================================
//  ESP32 + LD06 : envoi des scans en CSV AVEC l'intensité (pour Lidar Plot)
//  Basé sur ESP32_LD06_Test.ino (même câblage) — seule la sortie change :
//    printScanTeleplot() envoie x, y seulement  -> intensité perdue
//    printScanCSV()      envoie N, angle, distance, INTENSITÉ, x, y
//
//  Dans Lidar Plot : port COM3, Débit = Auto (ou 921600), Format = Texte.
// ============================================================================

#include "ld06.h"

#define RX_LIDAR   33   // TX du lidar -> GPIO33
#define TX_LIDAR   -1   // non utilisé
#define LD06_PWM_PIN 32 // PWM du lidar -> GPIO32
#define LIDAR_BAUD 230400
LD06 ld06(Serial2, LD06_PWM_PIN);

bool skipNext = true;

void setup() {
  // 921600 bauds : un tour en CSV fait ~12 ko ; à 115200 il faudrait ~1 s pour l'envoyer
  Serial.begin(921600);

  Serial2.setRxBufferSize(4096);
  Serial2.begin(LIDAR_BAUD, SERIAL_8N1, RX_LIDAR, TX_LIDAR);
  Serial2.setTimeout(10);
  ld06.init();

  ld06.enableCRC();
  ld06.enableFullScan();
  ld06.disableFiltering();  // on garde TOUS les points : le seuil d'intensité se règle dans Lidar Plot

  /*
  // --- Variante : filtrer directement sur le robot (ce que montrait le prof) ---
  ld06.enableFiltering();
  ld06.setIntensityThreshold(100);    // supprime les points d'intensité < 100
  ld06.setDistanceRange(100, 12000);  // 0,1 à 12 m  (attention : l'exemple d'origine coupe à 1 m !)
  ld06.setAngleRange(0, 360);
  */
}

void loop() {
  if (ld06.readScan()) {
    if (skipNext) {  // pendant l'envoi d'un tour, le tour suivant perd des paquets : on le saute
      skipNext = false;
      return;
    }
    ld06.printScanCSV(Serial);  // "N,Angle(°),Distance(mm),Intensity,x(mm),y(mm)" puis une ligne vide
    skipNext = true;
    while (Serial2.available()) Serial2.read();  // vide les octets à moitié reçus
  }
}
