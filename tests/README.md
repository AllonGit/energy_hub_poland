# Testy — Energy Hub Poland

## Szybki start

```bash
# 1. Sklonuj repo i wejdź do katalogu
git clone https://github.com/abnvle/energy_hub_poland.git
cd energy_hub_poland

# 2. Utwórz i aktywuj wirtualne środowisko
python -m venv .venv
# Windows:
.venv\Scripts\activate
# Linux/macOS:
source .venv/bin/activate

# 3. Zainstaluj zależności testowe
pip install -r requirements_test.txt

# 4. Uruchom testy jednostkowe
python -m pytest tests/ -v -m "not contract"

# 5. Uruchom testy kontraktowe (wymaga internetu)
python -m pytest tests/ -v -m contract
```

## Struktura testów

```
tests/
├── common.py                        # Współdzielone stałe i helpery
├── conftest.py                      # Stuby HA + fixture'y pytest
├── test_helpers.py                  # Funkcje pomocnicze (DST, taryfy, święta)
├── test_config_flow_validators.py   # Walidacja formatu godzin i entity ID
├── test_coordinator_parse_prices.py # Parsowanie odpowiedzi API na ceny
├── test_coordinator_update.py       # Przejście dnia, cache, obsługa awarii API
├── test_api.py                      # Klient HTTP (mockowany)
├── test_binary_sensor_logic.py      # Wykrywanie skoków cen, status API
├── test_sensor_logic.py             # Sensory: ceny, średnia, min/max, delta energii
└── test_api_contract.py             # Testy kontraktowe (prawdziwe API)
```

## Rodzaje testów

### Testy jednostkowe (`-m "not contract"`)

Testują logikę biznesową w izolacji — bez internetu, bez Home Assistant.
Moduły HA są zastąpione stubami w `conftest.py`.

| Plik | Co testuje |
|------|-----------|
| `test_helpers.py` | `is_summer_time()`, `parse_hour_ranges()`, `is_peak_time()`, ceny G12/G12w, polskie święta |
| `test_config_flow_validators.py` | `validate_hour_format()`, `validate_entity_id()` |
| `test_coordinator_parse_prices.py` | `_parse_prices()` — konwersja JSON → dict godzinowy, obsługa błędnych danych |
| `test_coordinator_update.py` | `_async_update_data()` — przejście dnia (tomorrow→today), ładowanie/zapis cache, zachowanie przy awarii API |
| `test_api.py` | `async_get_prices()` — poprawne zapytanie, timeout, błędy HTTP, nagłówki |
| `test_binary_sensor_logic.py` | `PriceSpikeBinarySensor` (cena > 130% średniej), `ApiStatusBinarySensor` |
| `test_sensor_logic.py` | `_scale_price()`, `AveragePriceSensor`, `CheapestHourSensor`, `MinMaxPriceSensor`, `_get_energy_delta()`, `SavingsSensor` |

### Testy kontraktowe (`-m contract`)

Odpytują prawdziwe API `datahub.gkpge.pl` i sprawdzają, czy format odpowiedzi
się nie zmienił. Uruchamiaj je okresowo — wykryją zmiany po stronie dostawcy danych
zanim użytkownicy zgłoszą problemy.

| Test | Co sprawdza |
|------|-----------|
| `test_api_returns_data_for_today` | Czy endpoint odpowiada |
| `test_response_has_24_records` | Czy zwraca 24 rekordy (1 na godzinę) |
| `test_record_has_date_time_field` | Czy klucz `date_time` istnieje |
| `test_date_time_format` | Czy format to `%Y-%m-%d %H:%M:%S` |
| `test_record_has_attributes_array` | Czy `attributes` jest tablicą |
| `test_price_attribute_exists_and_is_numeric` | Czy atrybut `price` istnieje i jest liczbą |
| `test_price_is_in_expected_range_mwh` | Czy cena jest w rozsądnym zakresie (-500 – 5000 PLN/MWh) |
| `test_full_parse_roundtrip` | Pełny cykl: fetch → parse → 24 godzinne ceny |

## Przydatne komendy

```bash
# Wszystkie testy naraz
python -m pytest tests/ -v

# Tylko konkretny plik
python -m pytest tests/test_helpers.py -v

# Tylko konkretna klasa
python -m pytest tests/test_sensor_logic.py::TestMinMaxPriceSensor -v

# Z pokryciem kodu (wymaga: pip install pytest-cov)
python -m pytest tests/ -m "not contract" --cov=custom_components/energy_hub_poland
```
