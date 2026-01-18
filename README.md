# ⚡ Energy Hub Poland
### Twój inteligentny asystent kosztów energii w Home Assistant.

### Język/Language
<details>
<summary> click to expand </summary>

**Energy Hub Poland** is an advanced integration that does more than just fetch energy prices. It acts as your personal energy analyst. Whether you use a dynamic tariff (RCE) or a fixed time-of-use tariff (G12/G12w), this system calculates your real costs and suggests how to save money.

![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)
![version](https://img.shields.io/github/v/release/AllonGit/energy_hub_poland?label=version)
![license](https://img.shields.io/github/license/AllonGit/energy_hub_poland?label=license)

<p align="center">
  <img src="images/dark_logo.png" alt="Energy Hub Poland Logo" width="600">
</p>

## 🌟 Features and Operation Modes

The integration offers 4 modes of operation, selected during configuration:

### 1. 📉 Dynamic Mode (RCE / Market Prices)
For users billed according to hourly market rates (PGE DataHub / TGE).
* **Current Price:** Refreshed hourly.
* **Forecast:** Full price schedule for "Tomorrow" (available after ~2:00 PM).
* **Statistics:** Automatic detection of the lowest and highest prices of the day.

### 2. 🏠 G12 / G12w Modes (Time-of-Use Tariffs)
Perfect reflection of your contract with the operator.
* **Flexible Zones:** You define your own peak hours (e.g., `6-13,15-22`).
* **Auto-Holidays (G12w):** The integration automatically recognizes weekends and **Polish statutory holidays** as off-peak (cheap) zones (uses the `holidays` library).
* **Visualization:** A `Zone` sensor shows a clear status: "Peak" (Szczyt) or "Off-peak" (Poza szczytem).

### 3. 📊 Comparison Mode (Savings Simulator)
**The most powerful feature.** It allows you to check the profitability of changing tariffs based on your real usage.
* The system calculates costs in parallel for **Dynamic**, **G12**, and **G12w** tariffs.
* **Balance Sensor:** Shows in PLN (Polish Złoty) how much you saved (or lost) today compared to another tariff.
* **Tariff Recommendation:** An intelligent sensor that analyzes your usage and suggests: *"For you, the cheapest tariff is G12w"*.

---

## 🚀 Installation

### Step 1: HACS
1.  Open **HACS** -> **Integrations**.
2.  Menu (3 dots) -> **Custom repositories**.
3.  Add URL: `https://github.com/AllonGit/energy_hub_poland`
4.  Download the integration and restart Home Assistant.

### Step 2: Configuration
Go to **Settings** -> **Devices & Services** -> **Add Integration** -> **Energy Hub Poland**.

The wizard will guide you through the configuration depending on the selected mode:
1.  **Select Mode:** Dynamic, G12, G12w, or Comparison.
2.  **Prices and Hours (for G12/G12w/Comparison):** Enter net rates and peak hours (format: `6-13,15-22`).
3.  **Energy Sensor (Optional):** Select your electricity meter (kWh, `total_increasing` type) to unlock cost calculations in PLN.

---

## 💡 Key Sensors

After installation, the following entities will appear (names may vary slightly depending on config). 
*Note: Entity friendly names are currently generated in Polish.*

| Function | Example Entity ID | Description |
| :--- | :--- | :--- |
| **Current Price** | `sensor.energy_hub_poland_cena_aktualna` | Current rate for 1 kWh (Net). |
| **Tomorrow's Price** | `sensor.energy_hub_poland_cena_jutro` | Attributes contain the price list for the next day. |
| **Min/Max** | `sensor.energy_hub_poland_cena_min_dzis` | The lowest price value for the current day. |
| **Zone (G12)** | `sensor.energy_hub_poland_strefa_g12` | Status: "Szczyt" (Peak) / "Poza szczytem" (Off-peak). |
| **Cost Today** | `sensor.energy_hub_poland_koszt_dzis_dynamiczna` | How much you spent on electricity today (requires meter). |
| **Balance** | `sensor.energy_hub_poland_bilans_dynamiczna_vs_g12_dzis` | Cost difference between tariffs (Comparison Mode). |
| **Recommendation**| `sensor.energy_hub_poland_rekomendacja_taryfy` | Suggested best tariff for your household. |

### How to add to the Energy Dashboard?
In the official HA "Energy" dashboard settings, under "Grid consumption", select the price entity:
* `sensor.energy_hub_poland_cena_aktualna` (for Dynamic tariff)
* `sensor.energy_hub_poland_cena_aktualna_g12` (for G12 tariff)

---

## ❓ FAQ & Troubleshooting

**1. Do the prices include VAT?**
No. The integration operates on active energy prices (Net). Market prices fetched from the API are Net. Remember that your final bill also includes distribution fees and taxes.

**2. How to enter peak hours?**
Use a comma-separated range format. For example: `6-13,15-22` means peak hours are from 06:00 to 13:00 AND from 15:00 to 22:00.

---

## ⚖️ License and Legal Notice

The integration retrieves data from the publicly available PGE DataHub API. The author is not responsible for financial decisions made based on sensor readings.

**Project is released under the Apache 2.0 License with the following additional restrictions:**

1.  **Private Use:** You are free to use, modify, and install this software for private and educational purposes.
2.  **Commercial Restriction:** The use of the unique tariff comparison logic, recommendation algorithms, and the "Energy Hub" brand in paid products, commercial advisory services, or closed systems **is prohibited without the written consent of the author**.
3.  **Trademarks:** The name "Energy Hub Poland" and associated logos are trademarks of the author.

*Copyright (c) 2026 AllonGit*
</p>
</details>


**Energy Hub Poland** to zaawansowana integracja, która nie tylko pobiera ceny energii, ale działa jak Twój osobisty analityk. Niezależnie od tego, czy masz taryfę dynamiczną, czy stałą (G12/G12w), system policzy Twoje realne koszty i podpowie, jak oszczędzać.

![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)
![version](https://img.shields.io/github/v/release/AllonGit/energy_hub_poland?label=wersja)
![license](https://img.shields.io/github/license/AllonGit/energy_hub_poland?label=licencja)

<p align="center">
  <img src="images/dark_logo.png" alt="Energy Hub Poland Logo" width="600">
</p>

## 🌟 Możliwości i Tryby Pracy

Integracja oferuje 4 tryby pracy, wybierane podczas konfiguracji:

### 1. 📉 Tryb Dynamiczny (RCE)
Dla użytkowników rozliczających się wg stawek godzinowych z giełdy (PGE DataHub).
* **Aktualna cena:** Odświeżana co godzinę.
* **Prognoza:** Pełny harmonogram cen na "Jutro" (dostępny po godz. 14:00).
* **Statystyki:** Automatyczne wykrywanie najniższej i najwyższej ceny dnia.

### 2. 🏠 Tryby G12 / G12w (Taryfy Strefowe)
Idealne odwzorowanie Twojej umowy z operatorem.
* **Elastyczne strefy:** Sam definiujesz godziny szczytu (np. `6-13,15-22`).
* **Auto-Święta (G12w):** Integracja automatycznie rozpoznaje weekendy oraz **polskie święta ustawowe** jako strefę tanią (wymaga biblioteki `holidays`).
* **Wizualizacja:** Sensor `Strefa` pokazuje czytelny status: "Szczyt" lub "Poza szczytem".

### 3. 📊 Tryb Porównawczy (Symulator Oszczędności)
**Najpotężniejsza funkcja integracji.** Pozwala sprawdzić opłacalność zmiany taryfy na żywym organizmie.
* System liczy koszty równolegle dla **Dynamicznej**, **G12** i **G12w**.
* **Sensor Bilansu:** Pokazuje w PLN, ile zyskałeś (lub straciłeś) danego dnia względem innej taryfy.
* **Rekomendacja Taryfy:** Inteligentny sensor, który analizuje Twoje zużycie i wskazuje: *"Dla Ciebie najtańsza jest taryfa G12w"*.

---

## 🚀 Instalacja

### Krok 1: HACS
1.  Otwórz **HACS** -> **Integracje**.
2.  Menu (3 kropki) -> **Niestandardowe repozytoria**.
3.  Dodaj URL: `https://github.com/AllonGit/energy_hub_poland`
4.  Pobierz integrację i zrestartuj Home Assistant.

### Krok 2: Konfiguracja
Wejdź w **Ustawienia** -> **Urządzenia oraz usługi** -> **Dodaj integrację** -> **Energy Hub Poland**.

Kreator poprowadzi Cię przez konfigurację zależną od wybranego trybu:
1.  **Wybór Trybu:** Dynamiczny, G12, G12w lub Porównawczy.
2.  **Ceny i Godziny (dla G12/G12w/Porównawczego):** Podaj stawki netto i godziny szczytu (format: `6-13,15-22`).
3.  **Sensor Energii (Opcjonalny):** Wskaż swój licznik zużycia (kWh, typ `total_increasing`), aby odblokować obliczanie kosztów w złotówkach.

---

## 💡 Kluczowe Sensory

Po instalacji w systemie pojawią się encje (nazwy mogą się różnić w zależności od konfiguracji):

| Funkcja | Przykładowa nazwa encji | Opis |
| :--- | :--- | :--- |
| **Cena bieżąca** | `sensor.energy_hub_poland_cena_aktualna` | Aktualna stawka za 1 kWh (netto). |
| **Cena jutro** | `sensor.energy_hub_poland_cena_jutro` | Atrybuty zawierają listę cen na kolejny dzień. |
| **Min/Max** | `sensor.energy_hub_poland_cena_min_dzis` | Wartość najniższej ceny w danym dniu. |
| **Strefa (G12)** | `sensor.energy_hub_poland_strefa_g12` | Stan: "Szczyt" / "Poza szczytem". |
| **Koszt Dziś** | `sensor.energy_hub_poland_koszt_dzis_dynamiczna` | Ile wydałeś dzisiaj na prąd (wymaga licznika). |
| **Bilans** | `sensor.energy_hub_poland_bilans_dynamiczna_vs_g12_dzis` | Różnica kosztów między taryfami (Tryb Porównawczy). |
| **Rekomendacja**| `sensor.energy_hub_poland_rekomendacja_taryfy` | Sugerowana najlepsza taryfa dla Twojego domu. |

### Jak dodać do panelu Energia?
W oficjalnym dashboardzie "Energia" w HA, w sekcji "Sieć elektryczna", jako cenę wybierz encję:
* `sensor.energy_hub_poland_cena_aktualna` (dla taryfy dynamicznej)
* `sensor.energy_hub_poland_cena_aktualna_g12` (dla taryfy G12)

---

## ❓ FAQ & Troubleshooting

**1. Czy ceny zawierają VAT?**
Nie. Integracja operuje na cenach energii czynnej (netto/brutto zależnie co wpiszesz w G12, ale z API pobierane są ceny rynkowe netto). Pamiętaj, że pełny rachunek zawiera też opłaty dystrybucyjne.

**2. Jak wpisać godziny szczytu?**
Użyj formatu zakresów oddzielonych przecinkiem, np.: `6-13,15-22` oznacza szczyt od 06:00 do 13:00 ORAZ od 15:00 do 22:00.

---

## ⚖️ Licencja i Nota Prawna

Integracja pobiera dane z publicznie dostępnego API PGE DataHub. Autor nie ponosi odpowiedzialności za decyzje finansowe podejmowane na podstawie wskazań sensorów.

**Projekt udostępniany na licencji Apache 2.0 z dodatkowymi zastrzeżeniami:**

1.  **Użytek Prywatny:** Wolno Ci używać, modyfikować i instalować to oprogramowanie w celach prywatnych i edukacyjnych.
2.  **Ochrona Komercyjna:** Wykorzystywanie unikalnej logiki porównywania taryf, algorytmów rekomendacji oraz marki "Energy Hub" w płatnych produktach, usługach doradczych lub rozwiązaniach komercyjnych **jest zabronione bez pisemnej zgody autora**.
3.  **Znaki Towarowe:** Nazwa i logo "Energy Hub Poland" są własnością autora.

*Copyright (c) 2026 AllonGit*