![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)
![version](https://img.shields.io/github/v/release/AllonGit/ha_pge_dynamic)
![license](https://img.shields.io/github/license/AllonGit/ha_pge_dynamic)

# PGE Dynamic Energy (Ceny Dynamiczne) dla Home Assistant

Integracja pobierająca aktualne ceny energii elektrycznej (Rynek Bilansujący) bezpośrednio z oficjalnego API **PGE DataHub**. Narzędzie pozwala na monitorowanie stawek giełdowych TGE (Towarowa Giełda Energii) w czasie rzeczywistym bezpośrednio w Twoim panelu Home Assistant.

## 🌟 Główne Funkcje
- **Konfiguracja przez UI:** Proste dodawanie integracji przez interfejs Home Assistant (Config Flow).
- **Wybór Taryfy:** Możliwość wyboru taryfy (G1x/C1x) podczas instalacji (przygotowane pod przyszłe obliczenia kosztów).
- **Cena Netto:** Wyświetla aktualną stawkę rynkową w **PLN/kWh**.
- **Dokładność:** Dane pobierane z kontraktu Fix_1 (Rynek Bilansujący).
- **Kompletna doba:** 24 odrębne sensory godzinne (od `00:00` do `23:00`).
- **Sensor bieżący:** `sensor.pge_cena_aktualna` – pokazuje cenę dla obecnej godziny wraz z atrybutem wybranej taryfy.
- **Optymalizacja:** Używa `DataUpdateCoordinator` dla minimalnego obciążenia sieci i procesora.

## 🚀 Instalacja

### Przez HACS (Zalecane)
1. W Home Assistant przejdź do **HACS** -> **Integracje**.
2. Kliknij trzy kropki w prawym górnym rogu i wybierz **Custom repositories**.
3. Wklej URL tego repozytorium: `https://github.com/AllonGit/ha_pge_dynamic`
4. Wybierz kategorię **Integration** i kliknij **Dodaj**.
5. Znajdź integrację na liście, kliknij **Pobierz**, a następnie zrestartuj Home Assistant.

### Ręczna
1. Skopiuj folder `custom_components/pge_dynamic` do folderu `config/custom_components/`.
2. Zrestartuj Home Assistant.

## ⚙️ Konfiguracja
Integracja nie wymaga już wpisów w pliku `configuration.yaml`!
1. Przejdź do **Ustawienia** -> **Urządzenia oraz usługi**.
2. Kliknij **Dodaj integrację** w prawym dolnym rogu.
3. Wyszukaj `PGE Dynamic Energy`.
4. W oknie konfiguracji wpisz nazwę integracji oraz wybierz swoją taryfę (np. **G1x** dla gospodarstw domowych).
5. Zatwierdź – sensory zostaną utworzone automatycznie.

## 📊 Wykresy (ApexCharts)
Dla najlepszego efektu wizualnego zaleca się użycie karty `ApexCharts Card`. Przykład konfiguracji wyświetlającej ceny godzinowe:

```yaml
type: custom:apexcharts-card
header:
  show: true
  title: Ceny Energii PGE (Netto)
  show_states: true
graph_span: 24h
span:
  start: day
series:
  - entity: sensor.pge_cena_aktualna
    type: column
    color: "#ff9800"
    data_generator: |
      const prices = [];
      for (let i = 0; i < 24; i++) {
        const entity = `sensor.pge_cena_${i.toString().padStart(2, '0')}_00`;
        const state = hass.states[entity];
        if (state) {
          prices.push([new Date().setHours(i, 0, 0, 0), parseFloat(state.state)]);
        }
      }
      return prices;
```

### 💡 Masz pomysł? Zgłoś go!
Projekt jest stale rozwijany i jestem otwarty na nowe funkcjonalności!

* **Masz pomysł** na nowe sensory (np. cena średnia, powiadomienia o najtańszych godzinach)?
* **Chcesz zaproponować** zmiany w kodzie lub ulepszyć algorytm?
* **Znalazłeś błąd** lub problem z działaniem na Twojej wersji Home Assistant?

Zapraszam do sekcji [Issues](https://github.com/AllonGit/ha_pge_dynamic/issues) – każda sugestia pomaga ulepszyć tę integrację dla polskiej społeczności!

---

### ⚖️ Licencja
Projekt udostępniany na licencji **MIT**. Pełną treść znajdziesz w pliku [LICENSE](LICENSE).

---

### ⚠️ Nota prawna
Integracja ma charakter open-source i hobbystyczny. Dane są pobierane z publicznie dostępnego API PGE DataHub. 

**Autor nie ponosi odpowiedzialności** za ewentualne błędy w danych, przerwy w dostawie informacji przez PGE, ani za jakiekolwiek decyzje finansowe (np. planowanie zużycia energii) podejmowane na podstawie odczytów z tej integracji. Zawsze weryfikuj dane u swojego dostawcy energii.