#include <Arduino.h>
#include <HTTPClient.h>
#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <time.h>

#if __has_include("config.local.h")
#include "config.local.h"
#endif
#ifndef IOT_WIFI_SSID
#define IOT_WIFI_SSID "Wokwi-GUEST"
#endif
#ifndef IOT_WIFI_PASSWORD
#define IOT_WIFI_PASSWORD ""
#endif
#ifndef IOT_WIFI_CHANNEL
#define IOT_WIFI_CHANNEL 6
#endif
#ifndef IOT_TELEMETRY_URL
#define IOT_TELEMETRY_URL "http://host.wokwi.internal:8080/api/telemetria"
#endif
#ifndef IOT_DEVICE_KEY
#define IOT_DEVICE_KEY ""
#endif

extern const uint8_t rootca_crt_bundle_start[] asm("_binary_certs_x509_crt_bundle_bin_start");

#ifndef PARKING_SLOT
#define PARKING_SLOT 0  // 0 = los cuatro puestos; 1–4 = un ESP32 por puesto.
#endif
static_assert(PARKING_SLOT >= 0 && PARKING_SLOT <= 4, "Puesto invalido");

namespace {
constexpr char WIFI_SSID[] = IOT_WIFI_SSID;
constexpr char TELEMETRY_URL[] = IOT_TELEMETRY_URL;
constexpr uint32_t SEND_INTERVAL_MS = 750;
constexpr uint32_t SAMPLE_INTERVAL_MS = 40;
constexpr uint32_t MIN_SEND_INTERVAL_MS = 100;
constexpr uint32_t ERROR_RETRY_MS = 1000;
constexpr uint32_t WIFI_RETRY_MS = 10000;
constexpr int OCCUPIED_THRESHOLD = 2500;
constexpr int FREE_THRESHOLD = 1800;

struct Slot {
  const char* id;
  uint8_t adcPin;
  uint8_t linkPin;  // A GND (derecha) = en línea.
  bool occupied;
};

Slot slots[] = {
    {"A1", 34, 25, false},
    {"A2", 35, 26, false},
    {"A3", 32, 27, false},
    {"A4", 33, 14, false},
};

constexpr size_t FIRST_SLOT = PARKING_SLOT == 0 ? 0 : PARKING_SLOT - 1;
constexpr size_t END_SLOT = PARKING_SLOT == 0 ? 4 : PARKING_SLOT;
uint32_t lastSend;
uint32_t lastSample;
uint8_t lastSentSignature = 255;
bool lastSendFailed;
uint32_t lastWifiAttempt;
bool wifiWasConnected;
WiFiClient plainClient;
WiFiClientSecure secureClient;
HTTPClient telemetryHttp;
bool httpReady;

String collectTelemetry() {
  String payload;
  payload.reserve(172);
  payload = "{";
  for (size_t i = FIRST_SLOT; i < END_SLOT; ++i) {
    Slot& slot = slots[i];
    if (digitalRead(slot.linkPin) == HIGH) {
      slot.occupied = false;
      continue;
    }

    const int reading = analogRead(slot.adcPin);
    if (reading >= OCCUPIED_THRESHOLD) {
      slot.occupied = true;
    } else if (reading <= FREE_THRESHOLD) {
      slot.occupied = false;
    }

    if (payload.length() > 1) {
      payload += ',';
    }
    char entry[56];
    snprintf(entry, sizeof(entry), "\"%s\":{\"ocupado\":%s,\"adc\":%d}",
             slot.id, slot.occupied ? "true" : "false", reading);
    payload += entry;
  }
  payload += '}';
  return payload;
}

uint8_t telemetrySignature() {
  uint8_t signature = 0;
  for (size_t i = FIRST_SLOT; i < END_SLOT; ++i) {
    if (digitalRead(slots[i].linkPin) == LOW) {
      signature |= (slots[i].occupied ? 3 : 1) << (2 * i);
    }
  }
  return signature;
}

bool sendTelemetry(const String& payload) {
  const bool secure = String(TELEMETRY_URL).startsWith("https://");
  if (secure && time(nullptr) < 1700000000) {
    Serial.println("Esperando hora NTP para verificar HTTPS...");
    return false;
  }
  if (!httpReady) {
    if (secure) secureClient.setCACertBundle(rootca_crt_bundle_start);
    WiFiClient& client = secure ? static_cast<WiFiClient&>(secureClient) : plainClient;
    if (!telemetryHttp.begin(client, TELEMETRY_URL)) {
      Serial.println("No se pudo iniciar HTTP.");
      return false;
    }
    telemetryHttp.setReuse(true);  // Conserva TCP/TLS entre reportes.
    telemetryHttp.setConnectTimeout(secure ? 5000 : 700);
    telemetryHttp.setTimeout(secure ? 5000 : 1000);
    httpReady = true;
  }
  // HTTPClient limpia los encabezados al terminar cada petición.
  telemetryHttp.addHeader("Content-Type", "application/json");
  if (strlen(IOT_DEVICE_KEY) > 0) telemetryHttp.addHeader("X-Device-Key", IOT_DEVICE_KEY);
  const uint32_t started = millis();
  const int status = telemetryHttp.POST(payload);

  if (status == 204) {
    Serial.println(payload);
    Serial.printf("Reporte aceptado | HTTP %lu ms\n", millis() - started);
    return true;
  } else {
    Serial.printf("Servidor HTTP (%d). Revisa URL, conectividad y clave del sensor.\n", status);
    telemetryHttp.end();
    httpReady = false;
    return false;
  }
}
}  // namespace

void setup() {
  Serial.begin(115200);
  analogReadResolution(12);
  for (size_t i = FIRST_SLOT; i < END_SLOT; ++i) {
    pinMode(slots[i].linkPin, INPUT_PULLUP);
  }
  WiFi.mode(WIFI_STA);
  WiFi.setAutoReconnect(true);
  WiFi.begin(WIFI_SSID, IOT_WIFI_PASSWORD, IOT_WIFI_CHANNEL);
  configTime(0, 0, "pool.ntp.org", "time.google.com");
  lastWifiAttempt = millis();
  Serial.println("Estacionamiento IoT | Conectando a Wokwi-GUEST...");
}

void loop() {
  const uint32_t now = millis();
  const bool connected = WiFi.status() == WL_CONNECTED;
  if (connected != wifiWasConnected) {
    wifiWasConnected = connected;
    if (connected) {
      Serial.print("Wi-Fi conectado. IP: ");
      Serial.println(WiFi.localIP());
    } else {
      Serial.println("Wi-Fi desconectado.");
      telemetryHttp.end();
      httpReady = false;
    }
  }

  if (connected && now - lastSample >= SAMPLE_INTERVAL_MS) {
    lastSample = now;
    const String payload = collectTelemetry();
    const uint8_t signature = telemetrySignature();
    const uint32_t elapsed = now - lastSend;
    const bool changed = signature != lastSentSignature;
    if (payload != "{}" && elapsed >= (lastSendFailed ? ERROR_RETRY_MS : MIN_SEND_INTERVAL_MS)
        && (changed || elapsed >= SEND_INTERVAL_MS)) {
      lastSendFailed = !sendTelemetry(payload);
      lastSend = millis();
      if (!lastSendFailed) lastSentSignature = signature;
    }
  } else if (!connected && now - lastWifiAttempt >= WIFI_RETRY_MS) {
    lastWifiAttempt = now;
    WiFi.reconnect();
  }
  delay(5);
}
