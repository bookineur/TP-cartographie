// ============================================================================
//  ESP32 + LD06 : scans CSV pour Lidar Lab (aperçu en direct + capture USB)  — version 2
//  Basé sur ESP32_LD06_CSV_intensite.ino (même câblage), avec en plus :
//    - roues arrêtées au démarrage (toutes les broches moteurs à LOW)
//    - vitesse de rotation du LiDAR réglable par PWM (GPIO32)
//
//  Sortie USB : 921600 bauds, printScanCSV = "N,Angle,Distance,Intensity,x,y"
//  (en-tête au premier tour seulement), une ligne par point, puis une ligne vide.
//  C'est le format attendu par Lidar Lab (codex_lidar). Ne pas ouvrir Teleplot
//  ou le moniteur série en même temps : un seul programme peut utiliser le port.
// ============================================================================

#include "ld06.h"

#define RX_LIDAR     33   // TX du lidar -> GPIO33
#define TX_LIDAR     -1   // non utilisé
#define LD06_PWM_PIN 32   // PWM du lidar -> GPIO32
#define LIDAR_BAUD   230400
LD06 ld06(Serial2, LD06_PWM_PIN);

// ---------------- Vitesse du LiDAR ----------------
// ~40 % ≈ 10 Hz (≈ 450 points/tour). Plus bas = plus lent = plus de points par tour.
// Essaie 35 puis 30 et regarde le nombre de points affiché dans Lidar Lab.
#define LIDAR_PWM_PCT 40
#define PWM_FREQ_HZ   30000  // 20 à 50 kHz recommandé
#define PWM_BITS      8      // 0 à 255
#define PWM_CHANNEL   0      // seulement pour l'ancien noyau ESP32 (2.x)

// ---------------- Roues (pont en H) ----------------
//   M2 avant gauche   : D18 avance, D19 recule
//   M1 avant droite   : D5  avance, D17 recule
//   M3 arriere gauche : D15 avance, D2  recule
//   M4 arriere droite : D16 avance, D4  recule
const uint8_t MOTOR_PINS[] = {18, 19, 5, 17, 15, 2, 4, 16};

void stopWheels() {
  for (uint8_t pin : MOTOR_PINS) {
    pinMode(pin, OUTPUT);
    digitalWrite(pin, LOW);  // les deux entrées à LOW = roue arrêtée
  }
}

void initLidarPwm() {
  uint32_t duty = (uint32_t)constrain(LIDAR_PWM_PCT, 0, 100) * 255 / 100;
#if ESP_ARDUINO_VERSION_MAJOR >= 3
  ledcAttach(LD06_PWM_PIN, PWM_FREQ_HZ, PWM_BITS);
  ledcWrite(LD06_PWM_PIN, duty);
#else
  ledcSetup(PWM_CHANNEL, PWM_FREQ_HZ, PWM_BITS);
  ledcAttachPin(LD06_PWM_PIN, PWM_CHANNEL);
  ledcWrite(PWM_CHANNEL, duty);
#endif
}

bool skipNext = true;

void setup() {
  stopWheels();             // roues arrêtées avant tout le reste

  // 921600 bauds : un tour en CSV fait ~12 ko ; à 115200 il faudrait ~1 s pour l'envoyer
  Serial.begin(921600);

  Serial2.setRxBufferSize(4096);
  Serial2.begin(LIDAR_BAUD, SERIAL_8N1, RX_LIDAR, TX_LIDAR);
  Serial2.setTimeout(10);
  ld06.init();              // met GPIO32 à HIGH...
  initLidarPwm();           // ...puis on applique notre vitesse (APRÈS init)

  ld06.enableCRC();
  ld06.enableFullScan();
  ld06.disableFiltering();  // tous les points : portée et intensité se règlent dans Lidar Lab
}

void loop() {
  if (ld06.readScan()) {
    if (skipNext) {  // pendant l'envoi d'un tour, le tour suivant perd des paquets : on le saute
      skipNext = false;
      return;
    }
    ld06.printScanCSV(Serial);  // points du tour puis une ligne vide
    skipNext = true;
    while (Serial2.available()) Serial2.read();  // vide les octets à moitié reçus
  }
}
