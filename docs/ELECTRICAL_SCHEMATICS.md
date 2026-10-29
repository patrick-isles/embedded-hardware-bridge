# Electrical Engineering & Circuit Theory Specifications
**Project**: `embedded-hardware-bridge`  
**Author**: Patrick Isles  
**Academic Context**: Portland Community College — Electronic Engineering Technology (EET) & Philosophy (PSU B.A.)  
**Document Revision**: 1.0.0 (October 2026)

---

## 1. Overview and System Topology

The **Embedded Hardware Bridge (EHB)** provides a production-grade interface between low-level electronic circuit telemetry and Linux system observability. It bridges physical (or Hardware-in-the-Loop simulated) microcontroller measurements into the Prometheus monitoring ecosystem.

```
       [ DC Power Source: 5.0V / 3.3V ]
                     │
                     ▼
         ┌───────────────────────┐
         │ Current Shunt Resistor│
         │   R_shunt = 0.100 Ω   │──────┐
         └───────────────────────┘      │
                     │                  │
        ┌────────────┴────────────┐     │ Differential
        │                         │     │ Sense (I = ΔV/R)
        ▼                         ▼     ▼
┌───────────────┐         ┌──────────────────────┐
│ Dynamic Load  │         │  12-bit ADC / MCU    │
│  R_L = 10-50Ω │         │  (STM32 / ATmega)    │
└───────────────┘         └──────────────────────┘
        │                            │
       GND                  UART TX  │ 115200 8N1 (CRC-16 Framing)
                                     ▼
                          ┌──────────────────────┐
                          │ Linux Host / Kernel  │
                          │   ehb-daemon (:9105) │
                          └──────────────────────┘
                                     │
                                     ▼
                          [ Prometheus / Grafana ]
```

---

## 2. Core Electrical Calculations & DC Circuit Theory

### 2.1 Ohm's Law and Power Dissipation
The circuit telemetry daemon continually solves for dynamic circuit impedance and instantaneous power dissipation across the DC power rail:

$$\begin{aligned}
V &= I \cdot R_L \\
P &= V \cdot I = I^2 \cdot R_L = \frac{V^2}{R_L}
\end{aligned}$$

Where:
* $V$: Terminal DC bus voltage ($V \in [0.0, 5.5\text{ V}]$).
* $I$: Loop current ($I \in [0.0, 1.0\text{ A}]$) measured across low-side/high-side shunt.
* $P$: Power consumed by the active load ($W$).
* $R_L$: Dynamic instantaneous load resistance ($\Omega$).

### 2.2 Low-Side Current Sensing
Current measurement utilizes a precision low-side current-sense resistor ($R_{shunt} = 100\text{ m}\Omega, \pm 0.1\%$):

$$I_{load} = \frac{V_{shunt}}{R_{shunt}} = \frac{V_{shunt}}{0.100\ \Omega} = 10.0 \cdot V_{shunt}$$

---

## 3. Analog-to-Digital Converter (ADC) Quantization

### 3.1 12-Bit Quantization Resolution
The microcontroller utilizes a successive-approximation register (SAR) 12-bit ADC with an internal voltage reference $V_{ref} = 5.000\text{ V}$.

The total number of discrete quantization states is:

$$N = 2^{12} = 4096\ \text{discrete steps}\ (0 \text{ to } 4095)$$

The Least Significant Bit (LSB) voltage weight is:

$$V_{LSB} = \frac{V_{ref}}{2^{12} - 1} = \frac{5.000\text{ V}}{4095} \approx 1.2210\text{ mV / code}$$

For any raw integer ADC register reading $D_{raw} \in [0, 4095]$:

$$V_{measured} = D_{raw} \cdot V_{LSB} = D_{raw} \cdot \left(\frac{5.000}{4095}\right)$$

### 3.2 Voltage Divider Attenuation Network
For input potentials exceeding $V_{ref}$ (such as 12V automotive or 24V industrial rails), a passive resistor divider attenuates $V_{in}$:

```
     V_in o──────[ R1 ]──────┬──────o V_adc (To MCU)
                             │
                           [ R2 ]
                             │
                            GND
```

$$V_{adc} = V_{in} \cdot \left( \frac{R_2}{R_1 + R_2} \right)$$

