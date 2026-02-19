# ⚡ Energy Hub Poland
## Your intelligent energy cost assistant for Home Assistant

![GitHub Release](https://img.shields.io/github/v/release/AllonGit/energy_hub_poland?style=flat-square&color=blue)
![License](https://img.shields.io/github/license/AllonGit/energy_hub_poland?style=flat-square&color=green)
![HACS](https://img.shields.io/badge/HACS-Custom-orange?style=flat-square)
![Maintenance](https://img.shields.io/badge/Maintained%3F-yes-green.svg?style=flat-square)

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=AllonGit&repository=energy_hub_poland&category=integration)

<p align="center">
  <img src="brands/dark_logo@2x.png" width="400" alt="Energy Hub Poland Logo">
</p>

---

**Energy Hub Poland** is an advanced Home Assistant integration designed specifically for the Polish energy market. It allows you to monitor electricity prices, analyze costs, and optimize energy consumption based on actual tariffs (including dynamic RCE rates).

A unique feature is the **Comparison Mode**, which analyzes your consumption patterns and recommends the most cost-effective tariff for your household.

## 🌟 Features and Operation Modes

The integration supports four main operational modes:

### 1. 📉 Dynamic Mode (RCE)
Fetches hourly market rates directly from PSE/TGE (Polish Power Exchange).
* Perfect for prosumers on net-billing.
* Displays net prices (excluding VAT and distribution fees).

### 2. 🏠 G12 Mode
Classic Time-of-Use (ToU) tariff defined by the user.
* Allows manual entry of peak hours ranges (e.g., `6-13,15-22`).
* Tracks costs separately for peak and off-peak zones.

### 3. 🏖️ G12w Mode (Weekend)
Extended ToU tariff that accounts for the Polish holiday calendar.
* Automatically treats **Saturdays, Sundays, and Polish statutory holidays** as off-peak zones.
* Uses the `holidays` library for precise detection of non-working days in Poland.

### 4. 📊 Comparison Mode (Experimental)
The integration's most powerful feature.
* Calculates energy costs for **all three tariff types simultaneously** in real-time.
* Indicates potential savings if you were to switch tariffs.
* Requires a connected energy meter sensor (kWh, `total_increasing` type).

---

## 🚀 Installation

### Step 1: Installation via HACS

1. Open **HACS** in Home Assistant.
2. Click the menu (three dots) in the top right corner and select **Custom repositories**.
3. Paste the URL: `https://github.com/AllonGit/energy_hub_poland`.
4. Select type: **Integration**.
5. Click **Download**.
6. **Restart Home Assistant**.

### Step 2: Configuration

1. Go to **Settings** -> **Devices & Services**.
2. Click the **Add Integration** button.
3. Search for **Energy Hub Poland**.
4. Follow the configuration wizard:
   * Select your default operation mode.
   * Input your energy meter entity (required for cost calculations).
   * Define peak hours (if using G12).

---

## 🚀 New Sensors and Automations

In version v1.2.1, we've introduced sensors to simplify home automation:

* **Average Daily Price**: Compare the current price with the average price for today and tomorrow.
* **Low Price Hour**: Schedule a dishwasher or laundry for a specific time.
* **Price Jump (Binary Sensor)**: Automatically turns on when the price is **30% higher** than the daily average. Ideal for turning off energy-intensive devices (e.g., a boiler) during price peaks.

---

## 💡 Usage Examples

Here is how you can leverage Energy Hub Poland in your automations:

* **Smart Charging:** Start your EV charger only when the dynamic tariff price drops below a certain threshold.
* **Savings Alerts:** Receive a notification at the end of the month with insights from Comparison Mode: *"If you used the G12w tariff, you would have saved 50 PLN this month."*
* **Visual Indicators:** Change your living room light color to red when the current energy price is in the daily peak range.

---

## 📈 Visualization - ApexCharts

To visualize dynamic prices (RCE) on a chart, we recommend using the **ApexCharts** card. Below is the ready-to-use configuration code.

**Instructions:**
1. Ensure you have the [ApexCharts Card](https://github.com/RomRider/apexcharts-card) installed via HACS.
2. Add a new "Manual" card to your Lovelace dashboard.
3. Paste the following code:

```yaml
type: custom:apexcharts-card
experimental:
  color_threshold: true
header:
  show: true
  title: Ceny Energii (Dziś + Jutro)
  show_states: true
  colorize_states: true
  standard_format: false
now:
  show: true
  label: TERAZ
  color: "#29B6F6"
graph_span: 48h
span:
  start: day
yaxis:
  - min: 0
    decimals: 2
    apex_config:
      forceNiceScale: true
apex_config:
  stroke:
    curve: smooth
    width: 2
  xaxis:
    labels:
      format: HH:mm
  annotations:
    xaxis:
      - x: <%= new Date().setHours(24,0,0,0) %>
        strokeDashArray: 4
        borderColor: "#e74c3c"
        borderWidth: 2
        label:
          text: JUTRO
          style:
            color: "#fff"
            background: "#e74c3c"
series:
  - entity: sensor.energy_hub_poland_energy_hub_poland_cena_dynamic
    name: Aktualna
    color: "#03A9F4"
    show:
      in_header: true
      in_chart: false
  - entity: sensor.energy_hub_poland_energy_hub_poland_cena_minimalna_dzis
    name: Min Dziś
    color: "#00E676"
    show:
      in_header: true
      in_chart: false
  - entity: sensor.energy_hub_poland_energy_hub_poland_cena_maksymalna_dzis
    name: Max Dziś
    color: "#FF1744"
    show:
      in_header: true
      in_chart: false
  - entity: sensor.energy_hub_poland_energy_hub_poland_cena_dynamic
    name: Cena
    type: area
    show:
      in_header: false
    color_threshold:
      - value: 0
        color: "#2ecc71"
      - value: 0.5
        color: "#f39c12"
      - value: 0.7
        color: "#e74c3c"
    data_generator: |
      if (!entity.attributes.today_prices) return [];
      const data = [];
      const startTs = new Date().setHours(0, 0, 0, 0);
      for (const [h, p] of Object.entries(entity.attributes.today_prices)) {
        data.push([startTs + (parseInt(h) * 3600000), p]);
      }
      const tom = entity.attributes.tomorrow_prices || {};
      for (const [h, p] of Object.entries(tom)) {
        data.push([startTs + 86400000 + (parseInt(h) * 3600000), p]);
      }
      return data;
```

### ⚡ Energy Dashboard Integration
To ensure Home Assistant correctly calculates costs in the official Energy dashboard:

Go to Settings -> Dashboards -> Energy.

In the Grid Consumption section, edit your energy source (meter).

In the Use an entity with current price field, select: sensor.energy_hub_current_price.

Save changes.

### 📖 Documentation and Help
I invite you to the [forum](https://community.home-assistant.io/t/custom-component-pge-datahub-poland-dynamic-electricity-prices/970823)

Found a bug? Report it in the [Issues](https://github.com/AllonGit/energy_hub_poland/issues).

Discussions and feature requests: [Discussions](https://github.com/AllonGit/energy_hub_poland/discussions).

### ⚖️ License and Legal Notice
This project is licensed under the **Apache 2.0** license.

Commercial Use Restriction: The unique tariff comparison logic (Comparison Mode) and recommendation algorithms are provided for private, non-commercial use only. Using these specific modules in commercial products without the author's permission is prohibited.

Created by AllonGit. Market data (RCE) is sourced from public APIs of energy operators.

*© 2026 AllonGit*
