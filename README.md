# Embedded Hardware Bridge (`embedded-hardware-bridge`)

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python: 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![Protocol: CRC--16--CCITT](https://img.shields.io/badge/CRC16-CCITT%200x1021-green.svg)](docs/ELECTRICAL_SCHEMATICS.md)
[![Telemetry: Prometheus](https://img.shields.io/badge/Metrics-Prometheus%20:9105-orange.svg)](http://localhost:9105/metrics)
[![Dependencies: Pure Stdlib](https://img.shields.io/badge/Dependencies-Zero%20External%20Pip-success.svg)](README.md)

> **Bridge DC/AC circuit theory, 12-bit ADC quantization, and microcontroller serial telemetry into Linux systems engineering and Prometheus observability.**

`embedded-hardware-bridge` is an open-source, production-grade telemetry pipeline connecting physical embedded hardware (or virtual Hardware-in-the-Loop simulated circuits) to Linux observability stacks. It reads framed binary serial packets over physical UART (`/dev/ttyUSB0`) or virtual Linux pseudo-terminals (`pty`), calculates real-time electrical parameters ($V, I, P = VI, R = V/I$), validates integrity using CRC-16-CCITT, checks for hardware electrical faults, and exports metrics directly to **Prometheus** on port `:9105` alongside an interactive terminal oscilloscope.

---

## Architecture Topology

```
   ┌──────────────────────────────────────────────────────────────┐
   │            PHYSICAL CIRCUIT OR HIL SIMULATOR                 │
   │                                                              │
   │  [DC Bus: 5V] ───[Current Shunt]───[Dynamic Load R_L] ── GND │
   │         │               │                     ▲              │
   │         ▼               ▼                     │              │
   │   [Voltage Sense]  [Current Sense]       [PWM Logic]         │
   │         │               │                     │              │
   │         └───────┬───────┴─────────────────────┘              │
   │                 ▼                                            │
   │     [12-Bit ADC / MCU Register]                              │
   │     - V_bus, I_bus, Temp (°C), GPIO (8-pin bitmask)          │
   │     - CRC-16-CCITT Frame Assembly (19-byte binary packet)    │
   └─────────────────────────┬────────────────────────────────────┘
                             │ UART Stream (115200 8N1 / PTY)
                             ▼
   ┌──────────────────────────────────────────────────────────────┐
   │         LINUX TELEMETRY DAEMON (`ehb-daemon`)                │
   │                                                              │
   │  - Frame Hunting & Sync Lock (`0xAA55`)                      │
   │  - CRC-16-CCITT Polynomial Integrity Verification            │
   │  - Real-Time Electrical Computations:                        │
   │      • Dynamic Impedance:  R = V / I                         │
   │      • Power Dissipation:  P = V * I                         │
   │      • ADC Quantization:   V_lsb = 5.0V / 4095               │
   │  - Fault Matrix: OverVoltage (>5.3V), Brownout (<4.5V),      │
   │                  OverTemp (>75°C)                            │
   └───────────────┬───────────────────────────────┬──────────────┘
                   │                               │
        HTTP GET   ▼                    HTTP GET   ▼
 ┌─────────────────────────────┐    ┌─────────────────────────────┐
 │    PROMETHEUS EXPORTER      │    │    TERMINAL OSCILLOSCOPE    │
 │       port :9105            │    │      (`ehb-monitor`)        │
 │                             │    │                             │
 │   eet_voltage_volts         │    │  • Analog Multi-Gauges      │
 │   eet_current_amperes       │    │  • Real-time Waveform Trace │
 │   eet_power_watts           │    │  • 8-bit GPIO LED Array     │
 │   eet_load_resistance_ohms  │    │  • Electrical Matrix        │
 │   eet_fault_active          │    │  • Fault Alarm Trip Badges  │
 └─────────────────────────────┘    └─────────────────────────────┘
```

---

## Key Features

1. **Pure Standard Library (Zero Pip Dependencies)**:
   - Written in modern, robust Python using standard library modules (`os`, `struct`, `threading`, `http.server`, `urllib`).
   - No external pip dependencies like `pyserial` or `prometheus_client` required. Runs natively out of the box on any Linux host.

2. **Binary Serial Frame Geometry & CRC-16-CCITT**:
   - 19-byte fixed binary packet structure with 2-byte sync header (`0xAA55`), 1-byte length, 14-byte payload, and 2-byte CRC-16 (`0x1021`, initial `0xFFFF`).
   - Handles corrupted frames, noise bursts, and bit flips gracefully with monotonic drop rate counters.

3. **Hardware-in-the-Loop (HIL) Simulator (`ehb-sim`)**:
   - Allocates an isolated Linux Pseudo-Terminal (PTY) pair via `pty.openpty()` linked at `/tmp/ehb-virtual-uart`.
   - Simulates dynamic load steps (e.g. switching between $10\,\Omega$ and $50\,\Omega$), thermal drift, voltage ripple, and GPIO pin clocking.

4. **Interactive Terminal Oscilloscope & Multimeter (`ehb-monitor`)**:
   - Live ASCII voltmeter, ammeter, power gauge, and temperature meter.
   - Scrolling 52-sample time-domain waveform graph displaying real-time voltage ripple.
   - 8-channel digital logic state indicator (`HIGH` ● / `LOW` ○) with raw binary and hex registers.

5. **Prometheus / Grafana Exporter**:
   - Standards-compliant OpenMetrics `/metrics` endpoint serving typed gauges and counters with full label support (`pin="0..7"`, `fault="overvoltage|brownout|overtemp"`).

---

## Binary Packet Specification (19 Bytes)

| Offset | Field | Type | Unit / Description |
|---|---|---|---|
| `0x00 - 0x01` | `SYNC` | `uint8[2]` | Synchronization word: `0xAA 0x55` |
| `0x02` | `LEN` | `uint8` | Payload length: `0x0E` (14 bytes) |
| `0x03 - 0x04` | `Voltage_mV` | `uint16` (BE) | DC Bus Voltage in millivolts ($0 - 65,535\text{ mV}$) |
| `0x05 - 0x06` | `Current_mA` | `uint16` (BE) | DC Bus Current in milliamperes ($0 - 65,535\text{ mA}$) |
| `0x07 - 0x08` | `Raw_ADC` | `uint16` (BE) | 12-bit ADC raw register code ($0 - 4095$) |
| `0x09 - 0x0A` | `Temp_cdeg` | `int16` (BE) | Thermal probe in centi-degrees Celsius ($2540 = 25.40^\circ\text{C}$) |
| `0x0B` | `GPIO` | `uint8` | 8-bit digital GPIO pin register (D0–D7) |
| `0x0C` | `Faults` | `uint8` | Bit 0: OverVoltage, Bit 1: Brownout, Bit 2: OverTemp |
| `0x0D - 0x10` | `Seq_ID` | `uint32` (BE) | Monotonic transmission sequence counter |
| `0x11 - 0x12` | `CRC16` | `uint16` (BE) | CRC-16-CCITT ($x^{16} + x^{12} + x^5 + 1$) over payload |

---

## Installation & Quickstart

### 1. Installation
Clone the repository and run the automated installer:
```bash
git clone https://github.com/patrick-isles/embedded-hardware-bridge.git
cd embedded-hardware-bridge
./install.sh
```
This adds `ehb-sim`, `ehb-daemon`, and `ehb-monitor` to your `~/.local/bin`.

### 2. Launching Hardware-in-the-Loop Simulation
In Terminal 1, launch the simulated microcontroller circuit:
```bash
ehb-sim
```
*Output:*
```
[ehb-sim] PTY Loopback active: /tmp/ehb-virtual-uart
[ehb-sim] Streaming HIL circuit telemetry (10.0 Hz) ...
```

### 3. Launching the Telemetry Daemon
In Terminal 2, start the daemon:
```bash
ehb-daemon --verbose
```
*Output:*
```
[ehb-daemon] Monitoring hardware bus on: /tmp/ehb-virtual-uart
[ehb-daemon] Prometheus metrics exporter online: http://localhost:9105/metrics
[RX #000142] 5.012V | 0.248A | 25.4°C | GPIO: 0b00100101 | CRC: OK
```

### 4. Launching the Terminal Oscilloscope
In Terminal 3, run the live ASCII multi-meter:
```bash
ehb-monitor
```

---

## Prometheus Integration

Add the following scrape configuration to `/etc/prometheus/prometheus.yml`:

```yaml
scrape_configs:
  - job_name: 'embedded_hardware'
    scrape_interval: 1s
    static_configs:
      - targets: ['localhost:9105']
```

### Sample `/metrics` Output:
```promql
# HELP eet_voltage_volts Measured DC bus voltage in Volts
# TYPE eet_voltage_volts gauge
eet_voltage_volts 5.0120

# HELP eet_current_amperes Measured DC bus current in Amperes
# TYPE eet_current_amperes gauge
eet_current_amperes 0.2480

# HELP eet_power_watts Calculated electrical power dissipation in Watts (P = V * I)
# TYPE eet_power_watts gauge
eet_power_watts 1.2430

# HELP eet_load_resistance_ohms Dynamic load resistance in Ohms (R = V / I)
# TYPE eet_load_resistance_ohms gauge
eet_load_resistance_ohms 20.210

# HELP eet_temperature_celsius Measured thermal sensor temperature in Celsius
# TYPE eet_temperature_celsius gauge
eet_temperature_celsius 25.40

# HELP eet_gpio_pin_state Digital logic state of GPIO pins (1=HIGH, 0=LOW)
# TYPE eet_gpio_pin_state gauge
eet_gpio_pin_state{pin="0"} 1
eet_gpio_pin_state{pin="1"} 0
...
```

---

## Automated Unit Testing

Run the automated test suite verifying CRC-16 polynomial checks, packet framing, bit-flip detection, and Ohm's law calculations:

```bash
python3 tests/test_crc16_and_framing.py -v
```

```
test_adc_quantization_resolution (__main__.TestCRC16AndFraming) ... ok
test_crc16_standard_vector (__main__.TestCRC16AndFraming) ... ok
test_crc_detection_on_bit_flip (__main__.TestCRC16AndFraming) ... ok
test_frame_packing_and_length (__main__.TestCRC16AndFraming) ... ok
test_ohms_law_and_power_computations (__main__.TestCRC16AndFraming) ... ok
test_stream_framing_resynchronization (__main__.TestCRC16AndFraming) ... ok

----------------------------------------------------------------------
Ran 6 tests in 0.000s

OK
```

---

## Author & Academic Background

**Patrick Isles**  
* Portland Community College — Electronic Engineering Technology (`EET-100D`)
* Portland State University — B.A. Philosophy
* GitHub: [@patrick-isles](https://github.com/patrick-isles)

Bridging formal electrical circuit principles (Kirchhoff's laws, ADC successive approximation, AC/DC analysis) with low-level Linux systems programming, kernel serial subsystems, and modern observability infrastructure.

---

## License

MIT License. See [LICENSE](LICENSE) for full details.