With standard $1\%$ precision resistors ($R_1 = 10\text{ k}\Omega, R_2 = 4.7\text{ k}\Omega$):

$$\text{Attenuation Ratio } \alpha = \frac{4.7}{10.0 + 4.7} = 0.3197$$

---

## 4. Thermistor Thermal Modeling (NTC Sensor)

Temperature telemetry is acquired via an NTC (Negative Temperature Coefficient) $10\text{ k}\Omega$ thermistor biased against a pull-up resistor $R_{bias} = 10\text{ k}\Omega$.

The non-linear resistance profile is modeled via the **Beta parameter equation**:

$$\frac{1}{T} = \frac{1}{T_0} + \frac{1}{\beta} \ln\left( \frac{R(T)}{R_0} \right)$$

Where:
* $T_0 = 298.15\text{ K}$ ($25^\circ\text{C}$).
* $R_0 = 10000\ \Omega$.
* $\beta = 3950\text{ K}$ (material constant).
* $T$ is temperature in Kelvin; $T_{Celsius} = T - 273.15$.

---

## 5. Serial Binary Packet Framing & Error Detection

### 5.1 Packet Frame Geometry (19 Bytes)

All serial frames transmitted across the UART link adhere to strict binary encapsulation:

| Byte Offset | Field Name | Data Type | Endianness | Description |
|---|---|---|---|---|
| `0x00` | `SYNC_0` | `uint8` | — | Constant `0xAA` |
| `0x01` | `SYNC_1` | `uint8` | — | Constant `0x55` |
| `0x02` | `PAYLOAD_LEN` | `uint8` | — | Length of payload (`0x0E` = 14 bytes) |
| `0x03 - 0x04` | `Voltage_mV` | `uint16` | Big-Endian | Bus potential ($0 - 65535\text{ mV}$) |
| `0x05 - 0x06` | `Current_mA` | `uint16` | Big-Endian | Current ($0 - 65535\text{ mA}$) |
| `0x07 - 0x08` | `Raw_ADC` | `uint16` | Big-Endian | 12-bit ADC code ($0 - 4095$) |
| `0x09 - 0x0A` | `Temp_cdegC` | `int16` | Big-Endian | Centi-degrees Celsius ($2540 = 25.40^\circ\text{C}$) |
| `0x0B` | `GPIO_Port` | `uint8` | Bitmask | Digital pins D0–D7 logic levels |
| `0x0C` | `Fault_Flags`| `uint8` | Bitmask | Bit 0: OverVoltage, Bit 1: Brownout, Bit 2: OverTemp |
| `0x0D - 0x10` | `Sequence_ID`| `uint32` | Big-Endian | Monotonic packet transmission counter |
| `0x11 - 0x12` | `CRC16` | `uint16` | Big-Endian | CRC-16-CCITT check over bytes `0x03 - 0x10` |

### 5.2 CRC-16-CCITT Algorithm
To detect bit-rot, electromagnetic interference (EMI), and UART baud clock skew, frames are validated using CRC-16-CCITT:

* **Generator Polynomial**: $G(x) = x^{16} + x^{12} + x^5 + 1$ (`0x1021`)
* **Initial Seed**: `0xFFFF`
* **Bit Flip Detection**: Guarantees detection of all single and double-bit burst errors $\le 16$ bits.

Standard reference check vector:
$$\text{ASCII string } \texttt{"123456789"} \implies \texttt{0x29B1}$$

---

## 6. Fault Trip Matrices & Safety Thresholds

The telemetry engine actively watches for electrical anomalies:

| Anomaly State | Condition | Firmware Action | Prometheus Metric Flag |
|---|---|---|---|
| **Over-Voltage (OV)** | $V_{bus} > 5.30\text{ V}$ | Flag bit 0 set; Load disconnect alarm | `eet_fault_active{fault="overvoltage"} = 1` |
| **Brownout (BO)** | $V_{bus} < 4.50\text{ V}$ | Flag bit 1 set; Logic reset safety | `eet_fault_active{fault="brownout"} = 1` |
| **Over-Temperature (OT)** | $T_{sens} > 75.0^\circ\text{C}$ | Flag bit 2 set; Thermal throttling | `eet_fault_active{fault="overtemp"} = 1` |
| **CRC Corruption** | Frame CRC mismatch | Frame dropped; counter incremented | `eet_crc_errors_total += 1` |
