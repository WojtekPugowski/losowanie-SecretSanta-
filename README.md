# 🎁 Losowanie prezentów → WhatsApp

Prosta aplikacja na macOS do losowania „kto komu robi prezent” (Secret Santa / Mikołajki).
Każdy uczestnik dostaje swój wynik **prywatnie przez WhatsApp**. Organizator, z którego konta
idą wiadomości, nie widzi wyników nigdzie w aplikacji. Zna tylko swój własny wynik.

## Funkcje

- **Losowanie unikatowe:** każdy losuje dokładnie jedną osobę, każda osoba jest wylosowana
  dokładnie raz i nikt nie losuje siebie.
- **Tryb „jeden łańcuch”** (domyślnie włączony): A → B → C → … → A, bez zamkniętych par
  typu A ↔ B.
- **Wyniki tylko w pamięci:** nie pojawiają się w przeglądarce, terminalu, logach ani plikach.
  Znikają po kliknięciu „Zakończ” albo po zamknięciu programu.
- **Tryb „nie patrz”:** przed wysyłką aplikacja ostrzega organizatora, odlicza 10–60 s
  (domyślnie 15 s), podaje godzinę powrotu i sygnalizuje koniec dwoma dźwiękami.
- **Automatyczna wysyłka** przez WhatsApp Desktop, bez klikania.
- **Ukryty wynik w wiadomości:** na liście czatów widać tylko nagłówek, a wylosowane imię
  jest schowane pod „Czytaj więcej”.
- **Ponowna wysyłka** do wybranej osoby (np. gdy wiadomość nie wyszła), bez nowego losowania
  i bez ujawniania wyniku.
- **Test** na własny numer przed właściwą wysyłką.
- **Tryb próbny** (`--dry-run`): nic nie jest wysyłane. Działa też na Linuksie i Windowsie.
- **Bez zależności:** wystarczy sam Python 3.9+ z biblioteką standardową.

## Wymagania

- macOS z zainstalowanym i zalogowanym **WhatsApp Desktop**
- **Python 3.9+** (`python3`). Jeśli go brakuje, macOS zaproponuje instalację narzędzi Xcode CLT.
- Uprawnienie **Dostępność** (oraz **Automatyzacja**) dla aplikacji, z której uruchamiasz skrypt
  (np. Terminal, iTerm). Bez niego program nie może nacisnąć Enter w WhatsAppie.

## Instalacja

```bash
git clone https://github.com/<twoj-login>/losowanie-whatsapp.git
cd losowanie-whatsapp
```

## Użycie

```bash
python3 losowanie_whatsapp.py
```

Przeglądarka otworzy się sama pod adresem `http://127.0.0.1:8765/`.

1. **Uczestnicy:** wpisz listę, jedna osoba w linii:
   ```
   Anna, 600 100 200
   Bartek, +48 601 200 300
   Celina, 0049 151 2345678
   ```
   - Separator: przecinek, średnik albo tabulator.
   - Numer bez kierunkowego program traktuje jako polski (+48).
   - Imiona muszą być różne. Przy dwóch Aniach dopisz inicjał nazwiska.
   - Wpisz też **swój numer**: posłuży do testu i do neutralnego czatu na koniec.
2. **Losuj.** Wynik trafia tylko do pamięci programu.
3. **Test na mój numer.** Sprawdź, czy wiadomość wyszła i czy końcówka schowała się pod
   „Czytaj więcej”.
4. **Wyślij wszystkim → „Rozumiem, start”** i odwróć się od ekranu. Wróć o podanej godzinie
   albo po dwóch dźwiękach.
5. Jeśli komuś nie doszło, użyj przycisku **„Wyślij ponownie”** przy tej osobie.
6. **Zakończ:** wyniki zostaną trwale usunięte z pamięci.

### Opcje uruchomienia

| Opcja | Działanie |
|---|---|
| `--dry-run` | tryb próbny: nic nie jest wysyłane, w terminalu widać tylko numery |
| `--no-browser` | nie otwieraj przeglądarki automatycznie |

