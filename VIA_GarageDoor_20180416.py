#include <ESP8266WiFi.h>
#include <WiFiClient.h>
#include <ESP8266WebServer.h>
#include <ESP8266mDNS.h>
#include <PubSubClient.h>
#include <DHT.h>

/**************************** PIN DEFINITIONS ********************************************/
const int MainDoor = D1;
const int ThirdDoor = D2;
const int Interlock = D5;
#define DHTPIN    D7
#define DHTTYPE   DHT22
DHT dht(DHTPIN, DHTTYPE);

/**************************** SENSOR DEFINITIONS *******************************************/
String Switch1;
String Switch2;

float diffTEMP = 0.2;
float tempValue;

float diffHUM = 0.5;
float humValue;

int i = 0, j = 0, k = 0, l = 0;
int watchdog1 = 0, watchdog2 = 0;

/************ WIFI and MQTT INFORMATION (CHANGE THESE FOR YOUR SETUP) ******************/
const char* host = "garage-webupdate";
const char* ssid = "########";
const char* password = "########";
IPAddress MQTTserver(#, #, #, #);

ESP8266WebServer server(80);
const char* serverIndex = "<form method='POST' action='/update' enctype='multipart/form-data'><input type='file' name='update'><input type='submit' value='Update'></form>";

void callback(char* topic, byte* payload, unsigned int length);

WiFiClient ethClient;
PubSubClient client(MQTTserver, 1883, callback, ethClient);

void setup(void) {
  pinMode(MainDoor, OUTPUT); // Relay Switch 1
  digitalWrite(MainDoor, HIGH);

  pinMode(ThirdDoor, OUTPUT); // Relay Switch 2
  digitalWrite(ThirdDoor, HIGH);

  pinMode(Interlock, OUTPUT); // Relay Switch 2
  digitalWrite(Interlock, HIGH);

  Serial.begin(9600);
  Serial.println();
  Serial.println("Booting Sketch...");
  pinMode(DHTPIN, INPUT);
  delay(300);

  WiFi.mode(WIFI_AP_STA);
  WiFi.begin(ssid, password);

  if (WiFi.waitForConnectResult() == WL_CONNECTED) {
    MDNS.begin(host);
    server.on("/", HTTP_GET, []() {
      server.sendHeader("Connection", "close");
      server.sendHeader("Access-Control-Allow-Origin", "*");
      server.send(200, "text/html", serverIndex);
    });
    server.on("/update", HTTP_POST, []() {
      server.sendHeader("Connection", "close");
      server.sendHeader("Access-Control-Allow-Origin", "*");
      server.send(200, "text/plain", (Update.hasError()) ? "FAIL" : "OK");
      ESP.restart();
    }, []() {
      HTTPUpload& upload = server.upload();
      if (upload.status == UPLOAD_FILE_START) {
        Serial.setDebugOutput(true);
        WiFiUDP::stopAll();
        Serial.printf("Update: %s\n", upload.filename.c_str());
        uint32_t maxSketchSpace = (ESP.getFreeSketchSpace() - 0x1000) & 0xFFFFF000;
        if (!Update.begin(maxSketchSpace)) { //start with max available size
          Update.printError(Serial);
        }
      } else if (upload.status == UPLOAD_FILE_WRITE) {
        if (Update.write(upload.buf, upload.currentSize) != upload.currentSize) {
          Update.printError(Serial);
        }
      } else if (upload.status == UPLOAD_FILE_END) {
        if (Update.end(true)) { //true to set the size to the current progress
          Serial.printf("Update Success: %u\nRebooting...\n", upload.totalSize);
        } else {
          Update.printError(Serial);
        }
        Serial.setDebugOutput(false);
      }
      yield();
    });
    server.begin();
    MDNS.addService("http", "tcp", 80);

    Serial.printf("Ready! Open http://%s.local in your browser\n", host);
  } else {
    Serial.println("WiFi Failed");
  }
  if (client.connect("garageNODE", "homeassistant", "1503")) {
    client.publish("outTopic", "hello world");
    client.subscribe("home/garage/control/#");
  }
}

void reconnect() {
  // Loop until we're reconnected
  while (!client.connected()) {
    Serial.print("Attempting MQTT connection...");
    // Attempt to connect
    if (client.connect("garageNODE", "#######", "#######")) {
      Serial.println("connected");
      client.subscribe("home/garage/control/#");
      client.publish("outTopic", "hello world");
    } else {
      Serial.print("failed, rc=");
      Serial.print(client.state());
      Serial.println(" try again in 5 seconds");
      // Wait 5 seconds before retrying
      delay(5000);
    }
  }
}

void DHT_Sensor() {
  float newTempValue = dht.readTemperature();
  float newHumValue = dht.readHumidity();
  if ((checkBoundSensor(newTempValue, tempValue, diffTEMP)) || (j == 10)) {
    tempValue = newTempValue;
    client.publish("home/garage/temperature", String(tempValue, 1).c_str(), true);;
    j = 0;
  }
  j++;
  if ((checkBoundSensor(newHumValue, humValue, diffHUM)) || (k >= 10)) {
    humValue = newHumValue;
    client.publish("home/garage/humidity", String(humValue, 1).c_str(), true);
    k = 0;
  }
  k++;
}

void callback(char* topic, byte* payload, unsigned int length) {
  String topicStr = String((char*)topic);
  //Print out some debugging info
  Serial.println("Callback update.");
  Serial.print("Topic: ");
  Serial.println(topicStr);
  l = 0;
  if (topicStr == "home/garage/control/set1")
  {
    Switch1 = String((char*)payload)[0];
    Serial.println(Switch1);
    //turn the switch on if the payload is '1' and publish to the MQTT server a confirmation message
    if (Switch1 == "1") {
      digitalWrite(MainDoor, LOW);
      digitalWrite(Interlock, LOW);
      client.publish( "home/garage/control1", "1");
      Serial.println("ON");
    }
    //turn the switch off if the payload is '0' and publish to the MQTT server a confirmation message
    else if (Switch1 == "0") {
      digitalWrite(MainDoor, HIGH);
      digitalWrite(Interlock, HIGH);
      client.publish( "home/garage/control1", "0");
      Serial.println("OFF");
    }
  }
  if (topicStr == "home/garage/control/set2")
  {
    Switch2 = String((char*)payload)[0];
    Serial.println(Switch2);
    //turn the switch on if the payload is '1' and publish to the MQTT server a confirmation message
    if (Switch2 == "1") {
      digitalWrite(ThirdDoor, LOW);
      digitalWrite(Interlock, LOW);
      client.publish( "home/garage/control2", "1");
      Serial.println("ON");
    }
    //turn the switch off if the payload is '0' and publish to the MQTT server a confirmation message
    else if (Switch2 == "0") {
      digitalWrite(ThirdDoor, HIGH);
      digitalWrite(Interlock, HIGH);
      client.publish( "home/garage/control2", "0");
      Serial.println("OFF");
    }
  }
}


/********************************** START CHECK SENSOR **********************************/
bool checkBoundSensor(float newValue, float prevValue, float maxDiff) {
  return newValue < prevValue - maxDiff || newValue > prevValue + maxDiff;
}

void loop(void) {
  server.handleClient();
  reconnect();
  delay(10);
  client.loop();
  if (i >= 500) {
    DHT_Sensor();
    i = 0;
  }
  if (l >= 100) {
    if ((Switch1 == "1")||(Switch2 == "1")) {
      client.publish( "home/garage/control1", "0");
      client.publish( "home/garage/control/set1", "0");
      client.publish( "home/garage/control2", "0");
      client.publish( "home/garage/control/set2", "0");
    }
    l = 0;
  }
  i++;
  l++;
}
