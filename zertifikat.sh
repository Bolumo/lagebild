#!/bin/sh
# Erzeugt eine eigene Zertifizierungsstelle (CA) nur für diesen Messaufbau und
# ein HTTPS-Zertifikat für den Mac. Das iPhone verlangt HTTPS, sonst gibt Safari
# Mikrofon, Kamera und Bewegungssensor nicht frei.
#
# Die CA ist per Name Constraints auf lokale Adressen beschränkt
# (192.168.x.x, 127.x.x.x, *.local, localhost) und gilt 1 Jahr.
#
# Danach aufs iPhone:
#   1. cert/lagebild-ca.cer per AirDrop schicken und das Profil installieren
#      (Einstellungen → Profil geladen → Installieren)
#   2. Einstellungen → Allgemein → Info → Zertifikatsvertrauenseinstellungen
#      → „Lagebild Test-CA“ einschalten
# Wieder entfernen: Einstellungen → Allgemein → VPN und Geräteverwaltung → Profil löschen.
set -eu
cd "$(dirname "$0")"
mkdir -p cert
cd cert

HOST="$(scutil --get LocalHostName).local"
IP="$(ipconfig getifaddr en0)"

if [ ! -f lagebild-ca.pem ]; then
  printf "basicConstraints=critical,CA:TRUE\nkeyUsage=critical,keyCertSign,cRLSign\nnameConstraints=critical,permitted;IP:192.168.0.0/255.255.0.0,permitted;IP:127.0.0.0/255.0.0.0,permitted;DNS:local,permitted;DNS:localhost\n" > ca.ext
  openssl req -new -newkey rsa:2048 -nodes -keyout lagebild-ca-key.pem -out ca.csr -subj "/CN=Lagebild Test-CA"
  openssl x509 -req -in ca.csr -signkey lagebild-ca-key.pem -days 365 -out lagebild-ca.pem -extfile ca.ext
  rm ca.csr ca.ext
fi
openssl x509 -in lagebild-ca.pem -outform der -out lagebild-ca.cer  # fürs iPhone (AirDrop)

printf "subjectAltName=DNS:%s,DNS:localhost,IP:%s,IP:127.0.0.1\nextendedKeyUsage=serverAuth\nbasicConstraints=CA:FALSE\nkeyUsage=critical,digitalSignature,keyEncipherment\n" "$HOST" "$IP" > server.ext
openssl req -new -newkey rsa:2048 -nodes -keyout server-key.pem -out server.csr -subj "/CN=$HOST"
openssl x509 -req -in server.csr -CA lagebild-ca.pem -CAkey lagebild-ca-key.pem -CAcreateserial -days 365 -out server.pem -extfile server.ext
rm server.csr server.ext
chmod 600 lagebild-ca-key.pem server-key.pem

echo
echo "Fertig."
echo "Aufs iPhone (AirDrop):  $(pwd)/lagebild-ca.cer"
echo "Im iPhone-Safari öffnen: https://$HOST:8443/   oder   https://$IP:8443/"