### Ustawienia w aplikacji

| Ustawienie | Domyślnie | Opis |
|---|---|---|
| Opóźnienie startu | 15 s | czas na odwrócenie się od ekranu (10–60 s) |
| Czas na otwarcie czatu | 4 s | zwiększ, jeśli WhatsApp otwiera czaty wolno i wiadomości nie wychodzą |

## Jak wygląda wiadomość

```
🎁 Wigilia 2026
Cześć Anna! Ta wiadomość jest tylko dla Ciebie.
Kliknij „Czytaj więcej” i przewiń na sam dół ⬇️
·
·   (40 linii odstępu)
·
Wylosowana osoba: *Bartek* 🎉

Nikomu nie mów 🤫
```

## Jak to działa

```
przeglądarka (UI)  ──HTTP 127.0.0.1──▶  losowanie_whatsapp.py  ──open whatsapp://send──▶  WhatsApp Desktop
                                         (wyniki tylko w RAM)   ──osascript: Enter─────▶
```

- Serwer nasłuchuje wyłącznie na `127.0.0.1` i nie zapisuje logów.
- Do przeglądarki trafiają tylko imiona i status wysyłki, nigdy wyniki losowania.
- Losowanie korzysta z `secrets.SystemRandom` (kryptograficzne źródło losowości).
  Wariant bez łańcucha losuje nieporządek z rozkładem jednostajnym metodą odrzucania.
- Lista uczestników (imiona i numery, bez wyników) zapisuje się w `localStorage` przeglądarki
  dla wygody.

## ⚠️ Ograniczenia: przeczytaj przed użyciem

Aplikacja chroni wyniki **przed przypadkowym podejrzeniem**, ale to nie jest ochrona
kryptograficzna:

- **Wysłane wiadomości zostają w historii WhatsAppa organizatora,** także na jego telefonie.
  Organizator nie powinien otwierać czatów z uczestnikami, dopóki nie usunie tych wiadomości
  u siebie („Usuń u mnie”).
- **Ukrywanie pod „Czytaj więcej”** zależy od wersji WhatsAppa. Sprawdź je przyciskiem „Test”.
- **Podczas wysyłki wyniki są przez chwilę na ekranie.** Stąd tryb „nie patrz”.
- **Automatyzacja klawiatury** (AppleScript) może przestać działać po aktualizacji WhatsAppa.
  Gdy czat otworzy się zbyt wolno, wiadomość zostanie jako szkic w polu tekstowym.
  Pomaga zwiększenie „Czasu na otwarcie czatu”.
- **Organizator z dostępem do kodu i komputera** mógłby go zmodyfikować. Rozwiązanie opiera
  się na zaufaniu do organizatora.

Pełną tajność, także wobec nadawcy, dałoby szyfrowanie kluczem publicznym każdego uczestnika.
Ten wariant jest na liście pomysłów.

## Rozwiązywanie problemów

| Problem | Rozwiązanie |
|---|---|
| „Brak uprawnienia Dostępności” | Ustawienia systemowe → Prywatność i ochrona → Dostępność → włącz Terminal. Uruchom ponownie skrypt. |
| WhatsApp otwiera czat, ale nie wysyła | Zwiększ „Czas na otwarcie czatu” do 6–8 s. Sprawdź, czy WhatsApp nie pokazuje okna logowania. |
| „Address already in use” | Program już działa w innym oknie terminala. Zamknij go (Ctrl+C) albo otwórz `http://127.0.0.1:8765/`. |
| Wiadomość nie doszła do jednej osoby | Użyj „Wyślij ponownie” przy tej osobie (z trybem „nie patrz”). |

## Testy

```bash
python3 -m unittest discover -s tests -v
```

## Licencja

[MIT](LICENSE): otwarta licencja. Możesz używać, kopiować, modyfikować i rozpowszechniać kod (także komercyjnie), pod warunkiem zachowania informacji o autorze.

Autor: WojtekPugowski
