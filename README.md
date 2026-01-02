# PGE Dynamic Energy (HACS)

Ceny dynamiczne PGE (FIX_1) dla Home Assistant. 26 sensorów (24h + Min/Max) do inteligentnego ładowania magazynów energii i EV. Realne koszty brutto.

## Funkcje
- **24 sensory godzinowe**: `sensor.pge_cena_00_00` do `sensor.pge_cena_23_00`.
- **Sensory Min/Max**: `sensor.pge_cena_minimalna` oraz `sensor.pge_cena_maksymalna`.
- **Koszty brutto**: Automatyczne doliczanie marży i 23% VAT do cen z API PGE DataHub.
- **Optymalizacja**: Jedno pobranie danych co 15 minut dla wszystkich encji.

## Instalacja
1. W HACS dodaj **Niestandardowe repozytorium**: URL Twojego GitHub.
2. Zainstaluj **PGE Dynamic Energy**.
3. Zrestartuj Home Assistant.
4. Dodaj integrację w **Ustawienia > Urządzenia oraz usługi**.

## Przykład Automatyzacji (Magazyn Energii)
Ładowanie magazynu, gdy cena jest najniższa w ciągu doby:

```yaml
trigger:
  - platform: template
    value_template: "{{ states('sensor.pge_cena_aktualna') == states('sensor.pge_cena_minimalna') }}"
action:
  - service: switch.turn_on
    target:
      entity_id: switch.ladowarka_magazynu

Autor: Allon